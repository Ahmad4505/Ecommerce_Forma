from celery import shared_task
from .notifications import deliver_notifications

@shared_task
def deliver_email():
    deliver_notifications()

@shared_task
def reconcile_refunds():
    from django.core.management import call_command
    call_command('reconcile_refunds')
