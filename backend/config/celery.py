import os
from celery import Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
app = Celery('forma')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
app.conf.beat_schedule = {'deliver-email': {'task':'core.tasks.deliver_email','schedule':30.0}}
app.conf.beat_schedule['reconcile-refunds']={'task':'core.tasks.reconcile_refunds','schedule':60.0}
