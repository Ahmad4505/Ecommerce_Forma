"""Sandbox-only hosted payment adapters. No card data enters this application."""
import hashlib
import hmac
import json
import re
from decimal import Decimal
from urllib.parse import quote
import requests
from django.conf import settings
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

class ProviderUnavailable(APIException):
    status_code = 503
    default_detail = 'This payment provider is not configured.'

def available_providers():
    required = {
        'paypal': ['PAYPAL_CLIENT_ID', 'PAYPAL_SECRET', 'PAYPAL_WEBHOOK_ID'],
        'checkout': ['CHECKOUT_SECRET', 'CHECKOUT_BASE_URL', 'CHECKOUT_WEBHOOK_SECRET'],
    }
    return {
        'mock': settings.MOCK_PAYMENTS_ENABLED,
        **{name: name in settings.ENABLED_PAYMENT_PROVIDERS and all(settings.PAYMENT_CONFIG.get(key) for key in keys)
           for name, keys in required.items()},
        # Widget/webhook integration still requires sandbox verification.
        'hyperpay': False,
    }

def api(method, url, **kwargs):
    try:
        response = requests.request(method, url, timeout=20, **kwargs)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError):
        raise ProviderUnavailable('Payment provider could not complete the request. Retry with the same payment.')

class PayPal:
    base = 'https://api-m.sandbox.paypal.com'
    def __init__(self):
        self.config = settings.PAYMENT_CONFIG
        if not all(self.config[k] for k in ['PAYPAL_CLIENT_ID','PAYPAL_SECRET','PAYPAL_WEBHOOK_ID']):
            raise ProviderUnavailable()
        token = api('POST', self.base+'/v1/oauth2/token', auth=(self.config['PAYPAL_CLIENT_ID'],self.config['PAYPAL_SECRET']), data={'grant_type':'client_credentials'})
        self.headers = {'Authorization': 'Bearer '+token['access_token'], 'Content-Type':'application/json'}
    def create(self, payment):
        data = api('POST', self.base+'/v2/checkout/orders', headers={**self.headers,'PayPal-Request-Id':str(payment.id)}, json={
            'intent':'CAPTURE', 'purchase_units':[{'reference_id':str(payment.id), 'custom_id':str(payment.id),
                'amount':{'currency_code':payment.currency,'value':str(payment.amount)}}],
            'payment_source':{'paypal':{'experience_context':{'return_url':settings.FRONTEND_URL+'/account/orders/'+str(payment.order_id),
                'cancel_url':settings.FRONTEND_URL+'/cart','user_action':'PAY_NOW'}}}})
        return data['id'], next(x['href'] for x in data['links'] if x['rel'] in ['payer-action','approve'])
    def verify(self, payment, gateway_id=None):
        data = api('GET', self.base+'/v2/checkout/orders/'+quote(payment.reference, safe=''), headers=self.headers)
        if data['status'] == 'APPROVED':
            data = api('POST', self.base+'/v2/checkout/orders/'+quote(payment.reference,safe='')+'/capture', headers={**self.headers,'PayPal-Request-Id':str(payment.id)+'-capture'}, json={})
        unit = data['purchase_units'][0]
        captures = unit.get('payments',{}).get('captures',[])
        if not captures:
            return None
        capture = captures[0]
        if unit.get('custom_id') != str(payment.id) or capture['amount']['currency_code'] != payment.currency or Decimal(capture['amount']['value']) != payment.amount:
            raise ValidationError('Payment details do not match the order.')
        return ('SUCCEEDED', capture['id']) if capture['status'] == 'COMPLETED' else None
    def webhook(self, request):
        event = request.data
        headers = request.headers
        verified = api('POST',self.base+'/v1/notifications/verify-webhook-signature',headers=self.headers,json={
            'auth_algo':headers.get('PAYPAL-AUTH-ALGO'), 'cert_url':headers.get('PAYPAL-CERT-URL'),
            'transmission_id':headers.get('PAYPAL-TRANSMISSION-ID'), 'transmission_sig':headers.get('PAYPAL-TRANSMISSION-SIG'),
            'transmission_time':headers.get('PAYPAL-TRANSMISSION-TIME'), 'webhook_id':self.config['PAYPAL_WEBHOOK_ID'],'webhook_event':event})
        if verified.get('verification_status') != 'SUCCESS':
            raise PermissionDenied('Invalid webhook signature.')
        reference = event.get('resource',{}).get('supplementary_data',{}).get('related_ids',{}).get('order_id')
        return str(event.get('id','')), reference
    def refund(self, payment, amount, key):
        return api('POST',self.base+'/v2/payments/captures/'+quote(payment.capture_id,safe='')+'/refund',headers={**self.headers,'PayPal-Request-Id':key},json={'amount':{'value':str(amount),'currency_code':payment.currency}})
    def refund_status(self, refund):
        result=api('GET',self.base+'/v2/payments/refunds/'+quote(refund.reference,safe=''),headers=self.headers)
        if result['amount']['currency_code']!=refund.payment.currency or Decimal(result['amount']['value'])!=refund.amount:
            raise ValidationError('Refund details do not match.')
        return 'SUCCEEDED' if result['status']=='COMPLETED' else 'FAILED' if result['status'] in ['FAILED','CANCELLED'] else 'PENDING'

