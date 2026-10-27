from django.core.management.base import BaseCommand
from payments.models import Refund
from payments.services import reconcile_refund

class Command(BaseCommand):
    help='Reconcile pending provider refunds using trusted server APIs.'
    def handle(self,*args,**kwargs):
        for pk in Refund.objects.filter(status='PENDING').values_list('pk',flat=True)[:100]:
            reconcile_refund(pk)
