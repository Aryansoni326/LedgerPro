"""
OTP and authentication rate limiting + brute-force protection.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import OTPRateLimitEvent, OTPVerification

logger = logging.getLogger(__name__)

# Per-session attempt cap (existing Phase 1 behaviour)
OTP_MAX_SESSION_ATTEMPTS = 5

# Per-IP verify attempts within sliding window
OTP_VERIFY_IP_LIMIT = getattr(settings, 'OTP_VERIFY_IP_LIMIT', 15)
OTP_VERIFY_IP_WINDOW_MINUTES = getattr(settings, 'OTP_VERIFY_IP_WINDOW_MINUTES', 15)

# Per-email verify failures across all sessions
OTP_VERIFY_EMAIL_LIMIT = getattr(settings, 'OTP_VERIFY_EMAIL_LIMIT', 10)
OTP_VERIFY_EMAIL_WINDOW_MINUTES = getattr(settings, 'OTP_VERIFY_EMAIL_WINDOW_MINUTES', 60)

# Login / OTP issuance (google_callback)
OTP_ISSUE_IP_LIMIT = getattr(settings, 'OTP_ISSUE_IP_LIMIT', 10)
OTP_ISSUE_IP_WINDOW_MINUTES = getattr(settings, 'OTP_ISSUE_IP_WINDOW_MINUTES', 15)

# Resend (existing: 3 per 10 min tracked separately via OTPResendTracker)
OTP_RESEND_IP_LIMIT = getattr(settings, 'OTP_RESEND_IP_LIMIT', 10)
OTP_RESEND_IP_WINDOW_MINUTES = getattr(settings, 'OTP_RESEND_IP_WINDOW_MINUTES', 15)


class RateLimitExceeded(Exception):
    def __init__(self, message: str, retry_after_minutes: int = 15):
        super().__init__(message)
        self.retry_after_minutes = retry_after_minutes


def _count_events(event_type: str, *, ip: str | None = None, email: str | None = None, minutes: int) -> int:
    since = timezone.now() - timedelta(minutes=minutes)
    qs = OTPRateLimitEvent.objects.filter(event_type=event_type, timestamp__gte=since)
    if ip:
        qs = qs.filter(ip_address=ip)
    if email:
        qs = qs.filter(email=email)
    return qs.count()


def record_event(event_type: str, *, ip: str | None = None, email: str | None = None) -> None:
    OTPRateLimitEvent.objects.create(event_type=event_type, ip_address=ip, email=email)


def check_verify_ip_limit(ip: str | None) -> None:
    if not ip:
        return
    count = _count_events('verify_attempt', ip=ip, minutes=OTP_VERIFY_IP_WINDOW_MINUTES)
    if count >= OTP_VERIFY_IP_LIMIT:
        logger.warning("OTP verify IP rate limit exceeded for %s", ip)
        raise RateLimitExceeded(
            'Too many verification attempts from this network. Please try again later.',
            OTP_VERIFY_IP_WINDOW_MINUTES,
        )


def check_verify_email_limit(email: str | None) -> None:
    if not email:
        return
    count = _count_events('verify_failure', email=email, minutes=OTP_VERIFY_EMAIL_WINDOW_MINUTES)
    if count >= OTP_VERIFY_EMAIL_LIMIT:
        logger.warning("OTP verify email lockout for %s", email)
        raise RateLimitExceeded(
            'Too many failed verification attempts for this account. Please try again later.',
            OTP_VERIFY_EMAIL_WINDOW_MINUTES,
        )


def check_issue_ip_limit(ip: str | None) -> None:
    if not ip:
        return
    count = _count_events('issue_otp', ip=ip, minutes=OTP_ISSUE_IP_WINDOW_MINUTES)
    if count >= OTP_ISSUE_IP_LIMIT:
        logger.warning("OTP issue IP rate limit exceeded for %s", ip)
        raise RateLimitExceeded(
            'Too many login attempts from this network. Please try again later.',
            OTP_ISSUE_IP_WINDOW_MINUTES,
        )


def check_resend_ip_limit(ip: str | None) -> None:
    if not ip:
        return
    count = _count_events('resend_otp', ip=ip, minutes=OTP_RESEND_IP_WINDOW_MINUTES)
    if count >= OTP_RESEND_IP_LIMIT:
        raise RateLimitExceeded(
            'Too many resend requests from this network. Please try again later.',
            OTP_RESEND_IP_WINDOW_MINUTES,
        )


def record_verify_attempt(ip: str | None, email: str | None) -> None:
    record_event('verify_attempt', ip=ip, email=email)


def record_verify_failure(ip: str | None, email: str | None) -> None:
    record_event('verify_failure', ip=ip, email=email)


def record_issue_otp(ip: str | None, email: str | None) -> None:
    record_event('issue_otp', ip=ip, email=email)


def record_resend_otp(ip: str | None, email: str | None) -> None:
    record_event('resend_otp', ip=ip, email=email)


def is_session_locked(verification: OTPVerification) -> bool:
    return verification.is_locked or verification.attempts >= OTP_MAX_SESSION_ATTEMPTS


def lock_session(verification: OTPVerification) -> None:
    if not verification.is_locked:
        verification.is_locked = True
        verification.save(update_fields=['is_locked'])
