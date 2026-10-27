from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers, viewsets
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from accounts.models import User
from accounts.serializers import RegistrationSerializer
from accounts.views import AuthThrottle, issue_token, email_delivery_mode
from core.permissions import is_admin, approved
from core.uploads import safe_image
from core.notifications import notify
from .models import Vendor
from .services import decide_vendor
from drf_spectacular.utils import extend_schema, extend_schema_view
from core.schema import MessageSerializer

class VendorApplicationInput(RegistrationSerializer):
    store_name = serializers.CharField()
    description = serializers.CharField()
    phone = serializers.CharField()
    address = serializers.CharField()
    logo = serializers.FileField()
    business_registration = serializers.CharField(required=False)

class VendorSerializer(serializers.ModelSerializer):
    active = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email', read_only=True)
    fullName = serializers.CharField(source='user.name', read_only=True)
    registeredAt = serializers.DateTimeField(source='created_at', read_only=True)
    class Meta:
        model = Vendor
        fields = ['id','name','description','phone','location','logo','business_registration','status','active','email','fullName','registeredAt','decision_reason']
        read_only_fields = ['status','decision_reason']
    def get_active(self, obj) -> bool:
        return obj.status == 'APPROVED' and obj.user.is_active
    def validate_logo(self, value):
        return safe_image(value)
    def to_representation(self, obj):
        data = super().to_representation(obj)
        user = self.context['request'].user
        if not is_admin(user) and obj.user_id != user.id:
            for key in ['email','fullName','phone','business_registration','decision_reason']:
                data.pop(key, None)
        return data

@method_decorator(csrf_protect, name='dispatch')
@extend_schema_view(post=extend_schema(request=VendorApplicationInput,responses={201:MessageSerializer},description='Public multipart application; CSRF required. Always creates a PENDING vendor.'))
class VendorRegistration(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]
    @transaction.atomic
    def post(self, request):
        class Application(RegistrationSerializer):
            store_name = serializers.CharField(min_length=2, max_length=150)
            description = serializers.CharField(min_length=20, max_length=5000)
            phone = serializers.CharField(min_length=7, max_length=40)
            address = serializers.CharField(min_length=8, max_length=300)
            logo = serializers.FileField()
            business_registration = serializers.CharField(max_length=200, required=False, allow_blank=True)
        serializer = Application(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        logo = safe_image(values['logo'])
        user = User.objects.create_user(email=values['email'], password=values['password'], name=values['name'], role='VENDOR')
        Vendor.objects.create(user=user, name=values['store_name'], description=values['description'], phone=values['phone'],
            location=values['address'], logo=logo, business_registration=values.get('business_registration',''))
        issue_token(user, 'verify')
        notify(user, 'Vendor application received', 'Your application is pending administrator approval. Verify your email to sign in.')
        for admin in User.objects.filter(role='ADMIN', is_staff=True, is_active=True):
            notify(admin, 'New vendor application', f'{user.name} applied for {values["store_name"]}. Review in the admin workspace.')
        return Response({'status': 'PENDING', 'message': 'Application received. Verify your email and await approval.', 'emailDelivery': email_delivery_mode()}, status=201)

class VendorViewSet(viewsets.ModelViewSet):
    serializer_class = VendorSerializer
    permission_classes = [AllowAny]
    http_method_names = ['get','patch','post','head','options']
    def get_queryset(self):
        qs = Vendor.objects.select_related('user')
        if is_admin(self.request.user):
            return qs.order_by('-created_at')
        if self.request.user.is_authenticated and hasattr(self.request.user, 'vendor'):
            from django.db.models import Q
            return qs.filter(Q(status='APPROVED', user__is_active=True)|Q(user=self.request.user)).order_by('name')
        return qs.filter(status='APPROVED', user__is_active=True).order_by('name')
    def create(self, request, *args, **kwargs):
        raise PermissionDenied('Use vendor registration; applications require review.')
    def perform_update(self, serializer):
        if not is_admin(self.request.user) and not (approved(self.request.user) and serializer.instance.user_id == self.request.user.id):
            raise PermissionDenied()
        serializer.save()
    @action(detail=True, methods=['post'])
    def decision(self, request, pk=None):
        if not is_admin(request.user) or not request.user.has_perm('vendors.approve_vendor'):
            raise PermissionDenied('Vendor approval permission required.')
        class Decision(serializers.Serializer):
            status = serializers.ChoiceField(choices=['APPROVED','REJECTED','SUSPENDED'])
            reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
        serializer = Decision(data=request.data)
        serializer.is_valid(raise_exception=True)
        vendor = self.get_object()
        vendor = decide_vendor(request.user, vendor.id, serializer.validated_data['status'], serializer.validated_data.get('reason',''))
        return Response(self.get_serializer(vendor).data)
