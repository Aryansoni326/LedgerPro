"""Print whether Resend OTP delivery is configured (no secrets)."""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ledgerpro_backend.settings")
django.setup()

from django.conf import settings

key = (getattr(settings, "RESEND_API_KEY", "") or "").strip()
from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "") or ""
print(f"RESEND_CONFIGURED={bool(key)}")
print(f"RESEND_KEY_LEN={len(key)}")
print(f"DEFAULT_FROM_EMAIL={from_email}")
print(f"EMAIL_HOST={getattr(settings, 'EMAIL_HOST', '')!r}")
