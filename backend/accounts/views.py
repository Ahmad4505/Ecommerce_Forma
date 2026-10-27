import hashlib
import secrets
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.core.cache import cache
from rest_framework import serializers, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError, Throttled
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from .models import User, AccountToken, Address
from core.models import Notification
from .serializers import RegistrationSerializer, UserSerializer, AddressSerializer
from core.notifications import notify
from drf_spectacular.utils import extend_schema, extend_schema_view
from core.schema import AuthInput, SessionOutput, MessageSerializer

class AuthThrottle(AnonRateThrottle):
    scope = 'auth'
    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}

def issue_token(user, purpose):
    token = secrets.token_urlsafe(32)
    AccountToken.objects.filter(user=user, purpose=purpose, used_at__isnull=True).update(used_at=timezone.now())
    AccountToken.objects.create(user=user, purpose=purpose,
        digest=hashlib.sha256(token.encode()).hexdigest(), expires_at=timezone.now()+timedelta(hours=1))
    path = 'verify-email' if purpose == 'verify' else 'reset-password'
    subject = 'Verify your email' if purpose == 'verify' else 'Reset your password'
    Notification.objects.filter(recipient=user, subject=subject, sent_at__isnull=True, cancelled_at__isnull=True).update(cancelled_at=timezone.now())
    notify(user, subject, f'{settings.FRONTEND_URL}/{path}?token={token}', immediate=True)

def email_delivery_mode():
    backend = settings.MAILERS.get('default', {}).get('BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
    return 'console' if settings.DEBUG and backend == 'django.core.mail.backends.console.EmailBackend' else 'email'

@method_decorator(csrf_protect, name='dispatch')
@extend_schema_view(get=extend_schema(responses=SessionOutput), post=extend_schema(request=AuthInput, responses=MessageSerializer,
    description='Session authentication. Fetch csrf first and send X-CSRFToken on every POST, including login and logout. Register/verify-email/password-reset/password-reset-confirm use single-use email tokens.'))
class AuthView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]
    def get_throttles(self):
        # Session hydration and CSRF retrieval are routine browser reads. They
        # must not consume the stricter login/registration/reset attempt budget.
        if self.request.method in {'GET','HEAD','OPTIONS'}:
            return [AnonRateThrottle(), UserRateThrottle()]
        return super().get_throttles()
    def get(self, request, action):
        if action == 'csrf':
            return Response({'csrfToken': get_token(request)})
        if action == 'session':
            return Response({'user': UserSerializer(request.user).data if request.user.is_authenticated else None})
        return Response(status=405)

    @transaction.atomic
    def post(self, request, action):
        if action == 'register':
            serializer = RegistrationSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = User.objects.create_user(**serializer.validated_data)
            issue_token(user, 'verify')
            return Response({'message': 'Check your email to activate your account.', 'emailDelivery': email_delivery_mode()}, status=201)
        if action == 'login':
            email = str(request.data.get('email', '')).strip().lower()[:254]
            key = 'login:' + hashlib.sha256(email.encode()).hexdigest()
            if cache.get(key, 0) >= 10:
                raise Throttled(detail='Please try again later.')
            password = request.data.get('password')
            if not isinstance(password,str) or len(password)>128:
                raise ValidationError('Unable to sign in with these details.')
            user = authenticate(request, email=email, password=password)
            if not user or not user.email_verified:
                if not cache.add(key,1,900):
                    cache.incr(key)
                raise ValidationError('Unable to sign in with these details.')
            cache.delete(key)
            login(request, user)
            return Response(UserSerializer(user).data)
        if action == 'logout':
            logout(request)
            return Response(status=204)
        if action == 'password-reset':
            user = User.objects.filter(email__iexact=str(request.data.get('email', ''))[:254], is_active=True).first()
            if user:
                issue_token(user, 'reset')
            return Response({'message': 'If the account exists, recovery instructions will be sent.', 'emailDelivery': email_delivery_mode()})
        if action == 'resend-verification':
            class Input(serializers.Serializer):
                email = serializers.EmailField()
            serializer = Input(data=request.data)
            serializer.is_valid(raise_exception=True)
            email = serializer.validated_data['email'].lower()
            key = 'verify-resend:' + hashlib.sha256(email.encode()).hexdigest()
            if cache.add(key, True, 60):
                user = User.objects.filter(email__iexact=email, email_verified=False, is_active=True).first()
                if user:
                    issue_token(user, 'verify')
            return Response({'message': 'If your account is awaiting verification, instructions will be sent.', 'emailDelivery': email_delivery_mode()})
        if action in {'verify-email','password-reset-confirm'}:
            purpose = 'verify' if action == 'verify-email' else 'reset'
            digest = hashlib.sha256(str(request.data.get('token','')).encode()).hexdigest()
            token = AccountToken.objects.select_for_update().filter(digest=digest, purpose=purpose, used_at__isnull=True, expires_at__gt=timezone.now()).first()
            if not token:
                raise ValidationError('The link is invalid or has expired.')
            if purpose == 'verify':
                token.user.email_verified = True
            else:
                password = serializers.CharField(max_length=128, trim_whitespace=False).run_validation(request.data.get('password', ''))
                validate_password(password, token.user)
                token.user.set_password(password)
            token.user.save()
            token.used_at = timezone.now()
            token.save()
            return Response({'message': 'Account updated. You can sign in.'})
        return Response(status=404)

@extend_schema_view(patch=extend_schema(request=AuthInput,responses=UserSerializer))
class ProfileView(APIView):
    def patch(self, request):
        class ProfileInput(serializers.Serializer):
            name = serializers.CharField(min_length=2, max_length=150)
            email = serializers.EmailField()
        serializer = ProfileInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data['email'].lower() != request.user.email.lower():
            raise ValidationError('Email changes require administrator assistance.')
        request.user.name = data['name']
        request.user.save(update_fields=['name'])
        return Response(UserSerializer(request.user).data)

class PasswordChangeView(APIView):
    throttle_classes = [AuthThrottle]

    class PasswordChangeInput(serializers.Serializer):
        current_password = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)
        password = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)

    @extend_schema(request=PasswordChangeInput, responses=MessageSerializer)
    def post(self, request):
        serializer = self.PasswordChangeInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        if not request.user.check_password(values['current_password']):
            raise ValidationError({'current_password': 'Your current password is incorrect.'})
        validate_password(values['password'], request.user)
        request.user.set_password(values['password'])
        request.user.save(update_fields=['password'])
        update_session_auth_hash(request, request.user)
        return Response({'message': 'Your password has been changed.'})

class PreferencesView(APIView):
    class PreferencesInput(serializers.Serializer):
        newsletter_notifications = serializers.BooleanField()
        order_notifications = serializers.BooleanField()

    @extend_schema(request=PreferencesInput, responses=UserSerializer)
    @transaction.atomic
    def patch(self, request):
        serializer = self.PreferencesInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        for key, value in serializer.validated_data.items():
            setattr(request.user, key, value)
        request.user.save(update_fields=list(serializer.validated_data))
        from core.models import NewsletterSubscriber
        if request.user.newsletter_notifications:
            NewsletterSubscriber.objects.get_or_create(email=request.user.email.lower())
        else:
            NewsletterSubscriber.objects.filter(email__iexact=request.user.email).delete()
        return Response(UserSerializer(request.user).data)

class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Address.objects.none()
        return Address.objects.filter(user=self.request.user).order_by('created_at')
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
