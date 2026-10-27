from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from core.permissions import is_admin, approved
from .models import Order
from .serializers import OrderSerializer
from .services import checkout, change_status
from drf_spectacular.utils import extend_schema

class CheckoutInput(serializers.Serializer):
    class Line(serializers.Serializer):
        productId = serializers.UUIDField()
        quantity = serializers.IntegerField(min_value=1, max_value=100)
        variant = serializers.CharField(max_length=60, required=False)
    class Shipping(serializers.Serializer):
        name = serializers.CharField(min_length=2, max_length=150)
        street = serializers.CharField(min_length=4, max_length=250)
        city = serializers.CharField(min_length=2, max_length=100)
        zip = serializers.CharField(min_length=2, max_length=30)
        country = serializers.CharField(min_length=2, max_length=100)
    idempotency_key = serializers.UUIDField()
    items = Line(many=True, min_length=1, max_length=100)
    address = Shipping()
    code = serializers.CharField(max_length=40, required=False, allow_blank=True)

class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderSerializer
    def get_throttles(self):
        from core.throttles import CheckoutThrottle
        return [CheckoutThrottle()] if self.action=='create' else super().get_throttles()
    def get_queryset(self):
        if getattr(self,'swagger_fake_view',False):
            return Order.objects.none()
        qs = Order.objects.select_related('user').prefetch_related('items__vendor')
        if is_admin(self.request.user):
            return qs.order_by('-created_at')
        if approved(self.request.user):
            return qs.filter(items__vendor__user=self.request.user).distinct().order_by('-created_at')
        return qs.filter(user=self.request.user).order_by('-created_at')
    @extend_schema(request=CheckoutInput, responses={201:OrderSerializer}, description='Customer only. Server recomputes all amounts and reserves inventory atomically. Reuse idempotency_key when retrying the same payload.')
    def create(self, request):
        serializer = CheckoutInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = checkout(request.user, serializer.validated_data)
        return Response(self.get_serializer(order).data, status=201)
    @action(detail=True, methods=['post'])
    def status(self, request, pk=None):
        order = self.get_object()
        class StatusInput(serializers.Serializer):
            status = serializers.ChoiceField(choices=['Shipped','Delivered','Cancelled'])
        serializer = StatusInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = change_status(request.user, order.id, serializer.validated_data['status'])
        return Response(self.get_serializer(order).data)
