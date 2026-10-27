import hashlib
import io
import json
import secrets
import uuid
from decimal import Decimal
from unittest.mock import patch
from datetime import timedelta
import pytest
from PIL import Image
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import User, AccountToken
from vendors.models import Vendor
from categories.models import Category
from products.models import Product
from orders.models import Order
from payments.models import Payment, WebhookEvent
from core.models import AuditLog

pytestmark = pytest.mark.django_db
PASSWORD = 'Unique-test-only-pass-4319!'

@pytest.fixture(autouse=True)
def clean_cache():
    cache.clear()

@pytest.fixture
def data():
    customer = User.objects.create_user('buyer@test.example', PASSWORD, name='Buyer',email_verified=True)
    other = User.objects.create_user('other@test.example',PASSWORD,name='Other',email_verified=True)
    admin = User.objects.create_superuser('admin@test.example',PASSWORD,name='Admin')
    owners=[]
    for index, status in enumerate(['APPROVED','APPROVED','PENDING','REJECTED','SUSPENDED']):
        user=User.objects.create_user(f'vendor{index}@test.example',PASSWORD,name='Owner',role='VENDOR',email_verified=True)
        store=Vendor.objects.create(user=user,name=f'Store {index}',description='Independent maker.',phone='12345678',location='Main street',status=status)
        owners.append((user,store))
    category=Category.objects.create(name='Furniture',slug='furniture')
    products=[]
    for index,(user,store) in enumerate(owners):
        products.append(Product.objects.create(vendor=store,category=category,name=f'Chair {index}',slug=f'chair-{index}',
            description='Oak lounge chair',sku=f'SKU{index}',stock=10,price='100.00'))
    return {'customer':customer,'other':other,'admin':admin,'owners':owners,'products':products,'category':category}

def client(user=None, csrf=False):
    result=APIClient(enforce_csrf_checks=csrf)
    if user:
        result.force_login(user)
    return result

def order_payload(data,quantity=1):
    return {'idempotency_key':str(uuid.uuid4()),'items':[{'productId':str(data['products'][0].id),'quantity':quantity}],
        'address':{'name':'Alex Buyer','street':'10 Main Street','city':'Portland','zip':'97201','country':'United States'}}

def order(data,api=None):
    result=(api or client(data['customer'])).post('/api/orders/',order_payload(data),format='json')
    assert result.status_code==201,result.data
    return result.data

def image():
    output=io.BytesIO()
    Image.new('RGB',(64,64)).save(output,format='PNG')
    output.seek(0)
    output.name='logo.png'
    return output

def test_api_public_catalog_json_and_pagination_contract(data):
    api = client()
    first = api.get('/api/products/?page_size=1')
    assert first.status_code == 200 and first['Content-Type'].startswith('application/json')
    page = first.json()
    assert {'count', 'next', 'previous', 'results'} <= page.keys()
    assert page['count'] == 2 and len(page['results']) == 1 and page['previous'] is None
    product = page['results'][0]
    assert {'id', 'vendorId', 'name', 'price', 'stock', 'images', 'available'} <= product.keys()
    assert Decimal(product['price']) == Decimal('100.00') and product['available'] is True
    assert isinstance(product['images'], list) and isinstance(product['stock'], int)
    second = api.get(page['next'])
    assert second.status_code == 200 and second.json()['next'] is None
    assert second.json()['results'][0]['id'] != product['id']
    assert api.get('/api/products/?page=999').status_code == 404


def test_api_role_response_matrix(data):
    public = ['products', 'categories', 'vendors']
    private = ['orders', 'addresses', 'cart', 'wishlist', 'reviews']
    admin_only = ['admin/users', 'admin/promotions', 'admin/banners', 'admin/reports', 'admin/audit', 'admin/payments']
    for role, user in [('guest', None), ('customer', data['customer']), ('vendor', data['owners'][0][0]), ('admin', data['admin'])]:
        api = client(user)
        for endpoint in public + private + admin_only + ['analytics']:
            expected = 200
            if endpoint not in public:
                if role == 'guest':
                    expected = 401
                elif endpoint in admin_only and role != 'admin':
                    expected = 403
                elif endpoint == 'analytics' and role == 'customer':
                    expected = 403
            response = api.get(f'/api/{endpoint}/')
            assert response.status_code == expected, (role, endpoint, response.status_code)
            assert response['Content-Type'].startswith('application/json')
            body = response.json()
            if expected >= 400:
                assert body['error']['status'] == expected and body['error']['details']


def test_api_error_envelopes_and_method_contract(data):
    api = client(data['customer'])
    responses = [
        (api.post('/api/orders/', {}, format='json'), 400),
        (client().get('/api/orders/'), 401),
        (api.get('/api/admin/payments/'), 403),
        (api.get(f'/api/products/{uuid.uuid4()}/'), 404),
        (api.get('/api/payments/'), 405),
        (api.post('/api/orders/', '{broken', content_type='application/json'), 400),
        (client(csrf=True).post('/api/auth/login/', {}, format='json'), 403),
    ]
    for response, status in responses:
        assert response.status_code == status
        assert response['Content-Type'].startswith('application/json')
        body = response.json()
        assert body['error']['status'] == status and body['error']['details']
        assert 'Traceback' not in response.content.decode()
    assert 'POST' in responses[4][0]['Allow']


def test_registration_never_assigns_privileged_fields():
    api=client()
    response=api.post('/api/auth/register/',{'name':'New Buyer','email':'new@test.example','password':PASSWORD,
        'role':'ADMIN','email_verified':True,'is_staff':True},format='json')
    assert response.status_code==201,response.data
    user=User.objects.get(email='new@test.example')
    assert user.check_password(PASSWORD) and user.role=='CUSTOMER' and not user.email_verified and not user.is_staff
    assert api.post('/api/auth/login/',{'email':user.email,'password':PASSWORD},format='json').status_code==400


