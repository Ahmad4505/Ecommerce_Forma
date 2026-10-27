from django.http import JsonResponse
from django.shortcuts import render
from rest_framework.views import exception_handler as drf_handler
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models.deletion import ProtectedError
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
import logging

def exception_handler(exc, context):
    if isinstance(exc,DjangoValidationError):
        exc = ValidationError(exc.messages)
    if isinstance(exc,ProtectedError):
        from orders.services import Conflict
        exc = Conflict('This record is referenced by existing commerce records and cannot be deleted.')
    response = drf_handler(exc, context)
    if response is None:
        logging.getLogger(__name__).error('Unhandled API exception', exc_info=(type(exc), exc, exc.__traceback__))
        return Response({'error': {'status': 500, 'details': 'The request could not be completed. Please try again shortly.'}}, status=500)
    if response is not None:
        response.data = {'error': {'status': response.status_code, 'details': response.data}}
    return response

def csrf_failure(request, reason=''):
    return JsonResponse({'error': {'status': 403, 'details': 'CSRF verification failed. Refresh and retry.'}}, status=403)

def server_error(request, exception=None, status=500):
    if request.path.startswith('/api/'):
        return JsonResponse({'error': {'status': status, 'details': 'The request could not be completed.'}}, status=status)
    return render(request, 'error.html', {'status': status}, status=status)

def bad_request(request, exception=None):
    return server_error(request, status=400)
def forbidden(request, exception=None):
    return server_error(request, status=403)
def not_found(request, exception=None):
    return server_error(request, status=404)
