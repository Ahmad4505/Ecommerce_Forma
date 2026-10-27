from rest_framework import serializers
from drf_spectacular.utils import inline_serializer

class MessageSerializer(serializers.Serializer):
    message = serializers.CharField()

class AuthInput(serializers.Serializer):
    email = serializers.EmailField(required=False)
    name = serializers.CharField(required=False)
    password = serializers.CharField(required=False, write_only=True)
    token = serializers.CharField(required=False, write_only=True)

class SessionOutput(serializers.Serializer):
    user = serializers.DictField(allow_null=True, required=False)
    csrfToken = serializers.CharField(required=False)

class SettingsInput(serializers.Serializer):
    name = serializers.CharField()
    shipping = serializers.DecimalField(max_digits=10,decimal_places=2)
    freeShipping = serializers.DecimalField(max_digits=10,decimal_places=2)
    newsletter = serializers.BooleanField()

class CartLineSerializer(serializers.Serializer):
    productId = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1,max_value=100)
    variant = serializers.CharField(max_length=60)

class ProductIdSerializer(serializers.Serializer):
    productId = serializers.UUIDField()

class BootstrapSerializer(serializers.Serializer):
    products = serializers.ListField(child=serializers.DictField())
    vendors = serializers.ListField(child=serializers.DictField())
    categories = serializers.ListField(child=serializers.CharField())
    orders = serializers.ListField(child=serializers.DictField())
    addresses = serializers.ListField(child=serializers.DictField())
    settings = SettingsInput()

class AnalyticsSerializer(serializers.Serializer):
    units = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=14,decimal_places=2)

class AuditSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    actor_id = serializers.UUIDField(allow_null=True)
    action = serializers.CharField()
    target = serializers.CharField()
    details = serializers.DictField()
    created_at = serializers.DateTimeField()