@pytest.mark.parametrize('backend', ['console', 'smtp'])
def test_existing_email_environment_loads_mailers_without_deprecations(backend):
    import os
    import subprocess
    import sys
    from pathlib import Path
    probe = '''
import os, warnings, django
from django.utils.deprecation import RemovedInDjango2028Warning
warnings.simplefilter('error', RemovedInDjango2028Warning)
django.setup()
from django.conf import settings
from django.core import mail
from accounts.views import email_delivery_mode
mailer = mail.mailers.default
backend = os.environ['EMAIL_BACKEND']
assert settings.MAILERS['default']['BACKEND'] == backend
assert email_delivery_mode() == ('console' if backend.endswith('console.EmailBackend') else 'email')
if backend.endswith('smtp.EmailBackend'):
    assert mailer.host == os.environ['EMAIL_HOST']
    assert mailer.port == 2525 and mailer.use_tls is True
    assert mailer.username == os.environ['EMAIL_HOST_USER']
    assert mailer.password == os.environ['EMAIL_HOST_PASSWORD']
    assert mailer.timeout == 17
assert not hasattr(settings, 'EMAIL_BACKEND')
print('Existing email environment mapped successfully; no transport connection opened')
'''
    result = subprocess.run([sys.executable, '-c', probe], cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, 'DJANGO_SETTINGS_MODULE':'config.settings', 'DEBUG':'True',
             'EMAIL_BACKEND':f'django.core.mail.backends.{backend}.EmailBackend',
             'EMAIL_HOST':'smtp.test.example', 'EMAIL_PORT':'2525', 'EMAIL_HOST_USER':'test-user',
             'EMAIL_HOST_PASSWORD':'test-only-mail-password', 'EMAIL_USE_TLS':'True', 'EMAIL_TIMEOUT':'17'},
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_email_delivery_mode_respects_mailer_and_debug(settings):
    from accounts.views import email_delivery_mode
    settings.MAILERS = {'default': {'BACKEND':'django.core.mail.backends.console.EmailBackend'}}
    settings.DEBUG = True
    assert email_delivery_mode() == 'console'
    settings.DEBUG = False
    assert email_delivery_mode() == 'email'


def test_console_registration_activation_login_and_logout(settings, django_capture_on_commit_callbacks):
    import re
    from contextlib import redirect_stdout
    from urllib.parse import urlsplit, parse_qs
    from core.models import Notification
    settings.DEBUG = True
    settings.MAILERS = {'default': {'BACKEND':'django.core.mail.backends.console.EmailBackend'}}
    api = client(csrf=True)
    token = api.get('/api/auth/csrf/').data['csrfToken']
    payload = {'name':'Console Buyer','email':'console-buyer@test.example','password':PASSWORD}
    output = io.StringIO()
    with redirect_stdout(output), django_capture_on_commit_callbacks(execute=True):
        registered = api.post('/api/auth/register/', payload, format='json', HTTP_X_CSRFTOKEN=token)
    assert registered.status_code == 201 and registered.data['emailDelivery'] == 'console'
    assert Notification.objects.get(recipient__email=payload['email']).sent_at is not None
    assert api.get('/api/auth/session/').data['user'] is None
    verification = re.search(r'Local development verify your email link:\n(https?://[^\s]+)', output.getvalue())
    assert verification, 'Console mail must contain the verification link'
    verification_token = parse_qs(urlsplit(verification[1]).query)['token'][0]
    endpoint = '/api/auth/verify-email/'
    assert api.post(endpoint, {'token':verification_token}, format='json', HTTP_X_CSRFTOKEN=token).status_code == 200
    assert api.post(endpoint, {'token':verification_token}, format='json', HTTP_X_CSRFTOKEN=token).status_code == 400
    assert api.post('/api/auth/login/', payload, format='json', HTTP_X_CSRFTOKEN=token).status_code == 200
    assert api.get('/api/auth/session/').data['user']['email'] == payload['email']
    token = api.get('/api/auth/csrf/').data['csrfToken']
    assert api.post('/api/auth/logout/', {}, format='json', HTTP_X_CSRFTOKEN=token).status_code == 204
    assert api.get('/api/auth/session/').data['user'] is None


@pytest.mark.parametrize('backend,debug', [('smtp',True), ('console',False)])
def test_plain_auth_link_output_is_limited_to_debug_console(data, settings, backend, debug):
    from contextlib import redirect_stdout
    from core.notifications import notify, deliver_notification
    settings.DEBUG = debug
    settings.MAILERS = {'default': {'BACKEND':f'django.core.mail.backends.{backend}.EmailBackend'}}
    record = notify(data['customer'], 'Verify your email', 'http://localhost/verify-email?token=test-only-token')
    output = io.StringIO()
    with patch('core.notifications.send_mail', return_value=1), redirect_stdout(output):
        assert deliver_notification(record.pk) is True
    assert output.getvalue() == ''

def test_registration_sends_after_commit_and_preserves_password_spaces(django_capture_on_commit_callbacks):
    from django.core import mail
    from core.models import Notification
    api=client(csrf=True)
    token=api.get('/api/auth/csrf/').data['csrfToken']
    password=' '+PASSWORD+' '
    with django_capture_on_commit_callbacks(execute=True):
        response=api.post('/api/auth/register/',{'name':'Mail Buyer','email':'mail@test.example','password':password},format='json',HTTP_X_CSRFTOKEN=token)
    assert response.status_code==201
    assert len(mail.outbox)==1
    assert Notification.objects.get(recipient__email='mail@test.example').sent_at is not None
    verification=mail.outbox[0].body.split('token=')[1]
    assert api.post('/api/auth/verify-email/',{'token':verification},format='json',HTTP_X_CSRFTOKEN=token).status_code==200
    assert api.post('/api/auth/login/',{'email':'mail@test.example','password':password},format='json',HTTP_X_CSRFTOKEN=token).status_code==200

