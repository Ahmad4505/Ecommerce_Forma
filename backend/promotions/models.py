from django.db import models
from core.models import BaseModel

class Promotion(BaseModel):
    code = models.CharField(max_length=40, unique=True)
    percent = models.PositiveSmallIntegerField()
    active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(percent__gt=0, percent__lte=100), name='coupon_percent_bounds')]

class Banner(BaseModel):
    title = models.CharField(max_length=150)
    subtitle = models.CharField(max_length=300)
    active = models.BooleanField(default=True)

class ProductReport(BaseModel):
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    reason = models.CharField(max_length=1000)
    status = models.CharField(max_length=20, default='Open')
