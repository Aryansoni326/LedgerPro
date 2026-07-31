"""Diagnose OTP email delivery using the exact settings the API would use.

    python manage.py check_otp_email you@example.com
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.services import OTPDeliveryError, OTPService


class Command(BaseCommand):
    help = "Send a test verification code and report exactly how delivery was attempted."

    def add_arguments(self, parser):
        parser.add_argument('email', help='Recipient address for the test code.')

    def handle(self, *args, **options):
        recipient = options['email']

        api_key = getattr(settings, 'RESEND_API_KEY', '') or ''
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '')
        smtp_host = getattr(settings, 'EMAIL_HOST', '') or ''

        self.stdout.write('Configuration in use:')
        self.stdout.write(f'  DEFAULT_FROM_EMAIL : {from_email or "(unset)"}')
        self.stdout.write(
            '  RESEND_API_KEY     : '
            + (f'set, {len(api_key.strip())} chars, starts with {api_key.strip()[:6]}...' if api_key.strip() else 'NOT SET')
        )
        self.stdout.write(f'  EMAIL_HOST         : {smtp_host or "(unset)"}')

        if api_key.strip():
            route = 'Resend HTTP API'
        elif smtp_host:
            route = 'SMTP (blocked on Render free tier)'
        else:
            route = 'console fallback — no email will be sent'
        self.stdout.write(f'  Delivery route     : {route}')
        self.stdout.write('')

        code = OTPService.generate_otp()
        self.stdout.write(f'Sending test code {code} to {recipient}...')

        try:
            OTPService.send_otp_email(recipient, code)
        except OTPDeliveryError as e:
            raise CommandError(f'Delivery failed: {e}')

        self.stdout.write(self.style.SUCCESS('Delivery call completed without error.'))