def test_failed_auth_email_stays_queued_and_resend_is_safe(django_capture_on_commit_callbacks):
    from core.models import Notification
    from core.notifications import deliver_notifications
    from django.core import mail
    api=client(csrf=True)
    token=api.get('/api/auth/csrf/').data['csrfToken']
    with patch('core.notifications.send_mail',side_effect=OSError('Mail unavailable')):
        with django_capture_on_commit_callbacks(execute=True):
            response=api.post('/api/auth/register/',{'name':'Queued Buyer','email':'queued@test.example','password':PASSWORD},format='json',HTTP_X_CSRFTOKEN=token)
    assert response.status_code==201
    old=Notification.objects.get(recipient__email='queued@test.example')
    assert old.sent_at is None
    assert api.post('/api/auth/resend-verification/',{'email':'queued@test.example'},format='json').status_code==403
    with django_capture_on_commit_callbacks(execute=True):
        response=api.post('/api/auth/resend-verification/',{'email':'queued@test.example'},format='json',HTTP_X_CSRFTOKEN=token)
    assert response.status_code==200
    old.refresh_from_db()
    assert old.cancelled_at is not None and old.sent_at is None
    assert len(mail.outbox)==1
    deliver_notifications()
    assert len(mail.outbox)==1
    assert api.post('/api/auth/resend-verification/',{'email':'queued@test.example'},format='json',HTTP_X_CSRFTOKEN=token).status_code==200
    assert Notification.objects.filter(recipient__email='queued@test.example').count()==2
    missing=api.post('/api/auth/resend-verification/',{'email':'missing@test.example'},format='json',HTTP_X_CSRFTOKEN=token)
    assert missing.status_code==200 and missing.data['message']==response.data['message']

@pytest.mark.parametrize('password', ['123', ' '*12])
def test_password_validation(password):
    response=client().post('/api/auth/register/',{'name':'New','email':'weak@test.example','password':password},format='json')
    assert response.status_code==400

def test_password_change_requires_current_password_csrf_and_preserves_session(data):
    api=client(csrf=True)
    endpoint='/api/auth/password-change/'
    assert api.post(endpoint,{},format='json').status_code==401
    token=api.get('/api/auth/csrf/').data['csrfToken']
    assert api.post('/api/auth/login/',{'email':'  BUYER@test.example  ','password':PASSWORD},format='json',HTTP_X_CSRFTOKEN=token).status_code==200
    other_session=client(data['customer'])
    payload={'current_password':PASSWORD,'password':'Replacement-test-pass-4839!'}
    assert api.post(endpoint,payload,format='json').status_code==403
    token=api.get('/api/auth/csrf/').data['csrfToken']
    assert api.post(endpoint,{**payload,'current_password':'incorrect'},format='json',HTTP_X_CSRFTOKEN=token).status_code==400
    assert api.post(endpoint,{**payload,'password':'weak'},format='json',HTTP_X_CSRFTOKEN=token).status_code==400
    assert api.post(endpoint,payload,format='json',HTTP_X_CSRFTOKEN=token).status_code==200
    assert api.get('/api/auth/session/').data['user']['id']==str(data['customer'].id)
    assert other_session.get('/api/auth/session/').data['user'] is None
    data['customer'].refresh_from_db()
    assert data['customer'].check_password(payload['password'])

def test_registration_verification_and_real_session_login():
    api=client(csrf=True)
    token=api.get('/api/auth/csrf/').data['csrfToken']
    payload={'name':'Registered Buyer','email':'registered@test.example','password':PASSWORD}
    with patch('accounts.views.notify') as notify_mock:
        assert api.post('/api/auth/register/',payload,format='json',HTTP_X_CSRFTOKEN=token).status_code==201
    verification=notify_mock.call_args.args[2].split('token=')[1]
    assert api.post('/api/auth/verify-email/',{'token':verification},format='json',HTTP_X_CSRFTOKEN=token).status_code==200
    assert api.post('/api/auth/verify-email/',{'token':verification},format='json',HTTP_X_CSRFTOKEN=token).status_code==400
    assert api.post('/api/auth/login/',payload,format='json',HTTP_X_CSRFTOKEN=token).status_code==200
    assert api.get('/api/auth/session/').data['user']['email']==payload['email']

def test_preferences_are_scoped_and_persisted(data):
    endpoint='/api/auth/preferences/'
    assert client().patch(endpoint,{},format='json').status_code==401
    api=client(data['customer'])
    assert api.patch(endpoint,{'newsletter_notifications':'invalid','order_notifications':False},format='json').status_code==400
    assert api.patch(endpoint,{'newsletter_notifications':False,'order_notifications':False,'role':'ADMIN','id':str(data['other'].id)},format='json').status_code==200
    data['customer'].refresh_from_db()
    data['other'].refresh_from_db()
    assert not data['customer'].newsletter_notifications and not data['customer'].order_notifications
    assert data['customer'].role=='CUSTOMER'
    assert data['other'].newsletter_notifications and data['other'].order_notifications
    assert api.get('/api/auth/session/').data['user']['order_notifications'] is False
    from core.notifications import notify
    from core.models import Notification
    notify(data['customer'],'Order update','Optional update',category='orders')
    assert not Notification.objects.filter(recipient=data['customer']).exists()
    notify(data['customer'],'Password security','Required account message')
    assert Notification.objects.filter(recipient=data['customer']).count()==1

def test_admin_payment_overview_permission_and_records(data):
    created=order(data)
    customer_api=client(data['customer'])
    payment=customer_api.post('/api/payments/',{'order_id':created['id'],'provider':'mock'},format='json')
    assert payment.status_code==200
    endpoint='/api/admin/payments/'
    assert client().get(endpoint).status_code==401
    assert customer_api.get(endpoint).status_code==403
    assert client(data['owners'][0][0]).get(endpoint).status_code==403
    response=client(data['admin']).get(endpoint)
    assert response.status_code==200
    assert response.data['results'][0]['id']==payment.data['id']

def test_unconfigured_payment_options_are_disabled():
    from django.test import override_settings
    with override_settings(MOCK_PAYMENTS_ENABLED=False, ENABLED_PAYMENT_PROVIDERS=[], PAYMENT_CONFIG={}):
        providers=client().get('/api/bootstrap/').data['paymentProviders']
        assert providers=={'mock':False,'paypal':False,'checkout':False,'hyperpay':False}