class Checkout:
    def __init__(self):
        config = settings.PAYMENT_CONFIG
        self.base = config['CHECKOUT_BASE_URL'].rstrip('/')
        if not re.fullmatch(r'https://[a-z0-9]+\.api\.sandbox\.checkout\.com', self.base) or not config['CHECKOUT_SECRET'] or not config['CHECKOUT_WEBHOOK_SECRET']:
            raise ProviderUnavailable()
        self.headers = {'Authorization':config['CHECKOUT_SECRET']}
        self.secret = config['CHECKOUT_WEBHOOK_SECRET']
    def create(self, payment):
        # Only two-decimal settlement currencies are currently enabled by the service.
        address = payment.order.address
        data = api('POST',self.base+'/hosted-payments',headers={**self.headers,'Cko-Idempotency-Key':str(payment.id)},json={
            'amount':int(payment.amount*100),'currency':payment.currency,'reference':str(payment.id), 'capture':True,
            'billing':{'address':{'address_line1':address['street'],'city':address['city'],'zip':address['zip'],'country':address.get('country_code','US')}},
            'success_url':settings.FRONTEND_URL+'/account/orders/'+str(payment.order_id),
            'cancel_url':settings.FRONTEND_URL+'/cart','failure_url':settings.FRONTEND_URL+'/cart'})
        return data['id'], data['_links']['redirect']['href']
    def verify(self, payment, gateway_id=None):
        data = api('GET',self.base+'/hosted-payments/'+quote(payment.reference,safe=''),headers=self.headers) if not gateway_id else {}
        # Resolve the gateway payment from the trusted hosted-session response.
        payment_id = gateway_id or data.get('payment_id') or data.get('payment',{}).get('id')
        if not payment_id:
            return None
        result = api('GET',self.base+'/payments/'+quote(payment_id,safe=''),headers=self.headers)
        if result.get('reference') != str(payment.id) or result['currency'] != payment.currency or Decimal(result['amount']) != payment.amount*100:
            raise ValidationError('Payment details do not match.')
        return ('SUCCEEDED',payment_id) if result['status'] == 'Captured' else None
    def webhook(self, request):
        expected = hmac.new(self.secret.encode(), request.body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,request.headers.get('Cko-Signature','')):
            raise PermissionDenied('Invalid webhook signature.')
        event = request.data
        return str(event.get('id','')), event.get('data',{}).get('reference'), event.get('data',{}).get('id')
    def refund(self, payment, amount, key):
        return api('POST', self.base+'/payments/'+quote(payment.capture_id,safe='')+'/refunds',headers={**self.headers,'Cko-Idempotency-Key':key},json={'amount':int(amount*100),'reference':key})
    def refund_status(self, refund):
        details=api('GET',self.base+'/payments/'+quote(refund.payment.capture_id,safe=''),headers=self.headers)
        if details.get('currency')!=refund.payment.currency:
            raise ValidationError('Refund currency does not match.')
        actions=api('GET',self.base+'/payments/'+quote(refund.payment.capture_id,safe='')+'/actions',headers=self.headers)
        action=next((a for a in actions if a.get('id')==refund.reference and a.get('type','').lower()=='refund'),None)
        if not action:
            return 'PENDING'
        if Decimal(action.get('amount',0))!=refund.amount*100:
            raise ValidationError('Refund amount does not match.')
        return 'SUCCEEDED' if action.get('approved') is True else 'FAILED' if action.get('approved') is False else 'PENDING'

