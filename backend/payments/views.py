from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError
from .models import Payment, WebhookEvent
from .services import initiate, verify
from .adapters import adapter
from orders.models import Order
from drf_spectacular.utils import extend_schema, extend_schema_view
from core.schema import MessageSerializer
from rest_framework.generics import ListAPIView
from core.permissions import PlatformAdmin

class PaymentInput(serializers.Serializer):
    order_id = serializers.UUIDField(required=False)
    provider = serializers.ChoiceField(choices=['mock','paypal','checkout','hyperpay'],required=False)
    mock_outcome = serializers.ChoiceField(choices=['SUCCEEDED','FAILED','CANCELLED'],required=False)

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id','order_id','provider','status','amount','currency','checkout_url','reference']
        read_only_fields = fields

class AdminPaymentList(ListAPIView):
    permission_classes = [PlatformAdmin]
    serializer_class = PaymentSerializer
    queryset = Payment.objects.select_related('order').order_by('-created_at')

@extend_schema_view(get=extend_schema(responses=PaymentSerializer),post=extend_schema(request=PaymentInput,responses=PaymentSerializer,
    description='Owner only. Initiate a hosted sandbox payment or verify via server API. Redirects do not change payment status. Mock outcomes are allowed only in explicitly enabled local DEBUG mode.'))
class PaymentView(APIView):
    from core.throttles import PaymentThrottle
    throttle_classes = [PaymentThrottle]
    def get(self, request, pk=None):
        if pk is None:
            return Response(status=405)
        payment = get_object_or_404(Payment, pk=pk, order__user=request.user)
        return Response(PaymentSerializer(payment).data)
    def post(self, request, pk=None):
        if pk:
            payment = get_object_or_404(Payment, pk=pk, order__user=request.user)
            payment = verify(payment.id, request.data.get('mock_outcome'))
        else:
            class Input(serializers.Serializer):
                order_id = serializers.UUIDField()
                provider = serializers.ChoiceField(choices=['mock','paypal','checkout','hyperpay'])
            serializer = Input(data=request.data)
            serializer.is_valid(raise_exception=True)
            get_object_or_404(Order, pk=serializer.validated_data['order_id'], user=request.user)
            payment = initiate(request.user, **serializer.validated_data)
        return Response(PaymentSerializer(payment).data)

@extend_schema_view(post=extend_schema(request={'application/json':{'type':'object'}},responses=MessageSerializer,description='Provider-authenticated callback. CSRF exempt; provider signature verification is mandatory. Duplicate event IDs are ignored.'))
class WebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    @transaction.atomic
    def post(self, request, provider):
        # Read body before DRF JSON parser for byte-exact HMAC.
        body = request.body
        result = adapter(provider).webhook(request)
        event_id, reference = result[:2]
        if not event_id or not reference:
            raise ValidationError('Missing event reference.')
        _, created = WebhookEvent.objects.get_or_create(provider=provider, event_id=event_id)
        if not created:
            return Response({'received':True})
        if provider=='checkout':
            import uuid
            try:
                uuid.UUID(reference)
            except (ValueError,TypeError,AttributeError):
                raise ValidationError('Invalid payment reference.')
        payment = Payment.objects.filter(provider=provider, **({'id':reference} if len(result)>2 else {'reference':reference})).first()
        if payment:
            verify(payment.id,gateway_id=result[2] if len(result)>2 else None)
        else:
            # Retry later if a valid notification races payment transaction commit.
            from .adapters import ProviderUnavailable
            raise ProviderUnavailable('Payment reference is not available yet; retry this notification.')
        return Response({'received':True})

class RefundView(APIView):
    from core.permissions import PlatformAdmin
    permission_classes = [PlatformAdmin]
    @extend_schema(request=MessageSerializer,responses=MessageSerializer,description='Admin only. Submit amount, reason and unique idempotency_key. Pending provider acknowledgements are never represented as completed refunds.')
    def post(self,request,pk):
        from .services import refund_payment
        class Input(serializers.Serializer):
            from decimal import Decimal
            amount=serializers.DecimalField(max_digits=12,decimal_places=2,min_value=Decimal('0.01'))
            idempotency_key=serializers.UUIDField()
            reason=serializers.CharField(min_length=3,max_length=500)
        serializer=Input(data=request.data)
        serializer.is_valid(raise_exception=True)
        get_object_or_404(Payment,pk=pk)
        refund=refund_payment(request.user,pk,**serializer.validated_data)
        return Response({'id':str(refund.id),'amount':str(refund.amount),'status':refund.status})