def test_admin_can_still_manage_inactive_banners(data):
    from promotions.models import Banner
    banner=Banner.objects.create(title='Hidden banner',subtitle='Saved but not published',active=False)
    assert str(banner.id) in {row['id'] for row in client(data['admin']).get('/api/bootstrap/').data['banners']}
    assert str(banner.id) not in {row['id'] for row in client().get('/api/bootstrap/').data['banners']}

def test_csrf_login_logout_and_cart(data):
    api=client(csrf=True)
    assert api.post('/api/auth/login/',{'email':data['customer'].email,'password':PASSWORD},format='json').status_code==403
    token=api.get('/api/auth/csrf/').data['csrfToken']
    assert api.post('/api/auth/login/',{'email':data['customer'].email,'password':PASSWORD},format='json',HTTP_X_CSRFTOKEN=token).status_code==200
    assert api.post('/api/auth/logout/',{}).status_code==403
    assert api.put('/api/cart/',[],format='json').status_code==403
    token=api.get('/api/auth/csrf/').data['csrfToken']
    assert api.post('/api/auth/logout/',{},HTTP_X_CSRFTOKEN=token).status_code==204
    assert api.get('/api/orders/').status_code==401

def test_reset_single_use_and_expiry(data):
    api=client()
    token=secrets.token_urlsafe(24)
    record=AccountToken.objects.create(user=data['customer'],purpose='reset',digest=hashlib.sha256(token.encode()).hexdigest(),expires_at=timezone.now()+timedelta(minutes=30))
    payload={'token':token,'password':'Replacement-test-pass-4839!'}
    assert api.post('/api/auth/password-reset-confirm/',payload,format='json').status_code==200
    assert api.post('/api/auth/password-reset-confirm/',payload,format='json').status_code==400
    expired='expired-token'
    AccountToken.objects.create(user=data['customer'],purpose='reset',digest=hashlib.sha256(expired.encode()).hexdigest(),expires_at=timezone.now()-timedelta(seconds=1))
    assert api.post('/api/auth/password-reset-confirm/',{**payload,'token':expired},format='json').status_code==400

def test_vendor_registration_starts_pending():
    response=client().post('/api/vendor-applications/',{'name':'Maker Name','email':'maker@test.example','password':PASSWORD,
        'store_name':'New Studio','description':'A detailed independent studio description.','phone':'123456789','address':'10 Studio Street','logo':image()},format='multipart')
    assert response.status_code==201,response.data
    assert Vendor.objects.get(user__email='maker@test.example').status=='PENDING'

@pytest.mark.parametrize('index',[2,3,4])
def test_unapproved_vendors_cannot_create_or_modify(data,index):
    user,store=data['owners'][index]
    api=client(user)
    assert api.post('/api/products/',{'name':'Forbidden'},format='json').status_code in [400,403]
    assert api.patch(f'/api/products/{data["products"][index].id}/',{'stock':12},format='json').status_code in [403,404]

def test_approval_and_immediate_suspension(data):
    user,store=data['owners'][2]
    api=client(data['admin'])
    assert client(data['customer']).post(f'/api/vendors/{store.id}/decision/',{'status':'APPROVED'},format='json').status_code==403
    assert client(user).post(f'/api/vendors/{store.id}/decision/',{'status':'APPROVED'},format='json').status_code==403
    assert api.post(f'/api/vendors/{store.id}/decision/',{'status':'APPROVED'},format='json').status_code==200
    assert client(user).patch(f'/api/products/{data["products"][2].id}/',{'stock':12},format='json').status_code==200
    assert api.post(f'/api/vendors/{store.id}/decision/',{'status':'SUSPENDED'},format='json').status_code==200
    assert client(user).patch(f'/api/products/{data["products"][2].id}/',{'stock':15},format='json').status_code in [403,404]
    assert AuditLog.objects.filter(target=str(store.id)).count()==2

def test_product_object_permissions_and_prices(data):
    product=data['products'][0]
    url=f'/api/products/{product.id}/'
    assert client(data['owners'][1][0]).patch(url,{'stock':999},format='json').status_code==403
    assert client(data['customer']).patch(url,{'stock':999},format='json').status_code==403
    assert client(data['owners'][0][0]).patch(url,{'price':'-1'},format='json').status_code==400
    assert client(data['owners'][0][0]).patch(url,{'discountPrice':'101'},format='json').status_code==400
    assert len(client().get('/api/products/').data['results'])==2

def test_upload_rejects_malicious_and_accepts_reencoded_image(data,tmp_path,settings):
    settings.MEDIA_ROOT=tmp_path
    api=client(data['owners'][0][0])
    file=io.BytesIO(b'<script>alert(1)</script>');file.name='evil.jpg'
    url=f'/api/products/{data["products"][0].id}/images/'
    assert api.post(url,{'images':file},format='multipart').status_code==400
    assert api.post(url,{'images':image()},format='multipart').status_code==200
    original=data['products'][0].pictures.get().id
    assert api.post(url,{'images':image(),'replace':'true'},format='multipart').status_code==200
    assert data['products'][0].pictures.count()==1
    assert data['products'][0].pictures.get().id!=original
    invalid=io.BytesIO(b'not an image');invalid.name='bad.jpg'
    assert api.post(url,{'images':invalid,'replace':'true'},format='multipart').status_code==400
    assert data['products'][0].pictures.count()==1

def test_public_forms_require_csrf_validate_and_persist():
    from core.models import ContactMessage, NewsletterSubscriber
    api=client(csrf=True)
    payload={'name':'Audit Buyer','email':'public@test.example','topic':'Order question','message':'Please help me with an order.'}
    assert api.post('/api/contact/',payload,format='json').status_code==403
    token=api.get('/api/auth/csrf/').data['csrfToken']
    assert api.post('/api/contact/',{**payload,'message':'short'},format='json',HTTP_X_CSRFTOKEN=token).status_code==400
    assert api.post('/api/contact/',payload,format='json',HTTP_X_CSRFTOKEN=token).status_code==201
    assert ContactMessage.objects.get().message==payload['message']
    for _ in range(2):
        assert api.post('/api/newsletter/',{'email':payload['email']},format='json',HTTP_X_CSRFTOKEN=token).status_code==201
    assert NewsletterSubscriber.objects.count()==1
    assert api.get('/api/contact/').status_code==405

