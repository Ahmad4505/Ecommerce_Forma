import json
import os
import secrets
import uuid
from decimal import Decimal
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify
from accounts.models import User
from vendors.models import Vendor
from categories.models import Category
from products.models import Product, ProductImage
from orders.models import Order, OrderItem
from payments.models import Payment
from reviews.models import Review
from promotions.models import Promotion, Banner
from core.models import PlatformSettings

class Command(BaseCommand):
    help = 'Idempotent local demo catalog. New account passwords printed once; existing passwords unchanged.'
    @transaction.atomic
    def handle(self, *args, **kwargs):
        if not settings.DEBUG:
            raise CommandError('Demo seeding is disabled outside DEBUG development.')
        catalog = json.loads((Path(__file__).resolve().parents[2]/'seed/catalog.json').read_text(encoding='utf-8'))
        accounts = {}
        for key, email, role in [('ADMIN','admin@ecommerce.test','ADMIN'),('VENDOR','vendor@ecommerce.test','VENDOR'),
                ('CUSTOMER','customer@ecommerce.test','CUSTOMER'),('PENDING','pending.vendor@ecommerce.test','VENDOR')]:
            user = User.objects.filter(email=email).first()
            if not user:
                password = os.environ.get('DEMO_'+key+'_PASSWORD') or secrets.token_urlsafe(18)
                user = User.objects.create_user(email,password,name=key.title()+' Demo',role=role,email_verified=True,
                    is_staff=role=='ADMIN',is_superuser=role=='ADMIN')
                self.stdout.write(f'NEW LOCAL ACCOUNT {email} password: {password}')
            accounts[key] = user
        stores = []
        for index, source in enumerate(catalog['vendors']):
            if index == 0:
                owner = accounts['VENDOR']
            else:
                owner,created = User.objects.get_or_create(email=f'studio{index+1}@ecommerce.test',defaults={'name':source['name'],'role':'VENDOR','email_verified':True})
                if created:
                    owner.set_unusable_password()
                    owner.save(update_fields=['password'])
            store,_ = Vendor.objects.get_or_create(user=owner,defaults={'name':source['name'],'description':source['description'],
                'phone':'+1 555 010 1000','location':source['location'],'status':'APPROVED'})
            stores.append(store)
        Vendor.objects.get_or_create(user=accounts['PENDING'],defaults={'name':'Pending Studio','description':'A new independent design studio awaiting review.',
            'phone':'+1 555 010 2000','location':'10 Design Lane, Portland','status':'PENDING'})
        categories = {}
        for name in catalog['categories']+['Kitchen & Dining','Textiles']:
            categories[name],_ = Category.objects.get_or_create(name=name,defaults={'slug':slugify(name)})
        sources = list(catalog['products'])
        # Twenty distinct size/finish editions of photographed product types.
        for i, source in enumerate(catalog['products'][:20]):
            variant = {**source,'id':f'edition-{i}', 'name':source['name']+' — Studio Edition',
                'slug':source['slug']+'-studio-edition','sku':source['sku']+'-ST', 'price':source['price']+15,'discountPrice':None}
            if source['name'] in ['Stoneware Coffee Cup','Textured Ceramic Bowl']:
                variant['category'] = 'Kitchen & Dining'
            if 'Cushion' in source['name']:
                variant['category'] = 'Textiles'
            sources.append(variant)
        products = []
        for i, source in enumerate(sources):
            product,_ = Product.objects.get_or_create(sku=source['sku'],defaults={'name':source['name'],'slug':slugify(source['slug']),
                'vendor':stores[i%5], 'category':categories[source['category']], 'description':source['description'],
                'price':source['price'],'discount_price':source['discountPrice'],'stock':source['stock'],'featured':i<8})
            # Reuse locally cached Unsplash photography; never fetch user-supplied URLs.
            image = source['images'][0]
            ProductImage.objects.get_or_create(product=product,source_url=image,defaults={
                'attribution':'Unsplash photograph; source ID '+Path(image).stem+'; https://unsplash.com/license'})
            products.append(product)
        customer = accounts['CUSTOMER']
        order,_ = Order.objects.get_or_create(user=customer,idempotency_key=uuid.UUID('72b05457-9fa1-4ee5-9614-bf093db445b2'),
            defaults={'request_hash':'seed','status':'Delivered','payment_status':'SUCCEEDED','subtotal':products[0].effective_price,
                'shipping':0,'total':products[0].effective_price,'currency':'USD',
                'address':{'name':customer.name,'street':'28 Garden Street','city':'Portland','zip':'97201','country':'United States'}})
        for product in products[:10]:
            OrderItem.objects.get_or_create(order=order,product=product,defaults={'vendor':product.vendor,'name':product.name,
                'price':product.effective_price,'quantity':1,'fulfillment':'Delivered'})
            Review.objects.get_or_create(user=customer,product=product,defaults={'rating':5,'text':'Carefully finished and beautifully made. A lovely addition to our home.'})
        total = sum(i.price*i.quantity for i in order.items.all())
        order.subtotal=order.total=total
        order.save(update_fields=['subtotal','total'])
        Payment.objects.get_or_create(order=order,defaults={'provider':'mock','reference':'seed-local-order','status':'SUCCEEDED','amount':total,'currency':'USD'})
        Promotion.objects.get_or_create(code='WELCOME10',defaults={'percent':10})
        Banner.objects.get_or_create(title='Good design. Better living.',defaults={'subtitle':'Independent brands. Objects made to last.'})
        PlatformSettings.objects.get_or_create(pk=1)
        self.stdout.write(self.style.SUCCESS(f'Demo catalog ready: {Product.objects.count()} products, {Category.objects.count()} categories. Existing records/passwords preserved.'))
