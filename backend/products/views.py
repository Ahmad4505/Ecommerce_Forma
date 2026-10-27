from django.db.models import Q
from django.db import transaction
from rest_framework import viewsets, serializers
from rest_framework.permissions import AllowAny
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from core.permissions import is_admin, approved
from core.uploads import safe_image
from .models import Product, ProductImage
from .serializers import ProductSerializer
from core.throttles import UploadThrottle

def public_products():
    return Product.objects.filter(status='ACTIVE', vendor__status='APPROVED', vendor__user__is_active=True)

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    search_fields = ['name','description','sku']
    filterset_fields = ['category__name','vendor','featured','status']
    ordering_fields = ['price','created_at','name']
    def get_queryset(self):
        qs = Product.objects.all() if is_admin(self.request.user) else Product.objects.filter(Q(status='ACTIVE',vendor__status='APPROVED',vendor__user__is_active=True)|Q(vendor__user=self.request.user)) if approved(self.request.user) else public_products()
        return qs.select_related('category','vendor__user').prefetch_related('pictures','reviews__user').order_by('-created_at')
    def check_manager(self, product=None):
        if is_admin(self.request.user):
            return
        if not approved(self.request.user) or (product and product.vendor.user_id != self.request.user.id):
            raise PermissionDenied('Only approved store owners may manage their products.')
    def perform_create(self, serializer):
        self.check_manager()
        if not is_admin(self.request.user) and serializer.validated_data['vendor'].user_id != self.request.user.id:
            raise PermissionDenied()
        if not is_admin(self.request.user) and serializer.validated_data.get('featured', False):
            raise PermissionDenied('Only admins may feature products.')
        serializer.save()
    def perform_update(self, serializer):
        self.check_manager(serializer.instance)
        if 'vendor' in serializer.validated_data and serializer.validated_data['vendor'] != serializer.instance.vendor:
            raise PermissionDenied('Product ownership cannot be transferred.')
        if 'featured' in self.request.data and not is_admin(self.request.user) and serializer.validated_data['featured'] != serializer.instance.featured:
            raise PermissionDenied('Only admins may feature products.')
        serializer.save()
    def perform_destroy(self, instance):
        self.check_manager(instance)
        instance.status = 'ARCHIVED'
        instance.save(update_fields=['status'])
    @action(detail=True, methods=['post'],throttle_classes=[UploadThrottle])
    @transaction.atomic
    def images(self, request, pk=None):
        product = self.get_object()
        self.check_manager(product)
        files = request.FILES.getlist('images')
        replace = serializers.BooleanField().run_validation(request.data.get('replace', False))
        if not files or len(files) + (0 if replace else product.pictures.count()) > 8:
            raise ValidationError('Provide images, maximum eight per product.')
        validated = [safe_image(file) for file in files]
        if replace:
            product.pictures.all().delete()
        for image in validated:
            ProductImage.objects.create(product=product, image=image)
        return Response(self.get_serializer(product).data)
    @action(detail=True, methods=['get'])
    def related(self, request, pk=None):
        product = self.get_object()
        return Response(self.get_serializer(public_products().filter(category=product.category).exclude(pk=pk)[:4], many=True).data)
