import uuid
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower
from core.models import BaseModel


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra):
        extra.update(is_staff=True, is_superuser=True, role='ADMIN', email_verified=True)
        return self.create_user(email, password, **extra)


class User(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = 'CUSTOMER'
        VENDOR = 'VENDOR'
        ADMIN = 'ADMIN'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.CUSTOMER)
    email_verified = models.BooleanField(default=False)
    newsletter_notifications = models.BooleanField(default=True)
    order_notifications = models.BooleanField(default=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']
    objects = UserManager()
    class Meta:
        constraints = [models.UniqueConstraint(Lower('email'), name='user_email_case_unique')]


class Address(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    label = models.CharField(max_length=80)
    name = models.CharField(max_length=150)
    street = models.CharField(max_length=250)
    city = models.CharField(max_length=100)
    zip = models.CharField(max_length=30)
    country = models.CharField(max_length=100)


class AccountToken(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    digest = models.CharField(max_length=64, unique=True)
    purpose = models.CharField(max_length=20)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True)
