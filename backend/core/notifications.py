from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.db import transaction
import logging
from .models import Notification

def notify(user, subject, body, category=None, immediate=False):
    if category == 'orders' and not user.order_notifications:
        return
    notification = Notification.objects.create(recipient=user, subject=subject, body=body)
    if immediate:
        transaction.on_commit(lambda: deliver_notification(notification.pk), robust=True)
    return notification

@transaction.atomic
def deliver_notification(notification_id):
    notification = Notification.objects.select_for_update(skip_locked=True).select_related('recipient').filter(
        pk=notification_id, sent_at__isnull=True, cancelled_at__isnull=True).first()
    if notification is None:
        return False
    try:
        sent = send_mail(notification.subject, notification.body, settings.DEFAULT_FROM_EMAIL, [notification.recipient.email], using='default')
        if sent != 1:
            raise RuntimeError('Mail transport did not accept the message.')
    except Exception:
        logging.getLogger(__name__).warning('Email delivery failed; notification %s remains queued for retry.', notification.pk)
        return False
    if (settings.DEBUG
            and settings.MAILERS.get('default', {}).get('BACKEND') == 'django.core.mail.backends.console.EmailBackend'
            and notification.subject in {'Verify your email', 'Reset your password'}):
        # Console MIME output may encode '=' and wrap tokens. Provide a directly
        # usable link only for the explicitly selected local console transport.
        print(f'Local development {notification.subject.lower()} link:\n{notification.body}\n', flush=True)
    notification.sent_at = timezone.now()
    notification.save(update_fields=['sent_at'])
    return True

def deliver_notifications(limit=100):
    # Durable outbox: run via management command or Celery beat. Failed mail stays pending.
    ids = list(Notification.objects.filter(sent_at__isnull=True, cancelled_at__isnull=True).order_by('created_at').values_list('pk', flat=True)[:limit])
    for notification_id in ids:
        deliver_notification(notification_id)
