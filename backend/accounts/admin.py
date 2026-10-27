from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Address

@admin.register(User)
class AccountAdmin(UserAdmin):
    ordering = ['email']
    list_display = ['email','name','role','is_active','email_verified']
    list_filter = ['role','is_active','email_verified']
    search_fields = ['email','name']
    fieldsets = ((None,{'fields':('email','password','name')}),
        ('Access',{'fields':('role','is_active','email_verified','is_staff','is_superuser','groups','user_permissions')}),
        ('Dates',{'fields':('last_login','date_joined')}))
    add_fieldsets = ((None,{'fields':('email','name','password1','password2','role')}),)
    readonly_fields = ['last_login','date_joined']
admin.site.register(Address)
