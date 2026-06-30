"""
OTP view helpers shared between accounts and firms apps.
"""
from rest_framework import status
from rest_framework.response import Response

from .models import OTPVerification
from .rate_limit import (
    OTP_MAX_SESSION_ATTEMPTS,
    RateLimitExceeded,
    check_verify_email_limit,
    check_verify_ip_limit,
    is_session_locked,
    lock_session,
    record_verify_attempt,
    record_verify_failure,
)
from .services import OTPService


def _client_ip(request) -> str | None:
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def verify_otp_session(
    request,
    verification: OTPVerification,
    code: str,
    *,
    email_for_limit: str | None = None,
) -> Response | None:
    """
    Run rate-limit, lockout, expiry, and code checks for an OTPVerification row.

    Returns None on success (caller should mark verified and respond).
    Returns a Response on failure.
    """
    ip = _client_ip(request)
    email = email_for_limit or (
        verification.user.email if verification.user else verification.email
    )

    try:
        check_verify_ip_limit(ip)
        check_verify_email_limit(email)
    except RateLimitExceeded as exc:
        return Response({'error': str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)

    # Count every verify API call toward IP rate limits (even if session is locked)
    record_verify_attempt(ip, email)

    if verification.is_verified:
        return Response(
            {'error': 'This verification session has already been completed.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if verification.is_expired():
        return Response(
            {'error': 'This code has expired (5-minute limit). Please request a new code.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if is_session_locked(verification):
        lock_session(verification)
        return Response(
            {
                'error': 'Maximum verification attempts exceeded. This session has been locked. Please request a new code.'
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if OTPService.verify_otp_hash(code, verification.otp_hash, salt=verification.pending_token):
        verification.is_verified = True
        verification.save(update_fields=['is_verified'])
        return None

    verification.attempts += 1
    if verification.attempts >= OTP_MAX_SESSION_ATTEMPTS:
        verification.is_locked = True
    verification.save(update_fields=['attempts', 'is_locked'])
    record_verify_failure(ip, email)

    remaining = max(0, OTP_MAX_SESSION_ATTEMPTS - verification.attempts)
    if verification.is_locked:
        error_msg = 'Invalid code. Maximum attempts exceeded. This session is now locked.'
    else:
        error_msg = f'Invalid code. {remaining} attempt(s) remaining.'

    return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
