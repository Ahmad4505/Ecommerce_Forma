"""Create disposable, untracked browser-test data. Does not touch PostgreSQL."""
import io
import json
import os
from pathlib import Path
import secrets
import sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
os.environ['DJANGO_SETTINGS_MODULE']='config.smoke_settings'
import django
django.setup()
from django.core.management import call_command
from accounts.models import User
credential_path=root/'.setup/backend-smoke-credentials.json'
credentials=json.loads(credential_path.read_text()) if credential_path.exists() else {key:secrets.token_urlsafe(20) for key in ['ADMIN','VENDOR','CUSTOMER','PENDING']}
credential_path.write_text(json.dumps(credentials),encoding='utf-8')
for key,value in credentials.items():
    os.environ['DEMO_'+key+'_PASSWORD']=value
call_command('seed_demo',stdout=io.StringIO())
from vendors.models import Vendor
Vendor.objects.filter(user__email='pending.vendor@ecommerce.test').update(status='PENDING',decision_by=None,decision_at=None,decision_reason='')
print('Disposable browser-test database seeded; credentials stored only under ignored .setup/.')
