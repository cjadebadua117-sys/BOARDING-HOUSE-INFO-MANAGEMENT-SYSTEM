"""
BHIMS security middleware.

1. SecurityHeadersMiddleware — adds the browser-hardening headers that Django
   does not set natively:
       Content-Security-Policy   blocks injected third-party scripts (XSS)
       Referrer-Policy           stops URL leakage to external sites
       Permissions-Policy        disables camera/mic/geolocation access
   Django already provides X-FrameOptions (DENY) and, in production,
   X-Content-Type-Options (nosniff) via SECURE_CONTENT_TYPE_NOSNIFF.

2. AdminIPGuardMiddleware — when DJANGO_ADMIN_IPS is configured, only those
   client IPs may open the Django admin. Requests answer with a plain 404 so
   the admin surface stays invisible to scanners.

3. AdminTOTPMiddleware — when DJANGO_ADMIN_TOTP_SECRET is configured, BHIMS
   admin-role sign-in (core.admin_login) additionally requires a valid
   RFC-6238 6-digit code (Google Authenticator/Authy). The code rides in the
   regular login POST as `totp_code`.
"""
import hashlib
import hmac
import re
import struct
import time

from django.conf import settings
from django.http import Http404
from django.middleware.gzip import GZipMiddleware


class SecurityHeadersMiddleware:
    """Static security headers on every response."""

    # 'unsafe-inline' for scripts/styles is required by this project's inline
    # <script> blocks and inline styles; frame-ancestors 'none' double-locks
    # clickjacking alongside X-Frame-Options: DENY.
    CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault('Content-Security-Policy', self.CSP)
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        return response


class AdminIPGuardMiddleware:
    """Restrict the Django admin and BHIMS admin pages to known IPs."""

    GUARDED_PREFIXES = ('/django-admin/', '/admin/')

    def __init__(self, get_response):
        self.get_response = get_response
        self.allowed = set(getattr(settings, 'ADMIN_IP_ALLOWLIST', []) or [])

    def __call__(self, request):
        if self.allowed and request.path.startswith(self.GUARDED_PREFIXES):
            client = request.META.get('REMOTE_ADDR', '')
            if client not in self.allowed:
                # 404 instead of 403: do not confirm the admin URL exists.
                raise Http404('Page not found.')
        return self.get_response(request)


def _totp_now(secret_b32: str, for_time: int | None = None) -> str:
    """RFC-6238 TOTP (SHA-1, 6 digits, 30s step) for a base32 secret."""
    import base64
    key = base64.b32decode(secret_b32 + '=' * ((8 - len(secret_b32) % 8) % 8), casefold=True)
    counter = int(for_time if for_time is not None else time.time()) // 30
    msg = struct.pack('>Q', counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f'{code:06d}'


def totp_is_valid(secret_b32: str, submitted: str) -> bool:
    """Accept the code for the current 30s window or one step either side."""
    if not secret_b32 or not submitted:
        return False
    submitted = ''.join(ch for ch in submitted if ch.isdigit())
    if len(submitted) != 6:
        return False
    now = int(time.time())
    return any(
        hmac.compare_digest(_totp_now(secret_b32, now + drift), submitted)
        for drift in (-30, 0, 30)
    )


class AdminTOTPMiddleware:
    """Second factor for BHIMS admin-role sign-ins (opt-in via settings)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        secret = getattr(settings, 'ADMIN_TOTP_SECRET', '')
        if (
            secret
            and request.method == 'POST'
            and request.path == '/accounts/admin/login/'
            and not totp_is_valid(secret, request.POST.get('totp_code', ''))
        ):
            from django.contrib import messages
            messages.error(request, 'Invalid or expired verification code.')
            # Drop the credentials so authenticate() below cannot succeed.
            request.POST = request.POST.copy()
            request.POST['username'] = ''
            request.POST['password'] = ''
        return self.get_response(request)


class GZipTextMiddleware(GZipMiddleware):
    """Compress text responses only.

    Django's GZipMiddleware does not look at Content-Type. For a streaming
    response it compresses unconditionally, even when the result is bigger --
    so the room photos and logo PNGs, which are already compressed formats,
    went out labelled `Content-Encoding: gzip`. That cost CPU, gained nothing,
    and Chrome reported ERR_ABORTED on the image request.

    Keeping this filter means HTML, CSS and JS still compress (the landing page
    drops from ~117 KB to ~24 KB) while images, video, audio and fonts are
    passed through untouched.
    """

    COMPRESSIBLE = re.compile(
        r'^(?:text/|application/(?:json|javascript|xml|xhtml\+xml|manifest\+json))',
        re.IGNORECASE,
    )

    def process_response(self, request, response):
        content_type = response.get('Content-Type', '')
        if content_type and not self.COMPRESSIBLE.match(
            content_type.split(';')[0].strip()
        ):
            return response
        return super().process_response(request, response)
