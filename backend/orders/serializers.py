from rest_framework import serializers
from .models import Order
from core.permissions import approved
from django.utils.crypto import salted_hmac

class OrderSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user_id', read_only=True)
    date = serializers.DateTimeField(source='created_at')
    items = serializers.SerializerMethodField()
    vendorStatuses = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()
    paymentId = serializers.UUIDField(source='payment.id',read_only=True,default=None)
    paymentProvider = serializers.CharField(source='payment.provider',read_only=True,default=None)
    paymentStatus = serializers.CharField(source='payment.status',read_only=True,default=None)
    customerKey = serializers.SerializerMethodField()
    class Meta:
        model = Order
        fields = ['id','userId','customerKey','date','status','payment_status','paymentId','paymentProvider','paymentStatus','items','total','subtotal','discount','shipping','currency','address','vendorStatuses']
    def get_customerKey(self, obj) -> str | None:
        user = self.context['request'].user
        if approved(user):
            return salted_hmac('vendor-customer-statistics', f'{user.vendor.id}:{obj.user_id}', algorithm='sha256').hexdigest()
        return None
    def scoped_items(self, obj):
        items = list(obj.items.all())
        user = self.context['request'].user
        return [i for i in items if i.vendor.user_id == user.id] if approved(user) else items
    def get_items(self, obj) -> list[dict]:
        return [{'id': str(i.id), 'productId': str(i.product_id), 'vendorId': str(i.vendor_id), 'name': i.name,
                 'price': str(i.price), 'quantity': i.quantity, 'variant': i.variant} for i in self.scoped_items(obj)]
    def get_total(self, obj) -> str:
        return str(sum(i.price*i.quantity for i in self.scoped_items(obj))) if approved(self.context['request'].user) else str(obj.total)
    def get_vendorStatuses(self, obj) -> dict:
        return {str(i.vendor_id): i.fulfillment for i in self.scoped_items(obj)}
    def get_address(self, obj) -> str:
        return ', '.join(str(obj.address.get(k,'')) for k in ['name','street','city','zip','country'])
    def to_representation(self, obj):
        data = super().to_representation(obj)
        if approved(self.context['request'].user):
            for key in ['userId','subtotal','discount','shipping','paymentId','paymentProvider','paymentStatus']:
                data.pop(key, None)
        return data
