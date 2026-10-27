"""Explicit, disposable SQLite browser-test settings. Never use for development data or deployment."""
from .test_settings import *
DATABASES = {'default': {'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR.parent/'.setup/backend-smoke.sqlite3'}}
MAILERS = {'default': {'BACKEND': 'django.core.mail.backends.console.EmailBackend'}}
