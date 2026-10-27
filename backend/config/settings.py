from pathlib import Path
import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / '.env')
DEBUG = env('DEBUG')
SECRET_KEY = env('DJANGO_SECRET_KEY')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])
INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'rest_framework', 'django_filters', 'corsheaders', 'drf_spectacular',
    'accounts', 'vendors', 'categories', 'products', 'carts', 'orders',
    'payments', 'reviews', 'promotions', 'core',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware', 'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.SecurityHeaders',
]
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates',
              'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True,
              'OPTIONS': {'context_processors': ['django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']}}]
DATABASES = {'default': env.db('DATABASE_URL', default='postgresql://ecommerce@localhost:5432/ecommerce')}
AUTH_USER_MODEL = 'accounts.User'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'core.password_validation.NonBlankPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
PASSWORD_RESET_TIMEOUT = 3600
FRONTEND_URL = env('FRONTEND_URL', default='http://localhost:5175')
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[FRONTEND_URL])
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[FRONTEND_URL])
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_AGE = 86400
SECURE_SSL_REDIRECT = not DEBUG
if env.bool('TRUST_PROXY',default=False):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO','https')
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
X_FRAME_OPTIONS = 'DENY'
CSRF_FAILURE_VIEW = 'core.errors.csrf_failure'
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
USE_TZ = True
TIME_ZONE = 'UTC'
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['core.authentication.BrowserSessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend', 'rest_framework.filters.SearchFilter', 'rest_framework.filters.OrderingFilter'],
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.BoundedPagination', 'PAGE_SIZE': 24,
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.AnonRateThrottle', 'rest_framework.throttling.UserRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {'anon': '120/min', 'user': '600/min', 'auth': '10/min',
        'checkout':'30/hour','payment':'60/hour','upload':'60/hour','public_forms':'20/hour'},
    'EXCEPTION_HANDLER': 'core.errors.exception_handler',
}
REDIS_URL = env('REDIS_URL', default='')
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': REDIS_URL}} if REDIS_URL else {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
if not DEBUG and not REDIS_URL:
    raise ImproperlyConfigured('REDIS_URL is required in production for shared throttling and cache.')
CELERY_BROKER_URL = REDIS_URL
# Keep the existing environment interface while using Django 6.1 mailers.
mail_backend = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
MAILERS = {'default': {'BACKEND': mail_backend}}
if mail_backend == 'django.core.mail.backends.smtp.EmailBackend':
    MAILERS['default']['OPTIONS'] = {
        'host': env('EMAIL_HOST', default='localhost'),
        'port': env.int('EMAIL_PORT', default=587),
        'username': env('EMAIL_HOST_USER', default=''),
        'password': env('EMAIL_HOST_PASSWORD', default=''),
        'use_tls': env.bool('EMAIL_USE_TLS', default=True),
        'timeout': env.int('EMAIL_TIMEOUT', default=10),
    }
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@ecommerce.test')
ADMIN_EMAIL = env('ADMIN_EMAIL', default='admin@ecommerce.test')
SETTLEMENT_CURRENCY = env('SETTLEMENT_CURRENCY', default='USD')
MOCK_PAYMENTS_ENABLED = DEBUG and env.bool('MOCK_PAYMENTS_ENABLED', default=False)
ENABLED_PAYMENT_PROVIDERS = env.list('ENABLED_PAYMENT_PROVIDERS', default=[])
PAYMENT_CONFIG = {key: env(key, default='') for key in [
    'PAYPAL_CLIENT_ID', 'PAYPAL_SECRET', 'PAYPAL_WEBHOOK_ID', 'CHECKOUT_SECRET',
    'CHECKOUT_BASE_URL', 'CHECKOUT_WEBHOOK_SECRET', 'HYPERPAY_TOKEN',
    'HYPERPAY_ENTITY_ID', 'HYPERPAY_WEBHOOK_KEY']}
SPECTACULAR_SETTINGS = {'TITLE': 'Forma Marketplace API', 'VERSION': '1.0.0',
    'SERVE_PERMISSIONS': ['rest_framework.permissions.AllowAny' if DEBUG else 'core.permissions.PlatformAdmin'],
    'SERVE_INCLUDE_SCHEMA': False}
