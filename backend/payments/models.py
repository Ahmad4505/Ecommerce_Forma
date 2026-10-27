from django.db import models
from core.models import BaseModel

class Payment(BaseModel):
    order = models.OneToOneField('orders.Order', on_delete=models.PROTECT, related_name='payment')
    provider = models.CharField(max_length=20)
    reference = models.CharField(max_length=200, blank=True, db_index=True)
    capture_id = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, default='PENDING', choices=[(s,s) for s in ['PENDING','REQUIRES_ACTION','PROCESSING','SUCCEEDED','FAILED','CANCELLED','REFUNDED']])
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    refunded_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3)
    checkout_url = models.URLField(max_length=2000, blank=True)

class WebhookEvent(BaseModel):
    provider = models.CharField(max_length=20)
    event_id = models.CharField(max_length=200)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['provider','event_id'], name='unique_provider_event')]

class Refund(BaseModel):
    payment = models.ForeignKey(Payment,on_delete=models.PROTECT,related_name='refunds')
    idempotency_key = models.UUIDField(unique=True)
    amount = models.DecimalField(max_digits=12,decimal_places=2)
    status = models.CharField(max_length=20,default='PENDING')
    reference = models.CharField(max_length=200,blank=True)
    reason = models.CharField(max_length=500)
    actor = models.ForeignKey('accounts.User',on_delete=models.PROTECT)
