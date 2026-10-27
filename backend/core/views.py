from django.db import transaction
from django.db.models import Sum
from django.utils.text import slugify
from rest_framework import serializers, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied, ValidationError
from accounts.models import User, Address
from accounts.serializers import UserSerializer, AddressSerializer
from vendors.models import Vendor
from vendors.views import VendorSerializer
from products.models import Product
from products.views import public_products
from products.serializers import ProductSerializer, ReviewSerializer
from categories.models import Category
from orders.models import Order, OrderItem
from orders.serializers import OrderSerializer
from carts.models import CartItem, WishlistItem
from promotions.models import Promotion, Banner, ProductReport
from reviews.models import Review
from .models import PlatformSettings, AuditLog, ContactMessage
from .permissions import is_admin, approved, PlatformAdmin
from payments.adapters import available_providers
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.throttling import AnonRateThrottle
from drf_spectacular.utils import extend_schema, extend_schema_view
from .schema import (CartLineSerializer, ProductIdSerializer, MessageSerializer,
    SettingsInput, BootstrapSerializer, AnalyticsSerializer, AuditSerializer)

class PublicFormThrottle(AnonRateThrottle):
    scope = 'public_forms'
    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}

@method_decorator(csrf_protect, name='dispatch')
class ContactView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PublicFormThrottle]

    class ContactInput(serializers.ModelSerializer):
        name = serializers.CharField(min_length=2, max_length=150)
        message = serializers.CharField(min_length=10, max_length=5000)
        class Meta:
            model = ContactMessage
            fields = ['name','email','topic','message']

    @extend_schema(request=ContactInput, responses={201: MessageSerializer})
    def post(self, request):
        serializer = self.ContactInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'message': 'Your message has been saved for our team.'}, status=201)

@method_decorator(csrf_protect, name='dispatch')
class NewsletterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PublicFormThrottle]

    class NewsletterInput(serializers.Serializer):
        email = serializers.EmailField()

    @extend_schema(request=NewsletterInput, responses={201: MessageSerializer})
    def post(self, request):
        from .models import NewsletterSubscriber
        serializer = self.NewsletterInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        config, _ = PlatformSettings.objects.get_or_create(pk=1)
        if not config.newsletter:
            raise ValidationError('Newsletter subscriptions are currently unavailable.')
        NewsletterSubscriber.objects.get_or_create(email=serializer.validated_data['email'].lower())
        return Response({'message': 'Your subscription has been saved.'}, status=201)

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id','name','slug']
        read_only_fields = ['slug']

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by('name')
    serializer_class = CategorySerializer
    def get_permissions(self):
        return [AllowAny()] if self.request.method in ['GET','HEAD','OPTIONS'] else [PlatformAdmin()]
    def perform_create(self, serializer):
        serializer.save(slug=slugify(serializer.validated_data['name']))

class PromotionSerializer(serializers.ModelSerializer):
    percent = serializers.IntegerField(min_value=1,max_value=100)
    class Meta:
        model = Promotion
        fields = ['id','code','percent','active','starts_at','ends_at']

class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = ['id','title','subtitle','active']

class ReportSerializer(serializers.ModelSerializer):
    productId = serializers.PrimaryKeyRelatedField(source='product', queryset=Product.objects.all())
    class Meta:
        model = ProductReport
        fields = ['id','productId','reason','status']

class AdminRecords(viewsets.ModelViewSet):
    permission_classes = [PlatformAdmin]
    def perform_create(self, serializer):
        instance = serializer.save()
        AuditLog.objects.create(actor=self.request.user, action='admin.create',target=str(instance.pk))
    def perform_update(self, serializer):
        instance = serializer.save()
        AuditLog.objects.create(actor=self.request.user, action='admin.update',target=str(instance.pk))

class PromotionViewSet(AdminRecords):
    queryset = Promotion.objects.all().order_by('code')
    serializer_class = PromotionSerializer
class BannerViewSet(AdminRecords):
    queryset = Banner.objects.all().order_by('created_at')
    serializer_class = BannerSerializer
