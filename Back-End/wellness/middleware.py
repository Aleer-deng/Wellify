from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse


class SecurityPolicyMiddleware:
    """Reject unsupported uploads and throttle Django/allauth HTML login paths."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in {'POST', 'PUT', 'PATCH'}:
            try:
                size = int(request.META.get('CONTENT_LENGTH') or 0)
            except ValueError:
                return HttpResponse('Invalid content length.', status=400)
            if size < 0:
                return HttpResponse('Invalid content length.', status=400)
            if size > settings.DATA_UPLOAD_MAX_MEMORY_SIZE:
                return HttpResponse('Request is too large.', status=413)
            if request.content_type == 'multipart/form-data' and request.FILES:
                return HttpResponse('File uploads are not supported.', status=415)
            if request.path in {'/admin/login/', '/api/v1/auth/social/login/', '/auth/password-reset/'} or request.path.startswith('/auth/reset/'):
                # REMOTE_ADDR is supplied by the server; do not trust client forwarding headers.
                key = 'html-login:' + request.META.get('REMOTE_ADDR', '')
                if not cache.add(key, 1, 60):
                    try:
                        attempts = cache.incr(key)
                    except ValueError:  # Entry expired between add and increment.
                        cache.add(key, 1, 60)
                        attempts = 1
                    if attempts > 10:
                        response = HttpResponse('Too many login attempts.', status=429)
                        response['Retry-After'] = '60'
                        return response
        response = self.get_response(request)
        # Django admin needs inline styling; scripts remain same-origin only.
        response['Content-Security-Policy'] = (
            "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "form-action 'self' https://accounts.google.com https://appleid.apple.com "
            "https://login.microsoftonline.com; base-uri 'none'; frame-ancestors 'none'"
        )
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        if request.path.startswith(('/api/', '/admin/', '/auth/')):
            response['Cache-Control'] = 'no-store, private'
        return response
