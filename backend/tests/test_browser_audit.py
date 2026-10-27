"""Opt-in browser audit using pytest's disposable database, never development records."""
import io
import json
import os
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen

import pytest
from django.core.management import call_command


@pytest.mark.skipif(os.environ.get('RUN_BROWSER_AUDIT') != '1', reason='Opt-in disposable browser audit')
@pytest.mark.django_db(transaction=True)
def test_disposable_browser_audit(live_server, settings, monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[2]
    scope = os.environ.get('BROWSER_AUDIT_SCOPE', 'full')
    assert scope in {'full', 'products', 'checkout', 'navigation', 'console', 'mobile'}, 'Unsupported browser audit scope'
    frontend = 'http://localhost:5177'
    settings.CORS_ALLOWED_ORIGINS = [frontend]
    settings.CSRF_TRUSTED_ORIGINS = [frontend]
    settings.FRONTEND_URL = frontend
    settings.MEDIA_ROOT = tmp_path / 'media'
    settings.DEBUG = True
    from PIL import Image
    audit_image = tmp_path / 'audit.png'
    Image.new('RGB', (64, 64), color='green').save(audit_image)
    output = io.StringIO()
    call_command('seed_demo', stdout=output)
    if scope == 'checkout':
        from products.models import Product
        initial_stock = dict(Product.objects.values_list('pk', 'stock'))
    credential_file = tmp_path / 'browser-credentials.txt'
    credential_file.write_text(output.getvalue(), encoding='utf-8')
    from django.core import mail
    from core import notifications
    mailbox_file = tmp_path / 'mailbox.json'
    mailbox_file.write_text('[]', encoding='utf-8')
    original_send = notifications.send_mail
    def capture_mail(*args, **kwargs):
        result = original_send(*args, **kwargs)
        mailbox_file.write_text(json.dumps([{'to': message.to, 'body': message.body, 'subject': message.subject} for message in mail.outbox]), encoding='utf-8')
        return result
    monkeypatch.setattr(notifications, 'send_mail', capture_mail)
    env = {**os.environ, 'VITE_API_BASE_URL': live_server.url + '/api/',
           'FRONTEND_TEST_URL': frontend, 'BACKEND_TEST_URL': live_server.url, 'DEMO_CREDENTIALS_FILE': str(credential_file),
           'DISPOSABLE_BROWSER_AUDIT': '1', 'AUDIT_IMAGE': str(audit_image), 'AUDIT_MAILBOX_FILE': str(mailbox_file)}
    if scope == 'console':
        env['CONSOLE_AUDIT_REPORT'] = str(root / '.functional-audit-results' / 'console-report.json')
    log = (tmp_path / 'vite.log').open('w', encoding='utf-8')
    server = subprocess.Popen(['node', '--preserve-symlinks', '--preserve-symlinks-main',
        'scripts/forma-run.mjs', 'dev', '--host', '127.0.0.1', '--port', '5177'],
        cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        for attempt in range(60):
            if server.poll() is not None:
                pytest.fail('Isolated Vite server exited; inspect test temporary vite.log')
            try:
                with urlopen(frontend, timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(.5)
        log_name = 'browser-run.log' if scope == 'full' else f'{scope}-run.log'
        run_log = root / '.functional-audit-results' / log_name
        run_log.parent.mkdir(exist_ok=True)
        with run_log.open('w', encoding='utf-8') as browser_log:
            command = ['node', '--preserve-symlinks', '--preserve-symlinks-main',
                'node_modules/@playwright/test/cli.js', 'test', '--config', 'playwright.audit.config.js']
            if scope == 'products':
                command += ['--grep', 'disposable vendor product upload|disposable admin product CRUD|vendor SPA navigation resets']
            elif scope == 'checkout':
                command += ['--grep', 'public routes, search, product details, guest bag and protected checkout|disposable customer profile, preferences, address, wishlist, cart and mock checkout|disposable login merges saved and guest bags']
            elif scope == 'navigation':
                command += ['navigation.spec.js', 'recovery.spec.js', 'z-auth-followup.spec.js']
            elif scope == 'mobile':
                command += ['zz-mobile-flows.spec.js']
            elif scope == 'console':
                command = ['node', '--preserve-symlinks', '--preserve-symlinks-main', 'tests/audit-console.mjs']
            result = subprocess.run(command,
                cwd=root, env=env, stdout=browser_log, stderr=subprocess.STDOUT, timeout=900)
        assert result.returncode == 0, run_log.read_text(encoding='utf-8')
        if scope == 'console':
            report = json.loads(Path(env['CONSOLE_AUDIT_REPORT']).read_text(encoding='utf-8'))
            assert report['visited'] and not report['failures']
            return
        from accounts.models import User
        from products.models import Product
        from core.models import ContactMessage, NewsletterSubscriber
        from orders.models import Order
        from vendors.models import Vendor
        if scope == 'mobile':
            from accounts.models import Address
            buyer = User.objects.get(email='customer@ecommerce.test')
            assert Address.objects.filter(user=buyer, label='Mobile Home', street='45 Mobile Avenue').exists()
            product = Product.objects.get(name='Mobile Audit Stool')
            assert str(product.price) == '99.00' and product.vendor.user.email == 'vendor@ecommerce.test'
            assert product.pictures.count() == 1 and Path(product.pictures.get().image.path).is_file()
            assert Vendor.objects.get(user__email='mobile.pending@ecommerce.test').status == 'APPROVED'
            order = Order.objects.get(user=buyer, address__street='51 Mobile Checkout Street')
            assert order.payment_status == 'SUCCEEDED' and order.payment.provider == 'mock'
            assert order.payment.status == 'SUCCEEDED' and order.payment.amount == order.total
            retry_order = Order.objects.get(user=buyer, address__street='52 Mobile Payment Retry Street')
            assert retry_order.payment_status == 'SUCCEEDED' and retry_order.payment.provider == 'mock'
            assert retry_order.payment.status == 'SUCCEEDED' and retry_order.payment.amount == retry_order.total
            return
        if scope == 'navigation':
            assert Vendor.objects.get(user__email='pending.vendor@ecommerce.test').status == 'PENDING'
            activated = User.objects.get(email='audit.activation@ecommerce.test')
            assert activated.email_verified and activated.check_password('New-reset-only-password-4839!')
            return
        if scope == 'checkout':
            from carts.models import CartItem
            from decimal import Decimal
            buyer = User.objects.get(email='customer@ecommerce.test')
            order = Order.objects.get(user=buyer, address__street='10 Audit Street')
            assert order.payment_status == 'SUCCEEDED'
            assert order.payment.provider == 'mock' and order.payment.status == 'SUCCEEDED'
            assert order.payment.amount == order.total and order.payment.currency == order.currency
            lines = list(order.items.select_related('product'))
            assert lines and order.subtotal == sum((line.price * line.quantity for line in lines), Decimal('0'))
            assert order.total == order.subtotal - order.discount + order.shipping
            for product_id in {line.product_id for line in lines}:
                quantity = sum(line.quantity for line in lines if line.product_id == product_id)
                assert Product.objects.get(pk=product_id).stock == initial_stock[product_id] - quantity
            saved_cart = list(CartItem.objects.filter(user=buyer))
            assert len(saved_cart) == 1 and saved_cart[0].quantity == 3
            return
        if scope == 'products':
            for name, price in [('Audit Walnut Stool', '135.00'), ('Audit Admin Product', '85.00')]:
                product = Product.objects.get(name=name)
                assert str(product.price) == price and product.status == 'ARCHIVED'
                assert product.pictures.count() == 1
                assert Path(product.pictures.get().image.path).is_file()
            vendor_product = Product.objects.get(name='Audit Walnut Stool')
            assert vendor_product.vendor.user.email == 'vendor@ecommerce.test'
            assert vendor_product.stock == 4
            return
        buyer = User.objects.get(email='customer@ecommerce.test')
        assert buyer.name == 'Audit Buyer' and not buyer.newsletter_notifications
        archived = Product.objects.get(name='Audit Walnut Stool')
        assert archived.status == 'ARCHIVED' and archived.stock == 4
        assert archived.pictures.count() == 1 and Path(archived.pictures.get().image.path).exists()
        assert Order.objects.filter(user=buyer, address__street='10 Audit Street', payment_status='SUCCEEDED').exists()
        assert Vendor.objects.get(user__email='pending.vendor@ecommerce.test').status == 'SUSPENDED'
        assert ContactMessage.objects.filter(email='audit.contact@ecommerce.test').exists()
        assert NewsletterSubscriber.objects.filter(email='audit.newsletter@ecommerce.test').exists()
        assert User.objects.get(email='audit.registration@ecommerce.test').email_verified is False
        activated = User.objects.get(email='audit.activation@ecommerce.test')
        assert activated.email_verified and activated.check_password('New-reset-only-password-4839!')

    finally:
        server.terminate()
        server.wait(timeout=20)
        log.close()
