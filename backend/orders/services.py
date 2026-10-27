import hashlib
import json
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied, APIException
from accounts.models import User
from core.models import PlatformSettings, AuditLog
from core.notifications import notify
from core.permissions import is_admin, approved
from products.models import Product
from promotions.models import Promotion
from .models import Order, OrderItem

class Conflict(APIException):
    status_code = 409
    default_detail = 'The request conflicts with current state.'

@transaction.atomic
def checkout(user, data):
    if user.role != 'CUSTOMER':
        raise PermissionDenied('Customer account required.')
    # Lock customer first: concurrent identical requests serialize before idempotency lookup.
    User.objects.select_for_update().get(pk=user.pk)
    digest = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
    existing = Order.objects.filter(user=user, idempotency_key=data['idempotency_key']).first()
    if existing:
        if existing.request_hash != digest:
            raise Conflict('Idempotency key was already used for another request.')
        return existing
    counts = {}
    for line in data['items']:
        key = line['productId']
        counts[key] = counts.get(key, 0) + line['quantity']
    products = {p.pk: p for p in Product.objects.select_for_update().filter(pk__in=counts).order_by('pk')}
    # Vendor locks prevent approval suspension racing a checkout decision.
    from vendors.models import Vendor
    stores = {v.pk: v for v in Vendor.objects.select_for_update().select_related('user').filter(pk__in={p.vendor_id for p in products.values()}).order_by('pk')}
    for pk, quantity in counts.items():
        product = products.get(pk)
        if not product or product.status != 'ACTIVE' or stores[product.vendor_id].status != 'APPROVED' or not stores[product.vendor_id].user.is_active or product.stock < quantity:
            raise Conflict('One or more products are unavailable in this quantity.')
    subtotal = sum(products[pk].effective_price*q for pk, q in counts.items())
    discount = Decimal('0')
    if data.get('code'):
        now = timezone.now()
        promotion = Promotion.objects.filter(code=data['code'].upper(), active=True).filter(Q(starts_at__isnull=True)|Q(starts_at__lte=now)).filter(Q(ends_at__isnull=True)|Q(ends_at__gt=now)).first()
        if not promotion:
            raise ValidationError('Coupon is invalid or expired.')
        discount = (subtotal*promotion.percent/100).quantize(Decimal('.01'))
    config, _ = PlatformSettings.objects.get_or_create(pk=1)
    shipping = config.shipping if subtotal < config.free_shipping else Decimal('0')
    order = Order.objects.create(user=user, idempotency_key=data['idempotency_key'], request_hash=digest,
        subtotal=subtotal, discount=discount, shipping=shipping, total=subtotal-discount+shipping,
        address=data['address'], currency=settings.SETTLEMENT_CURRENCY)
    for line in data['items']:
        product = products[line['productId']]
        OrderItem.objects.create(order=order, product=product, vendor_id=product.vendor_id, name=product.name,
            price=product.effective_price, quantity=line['quantity'], variant=line.get('variant', 'Natural'))
    for pk, quantity in counts.items():
        updated = Product.objects.filter(pk=pk, stock__gte=quantity).update(stock=F('stock')-quantity)
        if not updated:
            raise Conflict('Stock changed; please retry checkout.')
    from carts.models import CartItem
    CartItem.objects.filter(user=user).delete()
    notify(user, 'Order received', f'Order {order.id} is awaiting payment. Total {order.total} {order.currency}.', category='orders')
    return order

@transaction.atomic
def change_status(user, order_id, status):
    order = Order.objects.select_for_update().get(pk=order_id)
    items = list(order.items.select_related('vendor').all())
    if status == 'Cancelled':
        if not (is_admin(user) or (user.role == 'CUSTOMER' and order.user_id == user.id)):
            raise PermissionDenied()
        if order.status == 'Cancelled':
            return order
        if order.payment_status != 'PENDING' or any(i.fulfillment != 'Processing' for i in items):
            raise Conflict('Only unpaid, unshipped orders may be cancelled. Paid orders require refund assistance.')
        from payments.models import Payment
        if Payment.objects.filter(order=order).exclude(provider='mock').exclude(status__in=['FAILED','CANCELLED']).exists():
            raise Conflict('A provider payment is in progress. Reconcile it before cancellation to avoid releasing paid inventory.')
        for item in items:
            Product.objects.filter(pk=item.product_id).update(stock=F('stock')+item.quantity)
        order.status = 'Cancelled'
        order.items.update(fulfillment='Cancelled')
    else:
        if not (is_admin(user) or approved(user)):
            raise PermissionDenied()
        if order.payment_status != 'SUCCEEDED' or order.status == 'Cancelled':
            raise Conflict('Fulfillment requires confirmed payment.')
        scoped = items if is_admin(user) else [i for i in items if i.vendor.user_id == user.id]
        if not scoped:
            raise PermissionDenied()
        transitions = {'Processing':'Shipped', 'Shipped':'Delivered'}
        if any(transitions.get(i.fulfillment) != status for i in scoped):
            raise Conflict('Invalid fulfillment transition.')
        for item in scoped:
            item.fulfillment = status
            item.save(update_fields=['fulfillment'])
        states = list(order.items.values_list('fulfillment', flat=True))
        order.status = 'Delivered' if all(s == 'Delivered' for s in states) else 'Shipped' if all(s in ['Shipped','Delivered'] for s in states) else 'Processing'
    order.save()
    AuditLog.objects.create(actor=user, action='order.'+status.lower(), target=str(order.id))
    notify(order.user, 'Order status updated', f'Order {order.id}: {order.status}', category='orders')
    return order