class ReportViewSet(AdminRecords):
    queryset = ProductReport.objects.all().order_by('created_at')
    serializer_class = ReportSerializer

class CustomerSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    def get_role(self, obj) -> str:
        return obj.role.lower()
    class Meta:
        model = User
        fields = ['id','name','email','is_active','role']
        read_only_fields = ['email','role']
class CustomerViewSet(AdminRecords):
    queryset = User.objects.filter(role='CUSTOMER').order_by('date_joined')
    serializer_class = CustomerSerializer
    http_method_names = ['get','patch','head','options']

class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    http_method_names = ['get','post','head','options']
    def get_queryset(self):
        if getattr(self,'swagger_fake_view',False):
            return Review.objects.none()
        if is_admin(self.request.user):
            return Review.objects.all().select_related('user').order_by('-created_at')
        return Review.objects.filter(user=self.request.user).select_related('user').order_by('-created_at')
    def perform_create(self, serializer):
        user = self.request.user
        product = serializer.validated_data['product']
        if user.role != 'CUSTOMER' or not OrderItem.objects.filter(order__user=user, product=product, fulfillment='Delivered',order__payment_status='SUCCEEDED').exists():
            raise PermissionDenied('Only delivered purchases may be reviewed.')
        if Review.objects.filter(user=user,product=product).exists():
            raise ValidationError('You already reviewed this product.')
        serializer.save(user=user)