def test_unhandled_api_errors_are_generic():
    from core.errors import exception_handler
    response=exception_handler(RuntimeError('sensitive internal detail'),{})
    assert response.status_code==500
    assert 'sensitive internal detail' not in str(response.data)

def test_address_idor_and_owner_mass_assignment(data):
    from accounts.models import Address
    payload={'label':'Home','name':'Buyer','street':'10 Main Street','city':'Portland','zip':'97201','country':'US','userId':str(data['other'].id)}
    api=client(data['customer'])
    response=api.post('/api/addresses/',payload,format='json')
    assert response.status_code==201
    record=Address.objects.get(pk=response.data['id'])
    assert record.user_id==data['customer'].id
    url=f'/api/addresses/{record.id}/'
    outsider=client(data['other'])
    assert outsider.get(url).status_code==404
    assert outsider.patch(url,{'street':'Changed address'},format='json').status_code==404
    assert outsider.delete(url).status_code==404
    assert Address.objects.filter(pk=record.id,street='10 Main Street').exists()

def test_catalog_search_treats_sql_as_text_and_expired_session_is_anonymous(data):
    api=client(data['customer'])
    response=api.get('/api/products/',{'search':"'; DROP TABLE products_product; --"})
    assert response.status_code==200
    assert Product.objects.count()==len(data['products'])
    session=api.session
    session.set_expiry(-1)
    session.save()
    assert api.get('/api/auth/session/').data['user'] is None

def test_stock_prices_idempotency_and_order_ownership(data):
    api=client(data['customer']);payload=order_payload(data,2)
    payload['items'][0]['price']='0.01';payload['total']='0.02'
    first=api.post('/api/orders/',payload,format='json')
    assert first.status_code==201,first.data
    assert Decimal(first.data['total'])==Decimal('200.00')
    assert api.post('/api/orders/',payload,format='json').data['id']==first.data['id']
    data['products'][0].refresh_from_db();assert data['products'][0].stock==8
    changed={**payload,'items':[{'productId':str(data['products'][0].id),'quantity':1}]}
    assert api.post('/api/orders/',changed,format='json').status_code==409
    assert client(data['other']).get('/api/orders/'+first.data['id']+'/').status_code==404
    assert api.post('/api/orders/',order_payload(data,9),format='json').status_code==409
    assert Order.objects.count()==1

def test_vendor_only_own_order_lines(data):
    payload=order_payload(data);payload['items'].append({'productId':str(data['products'][1].id),'quantity':1})
    created=client(data['customer']).post('/api/orders/',payload,format='json')
    response=client(data['owners'][0][0]).get('/api/orders/'+created.data['id']+'/')
    assert len(response.data['items'])==1
    assert 'subtotal' not in response.data
    assert all(i['vendorId']==str(data['owners'][0][1].id) for i in response.data['items'])
    assert 'userId' not in response.data
    first_key=response.data['customerKey']
    assert first_key and first_key!=str(data['customer'].id)
    second_vendor=client(data['owners'][1][0]).get('/api/orders/'+created.data['id']+'/')
    assert second_vendor.data['customerKey']!=first_key
    repeated=order(data)
    same=client(data['owners'][0][0]).get('/api/orders/'+repeated['id']+'/')
    assert same.data['customerKey']==first_key
    other=order(data,client(data['other']))
    different=client(data['owners'][0][0]).get('/api/orders/'+other['id']+'/')
    assert different.data['customerKey']!=first_key

def test_cancellation_once_and_paid_fulfillment(data):
    created=order(data);api=client(data['customer']);url='/api/orders/'+created['id']+'/status/'
    assert api.post(url,{'status':'Cancelled'},format='json').status_code==200
    assert api.post(url,{'status':'Cancelled'},format='json').status_code==200
    data['products'][0].refresh_from_db();assert data['products'][0].stock==10
    created=order(data)
    url='/api/orders/'+created['id']+'/status/'
    vendor=client(data['owners'][0][0])
    assert vendor.post(url,{'status':'Shipped'},format='json').status_code==409

def test_mock_failed_then_success_and_redirect_is_not_proof(data):
    created=order(data);api=client(data['customer'])
    payment=api.post('/api/payments/',{'order_id':created['id'],'provider':'mock'},format='json')
    assert payment.status_code==200,payment.data
    order_model=Order.objects.get(pk=created['id']);assert order_model.payment_status=='PENDING'
    url='/api/payments/'+payment.data['id']+'/verify/'
    assert api.post(url,{'mock_outcome':'CANCELLED'},format='json').data['status']=='CANCELLED'
    assert api.post(url,{'mock_outcome':'FAILED'},format='json').data['status']=='FAILED'
    order_model.refresh_from_db();assert order_model.payment_status=='PENDING'
    assert api.post(url,{'mock_outcome':'SUCCEEDED'},format='json').data['status']=='SUCCEEDED'
    assert api.post(url,{'mock_outcome':'SUCCEEDED'},format='json').data['status']=='SUCCEEDED'
    order_model.refresh_from_db();assert order_model.payment_status=='SUCCEEDED'
    assert Payment.objects.count()==1

def test_external_payment_blocks_cancellation_until_reconciled(data):
    created=order(data)
    Payment.objects.create(order_id=created['id'],provider='checkout',reference='hpp_test',status='REQUIRES_ACTION',amount=108,currency='USD')
    assert client(data['customer']).post('/api/orders/'+created['id']+'/status/',{'status':'Cancelled'},format='json').status_code==409

def test_real_provider_missing_credentials_fails_closed(data):
    created=order(data)
    response=client(data['customer']).post('/api/payments/',{'order_id':created['id'],'provider':'paypal'},format='json')
    assert response.status_code==503
    assert not Payment.objects.exists()

