from django.conf import settings
from django.db import models
from core.models import BaseModel


class Vendor(BaseModel):
    class Status(models.TextChoices):
        PENDING = 'PENDING'
        APPROVED = 'APPROVED'
        REJECTED = 'REJECTED'
        SUSPENDED = 'SUSPENDED'
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='vendor')
    name = models.CharField(max_length=150)
    description = models.TextField()
    phone = models.CharField(max_length=40)
    location = models.CharField(max_length=300)
    logo = models.ImageField(upload_to='vendors/', blank=True)
    business_registration = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    decision_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='vendor_decisions')
    decision_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.CharField(max_length=500, blank=True)
    class Meta:
        permissions = [('approve_vendor', 'Can approve, reject or suspend vendor applications')]