@extend_schema_view(get=extend_schema(responses=CartLineSerializer(many=True)),put=extend_schema(request=CartLineSerializer(many=True),responses=CartLineSerializer(many=True)))
class CartView(APIView):
    def get(self, request):
        return Response([{'productId':str(i.product_id),'quantity':i.quantity,'variant':i.variant} for i in CartItem.objects.filter(user=request.user)])
    @transaction.atomic
    def put(self, request):
        class Line(serializers.Serializer):
            productId = serializers.UUIDField()
            quantity = serializers.IntegerField(min_value=1,max_value=100)
            variant = serializers.CharField(max_length=60,default='Natural')
        serializer = Line(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        if len(serializer.validated_data)>100:
            raise ValidationError('Maximum 100 cart lines.')
        User.objects.select_for_update().get(pk=request.user.pk)
        counts, keys = {}, set()
        for line in serializer.validated_data:
            key = (line['productId'],line['variant'])
            if key in keys:
                raise ValidationError('Duplicate cart line.')
            keys.add(key)
            counts[key[0]] = counts.get(key[0],0)+line['quantity']
        products = {p.pk:p for p in public_products().filter(pk__in=counts)}
        if any(pk not in products or products[pk].stock < count for pk,count in counts.items()):
            raise ValidationError('Stock is unavailable.')
        CartItem.objects.filter(user=request.user).delete()
        CartItem.objects.bulk_create([CartItem(user=request.user,product_id=i['productId'],quantity=i['quantity'],variant=i['variant']) for i in serializer.validated_data])
        return self.get(request)

@extend_schema_view(get=extend_schema(responses={'200':{'type':'array','items':{'type':'string','format':'uuid'}}}),post=extend_schema(request=ProductIdSerializer,responses={'200':{'type':'array','items':{'type':'string','format':'uuid'}}}))
class WishlistView(APIView):
    def get(self, request):
        return Response([str(pk) for pk in WishlistItem.objects.filter(user=request.user).values_list('product_id',flat=True)])
    def post(self, request):
        class Input(serializers.Serializer):
            productId = serializers.PrimaryKeyRelatedField(queryset=public_products())
        serializer = Input(data=request.data)
        serializer.is_valid(raise_exception=True)
        item, created = WishlistItem.objects.get_or_create(user=request.user,product=serializer.validated_data['productId'])
        if not created:
            item.delete()
        return self.get(request)

@extend_schema_view(patch=extend_schema(request=SettingsInput,responses=MessageSerializer))
class SettingsView(APIView):
    permission_classes = [PlatformAdmin]
    def patch(self, request):
        class Input(serializers.Serializer):
            name = serializers.CharField(max_length=100)
            shipping = serializers.DecimalField(max_digits=10,decimal_places=2,min_value=0)
            freeShipping = serializers.DecimalField(max_digits=10,decimal_places=2,min_value=0)
            newsletter = serializers.BooleanField()
        serializer = Input(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        config,_ = PlatformSettings.objects.get_or_create(pk=1)
        config.name,config.shipping,config.free_shipping,config.newsletter = data['name'],data['shipping'],data['freeShipping'],data['newsletter']
        config.save()
        AuditLog.objects.create(actor=request.user,action='platform.settings',target='1')
        return Response({'saved':True})

@extend_schema_view(get=extend_schema(responses=BootstrapSerializer))
class BootstrapView(APIView):
    """Bounded compatibility projection for existing frontend view models.

    Catalog pagination remains available through /products/. Private records are
    scoped server-side and never accepted back as database snapshots.
    """
    permission_classes = [AllowAny]
    def get(self, request):
        user = request.user
        products = public_products()
        vendors = Vendor.objects.filter(status='APPROVED',user__is_active=True)
        orders,addresses,users = Order.objects.none(), Address.objects.none(),User.objects.none()
        if user.is_authenticated:
            orders = Order.objects.filter(user=user)
            addresses = Address.objects.filter(user=user)
            if approved(user):
                products = (products | Product.objects.filter(vendor__user=user)).distinct()
                orders = Order.objects.filter(items__vendor__user=user).distinct()
            elif is_admin(user):
                products,vendors,orders,users = Product.objects.all(),Vendor.objects.all(),Order.objects.all(),User.objects.all()
            elif user.role == 'VENDOR':
                vendors = (vendors | Vendor.objects.filter(user=user)).distinct()
        config,_ = PlatformSettings.objects.get_or_create(pk=1)
        context = {'request':request}
        return Response({
            'paymentProviders': available_providers(),
            'products':ProductSerializer(products.select_related('category','vendor__user').prefetch_related('pictures','reviews__user').order_by('created_at')[:100],many=True,context=context).data,
            'vendors':VendorSerializer(vendors.select_related('user').order_by('created_at')[:100],many=True,context=context).data,
            'categories':list(Category.objects.order_by('name').values_list('name',flat=True)[:100]),
            'categoryRecords':CategorySerializer(Category.objects.order_by('name')[:100],many=True).data,
            'orders':OrderSerializer(orders.prefetch_related('items__vendor').order_by('-created_at')[:100],many=True,context=context).data,
            'users':UserSerializer(users.select_related('vendor')[:100],many=True).data,
            'addresses':AddressSerializer(addresses[:100],many=True).data,
            'promotions':PromotionSerializer(Promotion.objects.filter(active=True)[:100] if not is_admin(user) else Promotion.objects.all()[:100],many=True).data,
            'banners':BannerSerializer((Banner.objects.all() if is_admin(user) else Banner.objects.filter(active=True))[:100],many=True).data,
            'reports':ReportSerializer(ProductReport.objects.all()[:100],many=True).data if is_admin(user) else [],
            'settings':{'name':config.name,'shipping':str(config.shipping),'freeShipping':str(config.free_shipping),'newsletter':config.newsletter}})

@extend_schema_view(get=extend_schema(responses=AnalyticsSerializer))
class AnalyticsView(APIView):
    def get(self, request):
        if not (is_admin(request.user) or approved(request.user)):
            raise PermissionDenied()
        items = OrderItem.objects.filter(order__payment_status='SUCCEEDED').exclude(fulfillment='Cancelled')
        if not is_admin(request.user):
            items = items.filter(vendor__user=request.user)
        from django.db.models import F
        return Response({'units':items.aggregate(value=Sum('quantity'))['value'] or 0,
            'revenue':items.aggregate(value=Sum(F('price')*F('quantity')))['value'] or 0})

@extend_schema_view(get=extend_schema(responses=AuditSerializer(many=True)))
class AuditView(APIView):
    permission_classes = [PlatformAdmin]
    def get(self, request):
        return Response(list(AuditLog.objects.order_by('-created_at').values('id','actor_id','action','target','details','created_at')[:100]))