def test_partial_refund_admin_only_and_idempotent(data):
    created=order(data);buyer=client(data['customer'])
    payment=buyer.post('/api/payments/',{'order_id':created['id'],'provider':'mock'},format='json').data
    buyer.post('/api/payments/'+payment['id']+'/verify/',{'mock_outcome':'SUCCEEDED'},format='json')
    payload={'amount':'20.00','reason':'Partial return','idempotency_key':str(uuid.uuid4())}
    url='/api/payments/'+payment['id']+'/refunds/'
    assert buyer.post(url,payload,format='json').status_code==403
    api=client(data['admin'])
    first=api.post(url,payload,format='json')
    assert first.status_code==200,first.data
    assert api.post(url,payload,format='json').data['id']==first.data['id']
    model=Payment.objects.get(pk=payment['id']);assert model.refunded_amount==20 and model.status=='SUCCEEDED'
    assert api.post(url,{**payload,'idempotency_key':str(uuid.uuid4()),'amount':'1000.00'},format='json').status_code==409

def test_async_refund_reconciliation_counts_once(data):
    from payments.models import Refund
    from payments.services import reconcile_refund
    created=order(data)
    payment=Payment.objects.create(order_id=created['id'],provider='checkout',reference='hpp_test',capture_id='pay_test',status='SUCCEEDED',amount=108,currency='USD')
    refund=Refund.objects.create(payment=payment,idempotency_key=uuid.uuid4(),amount=20,reference='act_test',reason='Return',actor=data['admin'])
    with patch('payments.services.adapter') as factory:
        factory.return_value.refund_status.return_value='SUCCEEDED'
        reconcile_refund(refund.id)
        reconcile_refund(refund.id)
        assert factory.return_value.refund_status.call_count==1
    payment.refresh_from_db();assert payment.refunded_amount==20

def test_seed_image_references_are_available():
    from pathlib import Path
    catalog=json.loads((settings.BASE_DIR/'core/seed/catalog.json').read_text())
    for product in catalog['products']:
        path=settings.BASE_DIR.parent/'public'/product['images'][0].lstrip('/')
        assert path.exists(),str(path)
        with Image.open(path) as photo:
            assert min(photo.size)>0

def test_public_private_data_and_session_security(data):
    payload=client().get('/api/bootstrap/').data
    assert not payload['users'] and not payload['orders'] and not payload['addresses']
    assert all('email' not in vendor for vendor in payload['vendors'])
    api=client(data['customer']);response=api.get('/api/bootstrap/')
    assert response['Cache-Control']=='no-store'
    assert 'frame-ancestors' in response['Content-Security-Policy']
    assert api.patch('/api/auth/profile/',{'name':'Buyer','email':data['customer'].email,'role':'ADMIN'},format='json').status_code==200
    data['customer'].refresh_from_db();assert data['customer'].role=='CUSTOMER'

def test_invalid_checkout_webhook_signature(settings):
    settings.ENABLED_PAYMENT_PROVIDERS=['checkout']
    settings.PAYMENT_CONFIG={**settings.PAYMENT_CONFIG,'CHECKOUT_SECRET':'test-secret','CHECKOUT_WEBHOOK_SECRET':'signing-key','CHECKOUT_BASE_URL':'https://abcdefgh.api.sandbox.checkout.com'}
    assert client().post('/api/payments/webhooks/checkout/',{'id':'evt-test','data':{}},format='json',HTTP_CKO_SIGNATURE='invalid').status_code==403
    assert WebhookEvent.objects.count()==0

def test_authenticated_webhook_idempotency(data,settings):
    import hmac
    settings.ENABLED_PAYMENT_PROVIDERS=['checkout']
    settings.PAYMENT_CONFIG={**settings.PAYMENT_CONFIG,'CHECKOUT_SECRET':'test-secret','CHECKOUT_WEBHOOK_SECRET':'signing-key','CHECKOUT_BASE_URL':'https://abcdefgh.api.sandbox.checkout.com'}
    created=order(data)
    payment=Payment.objects.create(order_id=created['id'],provider='checkout',reference='hpp_123',amount=108,currency='USD')
    event=json.dumps({'id':'event-1','data':{'reference':str(payment.id)}})
    signature=hmac.new(b'signing-key',event.encode(),hashlib.sha256).hexdigest()
    with patch('payments.adapters.Checkout.verify',return_value=('SUCCEEDED','pay_test')) as verifier:
        for _ in range(2):
            assert client().post('/api/payments/webhooks/checkout/',event,content_type='application/json',HTTP_CKO_SIGNATURE=signature).status_code==200
        assert verifier.call_count==1
    assert WebhookEvent.objects.count()==1

def test_auth_throttling(data,settings):
    from accounts.views import AuthThrottle
    with patch.object(AuthThrottle,'rate','2/min',create=True):
        api=client()
        assert api.post('/api/auth/login/',{},format='json').status_code==400
        assert api.post('/api/auth/login/',{},format='json').status_code==400
        assert api.post('/api/auth/login/',{},format='json').status_code==429

def test_demo_seed_is_idempotent_and_four_accounts_work(settings):
    settings.DEBUG=True
    out=io.StringIO()
    with patch.dict('os.environ',{f'DEMO_{key}_PASSWORD':PASSWORD for key in ['ADMIN','VENDOR','CUSTOMER','PENDING']}):
        call_command('seed_demo',stdout=out)
        call_command('seed_demo',stdout=out)
    assert Product.objects.count()==60
    assert Category.objects.count()==10
    for email in ['admin@ecommerce.test','vendor@ecommerce.test','customer@ecommerce.test','pending.vendor@ecommerce.test']:
        assert client().post('/api/auth/login/',{'email':email,'password':PASSWORD},format='json').status_code==200
    assert Vendor.objects.get(user__email='pending.vendor@ecommerce.test').status=='PENDING'

