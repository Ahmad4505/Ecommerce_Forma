from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from .models import User, Address

class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    vendorId = serializers.SerializerMethodField()
    vendorStatus = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = ['id','name','email','role','vendorId','vendorStatus','email_verified','is_active','newsletter_notifications','order_notifications']
    def get_role(self, obj) -> str:
        return obj.role.lower()
    def get_vendorId(self, obj) -> str | None:
        return str(obj.vendor.id) if hasattr(obj, 'vendor') else None
    def get_vendorStatus(self, obj) -> str | None:
        return obj.vendor.status if hasattr(obj, 'vendor') else None

class RegistrationSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=2, max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)
    def validate(self, data):
        validate_password(data['password'], User(email=data['email'], name=data['name']))
        if User.objects.filter(email__iexact=data['email']).exists():
            raise serializers.ValidationError('Unable to register with these details.')
        return data

class AddressSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user_id', read_only=True)
    class Meta:
        model = Address
        fields = ['id','userId','label','name','street','city','zip','country']
