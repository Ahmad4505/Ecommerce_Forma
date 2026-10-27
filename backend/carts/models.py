from django.conf import settings
from django.db import models
from core.models import BaseModel

class CartItem(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    variant = models.CharField(max_length=60, default='Natural')
    class Meta:
        constraints = [models.UniqueConstraint(fields=['user','product','variant'], name='unique_cart_variant'),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name='cart_quantity_positive')]

class WishlistItem(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['user','product'], name='unique_wishlist_product')]