def test_seed_generates_credentials_and_preserves_existing_vendor_password(settings,monkeypatch):
    settings.DEBUG=True
    for key in ['ADMIN','VENDOR','CUSTOMER','PENDING']:
        monkeypatch.delenv('DEMO_'+key+'_PASSWORD',raising=False)
    existing=User.objects.create_user('studio2@ecommerce.test',PASSWORD,name='Existing owner',role='VENDOR')
    original_hash=existing.password
    output=io.StringIO()
    call_command('seed_demo',stdout=output)
    existing.refresh_from_db()
    assert existing.password==original_hash
    assert 'NEW LOCAL ACCOUNT customer@ecommerce.test password: ' in output.getvalue()
    assert Product.objects.count()==60

def test_session_and_csrf_reads_do_not_consume_login_attempt_budget():
    from accounts.views import AuthThrottle
    with patch.object(AuthThrottle,'rate','2/min',create=True):
        api=client()
        for _ in range(4):
            assert api.get('/api/auth/csrf/').status_code==200
            assert api.get('/api/auth/session/').status_code==200
        assert api.post('/api/auth/login/',{},format='json').status_code==400
        assert api.post('/api/auth/login/',{},format='json').status_code==400
        assert api.post('/api/auth/login/',{},format='json').status_code==429

@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_checkout():
    from django.db import connection
    if connection.vendor!='postgresql':
        pytest.skip('PostgreSQL required: SQLite cannot validate row-lock concurrency.')
    from concurrent.futures import ThreadPoolExecutor
    from django.db import close_old_connections
    from orders.services import checkout, Conflict
    owner=User.objects.create_user('race-owner@test.example',PASSWORD,name='Owner',role='VENDOR',email_verified=True)
    store=Vendor.objects.create(user=owner,name='Race store',status='APPROVED')
    category=Category.objects.create(name='Race',slug='race')
    product=Product.objects.create(vendor=store,category=category,name='Last chair',slug='last-chair',sku='LAST',price=10,stock=1)
    buyers=[User.objects.create_user(f'race-{i}@test.example',PASSWORD,name='Buyer',email_verified=True) for i in range(2)]
    def buy(pk):
        close_old_connections()
        try:
            from orders.views import CheckoutInput
            payload={'idempotency_key':str(uuid.uuid4()),'items':[{'productId':str(product.id),'quantity':1}], 'address':{'name':'Buyer','street':'10 Main','city':'Town','zip':'1234','country':'US'}}
            serializer=CheckoutInput(data=payload);serializer.is_valid(raise_exception=True)
            checkout(User.objects.get(pk=pk),serializer.validated_data)
            return True
        except Conflict:
            return False
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(buy,[u.pk for u in buyers]))
    assert sum(outcomes)==1
    product.refresh_from_db();assert product.stock==0


