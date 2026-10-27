from django.db import connection
from django.core.cache import cache
from django.http import JsonResponse

def readiness(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        cache.set('readiness',True,10)
        if cache.get('readiness') is not True:
            raise RuntimeError()
    except Exception:
        return JsonResponse({'status':'unavailable'},status=503)
    return JsonResponse({'status':'ok'})
