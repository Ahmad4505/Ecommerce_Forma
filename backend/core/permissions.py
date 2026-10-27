from rest_framework.permissions import BasePermission

def is_admin(user):
    return user.is_authenticated and user.is_active and user.role == 'ADMIN' and user.is_staff

def approved(user):
    return user.is_authenticated and user.is_active and user.role == 'VENDOR' and hasattr(user, 'vendor') and user.vendor.status == 'APPROVED'

class PlatformAdmin(BasePermission):
    def has_permission(self, request, view):
        return is_admin(request.user)

class VendorManager(BasePermission):
    def has_permission(self, request, view):
        return is_admin(request.user) or approved(request.user)
