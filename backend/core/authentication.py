from rest_framework.authentication import SessionAuthentication

class BrowserSessionAuthentication(SessionAuthentication):
    def authenticate_header(self, request):
        return 'Session'

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from django.conf import settings

class SessionSchema(OpenApiAuthenticationExtension):
    target_class = 'core.authentication.BrowserSessionAuthentication'
    name = 'cookieAuth'
    def get_security_definition(self, auto_schema):
        return {'type':'apiKey','in':'cookie','name':settings.SESSION_COOKIE_NAME,
            'description':'Django HttpOnly session. Unsafe requests also require X-CSRFToken from /api/auth/csrf/.'}
