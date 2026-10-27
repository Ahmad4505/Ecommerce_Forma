from rest_framework import serializers
from .models import Product, ProductImage
from categories.models import Category
from vendors.models import Vendor
from reviews.models import Review

class ReviewSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='user.name', read_only=True)
    userId = serializers.UUIDField(source='user_id', read_only=True)
    productId = serializers.PrimaryKeyRelatedField(source='product', queryset=Product.objects.all())
    date = serializers.DateTimeField(source='created_at', read_only=True)
    rating = serializers.IntegerField(min_value=1, max_value=5)
    text = serializers.CharField(min_length=8, max_length=2000)
    class Meta:
        model = Review
        fields = ['id','name','userId','productId','text','rating','date']

class ProductSerializer(serializers.ModelSerializer):
    vendorId = serializers.PrimaryKeyRelatedField(source='vendor', queryset=Vendor.objects.filter(status='APPROVED'))
    category = serializers.SlugRelatedField(slug_field='name', queryset=Category.objects.all())
    discountPrice = serializers.DecimalField(source='discount_price', max_digits=12, decimal_places=2, allow_null=True, required=False)
    images = serializers.SerializerMethodField()
    reviews = ReviewSerializer(many=True, read_only=True)
    rating = serializers.SerializerMethodField()
    available = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    class Meta:
        model = Product
        fields = ['id','vendorId','name','slug','description','category','price','discountPrice','sku','stock','status','featured','images','reviews','rating','available','createdAt']
    def get_images(self, obj) -> list[str]:
        request = self.context.get('request')
        return [request.build_absolute_uri(i.image.url) if i.image and request else i.image.url if i.image else i.source_url for i in obj.pictures.all()] or ['/fallback.svg']
    def get_rating(self, obj) -> float:
        reviews = list(obj.reviews.all())
        return round(sum(r.rating for r in reviews)/len(reviews), 1) if reviews else 0
    def get_available(self, obj) -> bool:
        return obj.status == 'ACTIVE' and obj.vendor.status == 'APPROVED' and obj.vendor.user.is_active
    def validate(self, data):
        price = data.get('price', self.instance.price if self.instance else 0)
        discount = data.get('discount_price', self.instance.discount_price if self.instance else None)
        if price <= 0 or (discount is not None and not 0 < discount < price):
            raise serializers.ValidationError('Price must be positive and discount lower than price.')
        return data
