from django.db import models
from django.db.models import Q, F
from core.models import BaseModel

class Product(BaseModel):
    vendor = models.ForeignKey('vendors.Vendor', on_delete=models.PROTECT, related_name='products')
    category = models.ForeignKey('categories.Category', on_delete=models.PROTECT)
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    discount_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    sku = models.CharField(max_length=100, unique=True)
    stock = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=[('ACTIVE','Active'),('DRAFT','Draft'),('ARCHIVED','Archived')], default='ACTIVE')
    featured = models.BooleanField(default=False)
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(price__gt=0), name='positive_product_price'),
            models.CheckConstraint(condition=Q(discount_price__isnull=True) | (Q(discount_price__gt=0) & Q(discount_price__lt=F('price'))), name='valid_product_discount')]
        indexes = [models.Index(fields=['status', 'category'])]
    @property
    def effective_price(self):
        return self.discount_price if self.discount_price is not None else self.price

class ProductImage(BaseModel):
    product = models.ForeignKey(Product, related_name='pictures', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='products/', blank=True)
    source_url = models.URLField(blank=True)
    attribution = models.CharField(max_length=500, blank=True)
