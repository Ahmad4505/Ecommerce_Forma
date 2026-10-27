from django.conf import settings
from django.db import models
from core.models import BaseModel

class Review(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey('products.Product', related_name='reviews', on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField()
    text = models.CharField(max_length=2000)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['user','product'], name='one_review_per_purchase'),
            models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name='review_rating_bounds')]
