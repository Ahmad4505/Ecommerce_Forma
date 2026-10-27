from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError
from orders.models import Order
from orders.services import Conflict
from core.notifications import notify
from .models import Payment
from .adapters import adapter

@transaction.atomic
def initiate(user, order_id, provider):
    order = Order.objects.select_for_update().get(pk=order_id, user=user)
    if order.status == 'Cancelled' or order.payment_status == 'SUCCEEDED':
        raise Conflict('This order cannot be paid.')
    if order.currency not in ['USD','EUR','GBP','SAR','AED']:
        raise ValidationError('Settlement currency is not enabled; only configured two-decimal currencies are supported.')
    if provider == 'mock' and not settings.MOCK_PAYMENTS_ENABLED:
        raise PermissionDenied('Mock payments are disabled.')
    payment, created = Payment.objects.get_or_create(order=order, defaults={'provider':provider,'amount':order.total,'currency':order.currency})
    if payment.provider != provider:
        raise Conflict('An order is bound to its initial payment provider.')
    if not payment.reference:
        if provider == 'mock':
            payment.reference = 'local-'+str(payment.id)
        else:
            payment.reference, payment.checkout_url = adapter(provider).create(payment)
        payment.status = 'REQUIRES_ACTION'
        payment.save()
    return payment

@transaction.atomic
def verify(payment_id, mock_outcome=None, gateway_id=None):
    # Consistent lock order with cancellation/initiation.
    order_id = Payment.objects.values_list('order_id',flat=True).get(pk=payment_id)
    order = Order.objects.select_for_update().get(pk=order_id)
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    if order.status == 'Cancelled':
        raise Conflict('Cancelled orders cannot be paid.')
    if payment.status in ['SUCCEEDED','REFUNDED']:
        return payment
    if payment.provider == 'mock':
        if not settings.MOCK_PAYMENTS_ENABLED or mock_outcome not in ['SUCCEEDED','FAILED','CANCELLED']:
            raise PermissionDenied('Explicit local mock outcome required.')
        result = (mock_outcome, payment.reference)
    else:
        result = adapter(payment.provider).verify(payment,gateway_id=gateway_id)
    if result:
        payment.status, payment.capture_id = result
        payment.save()
        if payment.status == 'SUCCEEDED':
            order.payment_status = 'SUCCEEDED'
            order.save(update_fields=['payment_status'])
            notify(order.user, 'Payment confirmed', f'Payment for {order.id} confirmed: {payment.amount} {payment.currency}.')
    return payment

@transaction.atomic
def refund_payment(actor,payment_id,amount,idempotency_key,reason):
    from .models import Refund
    from core.permissions import is_admin
    from core.models import AuditLog
    if not is_admin(actor):
        raise PermissionDenied()
    order_id = Payment.objects.values_list('order_id',flat=True).get(pk=payment_id)
    Order.objects.select_for_update().get(pk=order_id)
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    existing = Refund.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        if existing.payment_id != payment.id or existing.amount != amount:
            raise Conflict('Refund idempotency key already used.')
        return existing
    pending = sum(r.amount for r in payment.refunds.exclude(status='FAILED'))
    if payment.status != 'SUCCEEDED' or amount <= 0 or pending+amount > payment.amount:
        raise Conflict('Refund amount exceeds available captured funds.')
    refund = Refund.objects.create(payment=payment,amount=amount,idempotency_key=idempotency_key,reason=reason,actor=actor)
    if payment.provider == 'mock':
        if not settings.MOCK_PAYMENTS_ENABLED:
            raise PermissionDenied()
        refund.status,refund.reference='SUCCEEDED','mock-'+str(refund.id)
    else:
        result=adapter(payment.provider).refund(payment,amount,str(idempotency_key))
        refund.reference=result.get('id',result.get('action_id',''))
        # Only completed synchronous refunds are counted; asynchronous provider
        # acknowledgements remain PENDING for reconciliation, not reported as success.
        if payment.provider=='paypal' and result.get('status')=='COMPLETED':
            refund.status='SUCCEEDED'
        elif payment.provider=='hyperpay' and result.get('result',{}).get('code')=='000.000.000':
            refund.status='SUCCEEDED'
    refund.save()
    if refund.status=='SUCCEEDED':
        payment.refunded_amount+=amount
        if payment.refunded_amount==payment.amount:
            payment.status='REFUNDED'
            payment.order.payment_status='REFUNDED'
            payment.order.save(update_fields=['payment_status'])
        payment.save()
    AuditLog.objects.create(actor=actor,action='payment.refund',target=str(payment.id),details={'amount':str(amount),'status':refund.status,'reason':reason})
    return refund

@transaction.atomic
def reconcile_refund(refund_id):
    from .models import Refund
    reference=Refund.objects.select_related('payment').get(pk=refund_id)
    order=Order.objects.select_for_update().get(pk=reference.payment.order_id)
    payment=Payment.objects.select_for_update().get(pk=reference.payment_id)
    refund=Refund.objects.select_for_update().get(pk=refund_id)
    if refund.status!='PENDING' or not refund.reference:
        return refund
    refund.status=adapter(payment.provider).refund_status(refund)
    refund.save(update_fields=['status'])
    if refund.status=='SUCCEEDED':
        payment.refunded_amount+=refund.amount
        if payment.refunded_amount==payment.amount:
            payment.status='REFUNDED'
            order.payment_status='REFUNDED'
            order.save(update_fields=['payment_status'])
        payment.save()
        notify(order.user,'Refund confirmed',f'Refund of {refund.amount} {payment.currency} confirmed for {order.id}.')
    return refund
