from .test_settings import *
DATABASES = {'default': env.db('DATABASE_URL')}
