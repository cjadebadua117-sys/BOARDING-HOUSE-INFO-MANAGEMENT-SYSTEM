"""Generate a base32 TOTP secret for admin sign-in 2FA.

Usage:
    python manage.py generate_totp_secret

Put the printed secret into the .env file as DJANGO_ADMIN_TOTP_SECRET=<secret>
(or export it as an environment variable), then add it to Google
Authenticator / Authy by typing it or scanning the otpauth:// URI in a QR.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Generate a base32 TOTP secret for admin sign-in 2FA.'

    def add_arguments(self, parser):
        parser.add_argument('--label', default='BHIMS-Admin', help='Account label for the otpauth URI.')

    def handle(self, *args, **options):
        import base64
        import secrets

        raw = secrets.token_bytes(20)  # 160-bit secret, RFC-4226 recommendation
        secret = base64.b32encode(raw).decode('ascii').rstrip('=')
        label = options['label']
        uri = f'otpauth://totp/{label}?secret={secret}&issuer=BHIMS&digits=6&period=30'

        self.stdout.write(self.style.SUCCESS('TOTP secret generated.'))
        self.stdout.write('')
        self.stdout.write(f'DJANGO_ADMIN_TOTP_SECRET={secret}')
        self.stdout.write('')
        self.stdout.write('otpauth URI (for QR generation):')
        self.stdout.write(uri)
        self.stdout.write('')
        self.stdout.write(
            'Add it to the .env file (or your hosting environment), restart the '
            'server, and admin sign-in will now require a 6-digit code.'
        )
