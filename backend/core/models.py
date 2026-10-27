import uuid
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True


class AuditLog(BaseModel):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=100)
    target = models.CharField(max_length=100)
    details = models.JSONField(default=dict)


class PlatformSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    name = models.CharField(max_length=100, default='Forma')
    shipping = models.DecimalField(max_digits=10, decimal_places=2, default=8,validators=[MinValueValidator(0)])
    free_shipping = models.DecimalField(max_digits=10, decimal_places=2, default=150,validators=[MinValueValidator(0)])
    newsletter = models.BooleanField(default=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(shipping__gte=0,free_shipping__gte=0),name='nonnegative_shipping')]


class Notification(BaseModel):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    sent_at = models.DateTimeField(null=True)
    cancelled_at = models.DateTimeField(null=True)

class ContactMessage(BaseModel):
    name = models.CharField(max_length=150)
    email = models.EmailField()
    topic = models.CharField(max_length=100)
    message = models.TextField(max_length=5000)

class NewsletterSubscriber(BaseModel):
    email = models.EmailField(unique=True)
