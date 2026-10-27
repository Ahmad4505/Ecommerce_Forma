from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from core.permissions import is_admin
from core.models import AuditLog
from core.notifications import notify
from .models import Vendor

@transaction.atomic
def decide_vendor(actor, vendor_id, status, reason=''):
    if not is_admin(actor) or not actor.has_perm('vendors.approve_vendor'):
        raise PermissionDenied('Vendor approval permission required.')
    vendor = Vendor.objects.select_for_update().get(pk=vendor_id)
    if vendor.user_id == actor.id:
        raise PermissionDenied('You cannot approve your own store.')
    transitions = {'PENDING': {'APPROVED','REJECTED'}, 'APPROVED': {'SUSPENDED'},
        'SUSPENDED': {'APPROVED','REJECTED'}, 'REJECTED': {'APPROVED'}}
    if status not in transitions[vendor.status]:
        raise ValidationError('Invalid vendor status transition.')
    vendor.status, vendor.decision_by, vendor.decision_at, vendor.decision_reason = status, actor, timezone.now(), reason
    vendor.save()
    AuditLog.objects.create(actor=actor, action='vendor.'+status.lower(), target=str(vendor.id), details={'reason': reason})
    notify(vendor.user, 'Vendor application update', f'Your store {vendor.name} is {status}. {reason}')
    return vendor
