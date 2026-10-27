from django.core.management.base import BaseCommand
from core.notifications import deliver_notifications

class Command(BaseCommand):
    help = 'Deliver pending outbox email. Schedule regularly in production.'
    def handle(self, *args, **kwargs):
        deliver_notifications()