class HyperPay:
    base = 'https://eu-test.oppwa.com'
    def __init__(self):
        config = settings.PAYMENT_CONFIG
        if not config['HYPERPAY_TOKEN'] or not config['HYPERPAY_ENTITY_ID']:
            raise ProviderUnavailable()
        self.headers = {'Authorization':'Bearer '+config['HYPERPAY_TOKEN']}
        self.entity = config['HYPERPAY_ENTITY_ID']
    def create(self, payment):
        data = api('POST',self.base+'/v1/checkouts',headers=self.headers,data={
            'entityId':self.entity,'amount':str(payment.amount),'currency':payment.currency,
            'paymentType':'DB','merchantTransactionId':str(payment.id), 'testMode':'EXTERNAL'})
        # The frontend hosts the provider widget; raw card data goes directly to HyperPay.
        return data['id'], settings.FRONTEND_URL+'/payment/hyperpay/'+str(payment.id)
    def verify(self, payment, gateway_id=None):
        result = api('GET',self.base+'/v1/checkouts/'+quote(payment.reference,safe='')+'/payment',headers=self.headers,params={'entityId':self.entity})
        if result.get('merchantTransactionId') != str(payment.id) or result.get('currency') != payment.currency or Decimal(result.get('amount','0')) != payment.amount:
            raise ValidationError('Payment details do not match.')
        # Do not accept 000.200 pending / test-review result families as payment proof.
        return ('SUCCEEDED',result['id']) if re.fullmatch(r'000\.(000\.|100\.1|3)\d+', result.get('result',{}).get('code','')) else None
    def webhook(self, request):
        # HyperPay contracts differ: fail closed until merchant-specific encrypted webhook
        # specification is supplied and validated. Shopper callbacks use server API verify.
        raise ProviderUnavailable('HyperPay webhooks require merchant-specific encryption configuration and sandbox validation.')
    def refund(self, payment, amount, key):
        return api('POST',self.base+'/v1/payments/'+quote(payment.capture_id,safe=''),headers=self.headers,data={
            'entityId':self.entity,'amount':str(amount),'currency':payment.currency,'paymentType':'RF','merchantTransactionId':key})
    def refund_status(self, refund):
        result=api('GET',self.base+'/v1/payments/'+quote(refund.reference,safe=''),headers=self.headers,params={'entityId':self.entity})
        if result.get('paymentType')!='RF' or result.get('currency')!=refund.payment.currency or Decimal(result.get('amount',0))!=refund.amount:
            raise ValidationError('Refund details do not match.')
        return 'SUCCEEDED' if result.get('result',{}).get('code')=='000.000.000' else 'PENDING'

def adapter(provider):
    if provider == 'hyperpay':
        raise ProviderUnavailable('HyperPay is unavailable until its payment verification integration is complete.')
    if provider not in settings.ENABLED_PAYMENT_PROVIDERS:
        raise ProviderUnavailable()
    classes = {'paypal':PayPal,'checkout':Checkout,'hyperpay':HyperPay}
    if provider not in classes:
        raise ValidationError('Unknown provider.')
    return classes[provider]()
