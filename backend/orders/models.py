from django.conf import settings
from django.db import models
from core.models import BaseModel

class Order(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    idempotency_key = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=20, default='Processing')
    payment_status = models.CharField(max_length=20, default='PENDING')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    address = models.JSONField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=['user','idempotency_key'], name='unique_customer_checkout')]

class OrderItem(BaseModel):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT)
    vendor = models.ForeignKey('vendors.Vendor', on_delete=models.PROTECT)
    name = models.CharField(max_length=150)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField()
    variant = models.CharField(max_length=60, default='Natural')
    fulfillment = models.CharField(max_length=20, default='Processing')
