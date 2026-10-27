class SecurityHeaders:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        response = self.get_response(request)
        response['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; script-src 'self' https://cdn.jsdelivr.net"
        if request.path.startswith('/api/docs/'):
            response['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://cdn.jsdelivr.net; frame-ancestors 'none'"
        if request.path.startswith('/api/'):
            response['Cache-Control'] = 'no-store'
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        return response
