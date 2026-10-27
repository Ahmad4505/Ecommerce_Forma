import os
os.environ.setdefault('DJANGO_SECRET_KEY', 'test-only-key-never-used-for-deployment')
os.environ.setdefault('DEBUG', 'True')
from .settings import *
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
MAILERS = {'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
MOCK_PAYMENTS_ENABLED = True
REST_FRAMEWORK = {**REST_FRAMEWORK, 'DEFAULT_THROTTLE_RATES': {**REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'], 'anon': '10000/min', 'user': '10000/min', 'auth': '1000/min'}}