def assert_committed_postgresql_rows(checks):
    """Read committed test records from a separate process, never the development DB."""
    import os
    import subprocess
    import sys
    from django.db import connection
    assert connection.vendor == 'postgresql'
    assert connection.get_autocommit() and not connection.in_atomic_block
    config = connection.settings_dict
    assert config['NAME'].startswith('test_'), 'Persistence probes require a disposable test database'
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_backend_pid()')
        old_pid = cursor.fetchone()[0]
    connection.close()
    parameters = {key: config[value] for key, value in [('dbname','NAME'),('user','USER'),('password','PASSWORD'),('host','HOST'),('port','PORT')] if config.get(value)}
    parameters.update(config.get('OPTIONS', {}))
    probe = '''
import json, os, psycopg
parameters = json.loads(os.environ['PERSISTENCE_TEST_CONNECTION'])
assert parameters['dbname'].startswith('test_')
checks = json.loads(os.environ['PERSISTENCE_TEST_CHECKS'])
with psycopg.connect(**parameters, connect_timeout=10) as db:
    db.execute('SET TRANSACTION READ ONLY')
    for index, check in enumerate(checks):
        rows = db.execute(check['sql'], check['params']).fetchall()
        actual = json.loads(json.dumps(rows, default=str))
        assert actual == check['expected'], f'Persistence check {index} failed'
print(f'Verified {len(checks)} committed PostgreSQL checks in a separate process')
'''
    result = subprocess.run([sys.executable, '-c', probe], env={**os.environ,
        'PERSISTENCE_TEST_CONNECTION': json.dumps(parameters),
        'PERSISTENCE_TEST_CHECKS': json.dumps(checks, default=str)}, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_backend_pid()')
        assert cursor.fetchone()[0] != old_pid


@pytest.mark.django_db(transaction=True)
def test_postgresql_account_catalog_and_cart_persist_across_processes(data, settings, tmp_path):
    from django.db import connection
    if connection.vendor != 'postgresql':
        pytest.skip('PostgreSQL persistence verification requires a real database.')
    settings.MEDIA_ROOT = tmp_path / 'media'
    buyer = client(data['customer'])
    vendor = client(data['owners'][0][0])
    admin = client(data['admin'])
    assert buyer.patch('/api/auth/profile/', {'name':'Persisted Buyer','email':data['customer'].email}, format='json').status_code == 200
    assert buyer.patch('/api/auth/preferences/', {'newsletter_notifications':False,'order_notifications':False}, format='json').status_code == 200
    address = buyer.post('/api/addresses/', {'label':'Home','name':'Persisted Buyer','street':'25 Persistence Street','city':'Portland','zip':'97201','country':'United States'}, format='json')
    assert address.status_code == 201
    pending = data['owners'][2][1]
    assert admin.post(f'/api/vendors/{pending.id}/decision/', {'status':'APPROVED'}, format='json').status_code == 200
    product = vendor.post('/api/products/', {'vendorId':str(data['owners'][0][1].id),'name':'Persisted Stool','slug':'persisted-stool','sku':'PERSIST-1','description':'Committed catalog record','category':data['category'].name,'price':'75.00','stock':6}, format='json')
    assert product.status_code == 201, product.data
    product_id = product.data['id']
    assert vendor.patch(f'/api/products/{product_id}/', {'price':'79.00'}, format='json').status_code == 200
    assert vendor.post(f'/api/products/{product_id}/images/', {'images':image()}, format='multipart').status_code == 200
    assert buyer.put('/api/cart/', [{'productId':product_id,'quantity':2,'variant':'Natural'}], format='json').status_code == 200
    assert buyer.post('/api/wishlist/', {'productId':product_id}, format='json').status_code == 200
    checks = [
        {'sql':'SELECT name, newsletter_notifications, order_notifications FROM accounts_user WHERE id=%s','params':[data['customer'].id],'expected':[['Persisted Buyer',False,False]]},
        {'sql':'SELECT street FROM accounts_address WHERE id=%s AND user_id=%s','params':[address.data['id'],data['customer'].id],'expected':[['25 Persistence Street']]},
        {'sql':'SELECT status FROM vendors_vendor WHERE id=%s','params':[pending.id],'expected':[['APPROVED']]},
        {'sql':'SELECT price, stock, vendor_id FROM products_product WHERE id=%s','params':[product_id],'expected':[['79.00',6,str(data['owners'][0][1].id)]]},
        {'sql':'SELECT COUNT(*) FROM products_productimage WHERE product_id=%s','params':[product_id],'expected':[[1]]},
        {'sql':'SELECT quantity FROM carts_cartitem WHERE user_id=%s AND product_id=%s','params':[data['customer'].id,product_id],'expected':[[2]]},
        {'sql':'SELECT COUNT(*) FROM carts_wishlistitem WHERE user_id=%s AND product_id=%s','params':[data['customer'].id,product_id],'expected':[[1]]},
        {'sql':'SELECT COUNT(*) FROM django_session WHERE session_key=%s','params':[buyer.cookies[settings.SESSION_COOKIE_NAME].value],'expected':[[1]]},
    ]
    assert_committed_postgresql_rows(checks)
    restored = client()
    restored.cookies = buyer.cookies
    assert restored.get('/api/auth/session/').data['user']['name'] == 'Persisted Buyer'
    assert restored.get('/api/cart/').data[0]['quantity'] == 2
    assert product_id in restored.get('/api/wishlist/').data
    from pathlib import Path
    photo = Product.objects.get(pk=product_id).pictures.get()
    assert Path(photo.image.path).is_file()
    with Image.open(photo.image.path) as saved:
        assert saved.size == (64,64) and saved.format == 'JPEG'


@pytest.mark.django_db(transaction=True)
def test_postgresql_order_payment_and_idempotency_persist_across_processes(data):
    from django.db import connection
    if connection.vendor != 'postgresql':
        pytest.skip('PostgreSQL persistence verification requires a real database.')
    api = client(data['customer'])
    payload = order_payload(data, 2)
    assert api.put('/api/cart/', payload['items'], format='json').status_code == 200
    created = api.post('/api/orders/', payload, format='json')
    assert created.status_code == 201
    payment = api.post('/api/payments/', {'order_id':created.data['id'],'provider':'mock'}, format='json')
    assert payment.status_code == 200
    verify_url = f'/api/payments/{payment.data["id"]}/verify/'
    assert api.post(verify_url, {'mock_outcome':'SUCCEEDED'}, format='json').status_code == 200
    checks = [
        {'sql':"SELECT payment_status, subtotal, total, address->>'street' FROM orders_order WHERE id=%s",'params':[created.data['id']],'expected':[['SUCCEEDED','200.00','200.00','10 Main Street']]},
        {'sql':'SELECT quantity, price FROM orders_orderitem WHERE order_id=%s','params':[created.data['id']],'expected':[[2,'100.00']]},
        {'sql':'SELECT stock FROM products_product WHERE id=%s','params':[data['products'][0].id],'expected':[[8]]},
        {'sql':'SELECT provider, status, amount FROM payments_payment WHERE order_id=%s','params':[created.data['id']],'expected':[['mock','SUCCEEDED','200.00']]},
        {'sql':'SELECT COUNT(*) FROM carts_cartitem WHERE user_id=%s','params':[data['customer'].id],'expected':[[0]]},
        {'sql':'SELECT COUNT(*) FROM orders_order WHERE user_id=%s','params':[data['customer'].id],'expected':[[1]]},
        {'sql':'SELECT COUNT(*) FROM payments_payment WHERE order_id=%s','params':[created.data['id']],'expected':[[1]]},
    ]
    assert_committed_postgresql_rows(checks)
    assert api.get(f'/api/orders/{created.data["id"]}/').data['payment_status'] == 'SUCCEEDED'
    repeated = api.post('/api/orders/', payload, format='json')
    assert repeated.status_code == 201 and repeated.data['id'] == created.data['id']
    assert api.post(verify_url, {'mock_outcome':'SUCCEEDED'}, format='json').status_code == 200
    assert_committed_postgresql_rows(checks)


@pytest.mark.django_db(transaction=True)
def test_postgresql_failed_checkout_rolls_back_across_processes(data):
    from django.db import connection
    if connection.vendor != 'postgresql':
        pytest.skip('PostgreSQL persistence verification requires a real database.')
    api = client(data['customer'])
    payload = order_payload(data, 2)
    assert api.put('/api/cart/', payload['items'], format='json').status_code == 200
    with patch('orders.services.notify', side_effect=RuntimeError('Injected test-only checkout failure')):
        failed = api.post('/api/orders/', payload, format='json')
    assert failed.status_code == 500 and failed.data['error']['status'] == 500
    assert_committed_postgresql_rows([
        {'sql':'SELECT stock FROM products_product WHERE id=%s','params':[data['products'][0].id],'expected':[[10]]},
        {'sql':'SELECT quantity FROM carts_cartitem WHERE user_id=%s','params':[data['customer'].id],'expected':[[2]]},
        {'sql':'SELECT COUNT(*) FROM orders_order WHERE user_id=%s','params':[data['customer'].id],'expected':[[0]]},
        {'sql':'SELECT COUNT(*) FROM orders_orderitem','params':[],'expected':[[0]]},
        {'sql':'SELECT COUNT(*) FROM payments_payment','params':[],'expected':[[0]]},
    ])
