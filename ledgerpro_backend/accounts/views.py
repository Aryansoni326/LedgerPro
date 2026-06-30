import logging
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import OTPResendTracker, OTPVerification, User
from .otp_helpers import _client_ip, verify_otp_session
from .rate_limit import (
    RateLimitExceeded,
    check_issue_ip_limit,
    check_resend_ip_limit,
    record_issue_otp,
    record_resend_otp,
)
from .services import GoogleAuthService, OTPService

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([AllowAny])
def google_callback(request):
    """
    Callback endpoint for Google OAuth authentication.
    Accepts credential (Google ID Token), creates/gets user,
    generates OTP 2FA, and returns a pending token.
    """
    credential = request.data.get('credential')
    if not credential:
        return Response(
            {'error': 'Google credential (ID Token) is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        check_issue_ip_limit(_client_ip(request))
    except RateLimitExceeded as exc:
        return Response({'error': str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)

    try:
        profile = GoogleAuthService.verify_token(credential)
        email = profile['email']
        google_sub = profile['sub']
        full_name = profile.get('name', '')
        avatar_url = profile.get('picture', '')

        # Get or create User
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'google_sub': google_sub,
                'first_name': full_name,
                'avatar_url': avatar_url,
                'is_active': True
            }
        )

        # Update fields if user already existed but didn't have Google info
        if not created:
            updated = False
            if not user.google_sub:
                user.google_sub = google_sub
                updated = True
            if avatar_url and not user.avatar_url:
                user.avatar_url = avatar_url
                updated = True
            if full_name and not user.first_name:
                user.first_name = full_name
                updated = True
            if updated:
                user.save()

        # Create OTP Verification
        verification, code = OTPService.create_verification(user)

        # Send OTP
        OTPService.send_otp_email(user.email, code)
        record_issue_otp(_client_ip(request), user.email)

        return Response({
            'pending_2fa_token': verification.pending_token,
            'email': user.email
        }, status=status.HTTP_200_OK)

    except ValueError as ve:
        return Response({'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("Error in google_callback view: %s", e, exc_info=True)
        return Response({'error': 'An unexpected authentication error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def otp_verify(request):
    """
    Verify the 4-digit OTP code against the pending token.
    On success, issues a signed JWT session token.
    """
    pending_token = request.data.get('pending_token')
    code = request.data.get('code')

    if not pending_token or not code:
        return Response(
            {'error': 'Both pending_token and code are required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        try:
            verification = OTPVerification.objects.get(pending_token=pending_token)
        except OTPVerification.DoesNotExist:
            return Response({'error': 'Invalid verification session token.'}, status=status.HTTP_400_BAD_REQUEST)

        failure = verify_otp_session(request, verification, str(code).strip())
        if failure is not None:
            return failure

        # Code verified — issue session token
        session_payload = {
            'user_id': verification.user.id,
            'email': verification.user.email,
            'exp_timestamp': (timezone.now() + timedelta(days=7)).timestamp()
        }
        token = signing.dumps(session_payload, key=settings.SECRET_KEY)

        return Response({
            'token': token,
            'user': {
                'email': verification.user.email,
                'name': verification.user.get_full_name() or verification.user.email.split('@')[0].capitalize(),
                'avatar': verification.user.avatar_url
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error in otp_verify view: %s", e, exc_info=True)
        return Response({'error': 'An unexpected error occurred during code verification.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def otp_resend(request):
    """
    Rate-limited endpoint to resend a fresh OTP code for an active pending verification.
    Limits to maximum 3 resends per 10 minutes per email.
    """
    pending_token = request.data.get('pending_token')

    if not pending_token:
        return Response(
            {'error': 'pending_token is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Retrieve active verification session
        try:
            old_verification = OTPVerification.objects.get(pending_token=pending_token)
        except OTPVerification.DoesNotExist:
            return Response({'error': 'Verification session not found.'}, status=status.HTTP_400_BAD_REQUEST)

        # Prevent resending on already verified sessions
        if old_verification.is_verified:
            return Response({'error': 'Session already verified.'}, status=status.HTTP_400_BAD_REQUEST)

        user = old_verification.user
        email = user.email

        try:
            check_resend_ip_limit(_client_ip(request))
        except RateLimitExceeded as exc:
            return Response({'error': str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Check rate limiting: max 3 resends in last 10 minutes
        ten_minutes_ago = timezone.now() - timedelta(minutes=10)
        recent_resends = OTPResendTracker.objects.filter(email=email, timestamp__gte=ten_minutes_ago).count()

        if recent_resends >= 3:
            return Response(
                {'error': 'Rate limit exceeded. Maximum 3 resend attempts allowed per 10 minutes. Please try again later.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        # Log this resend
        OTPResendTracker.objects.create(email=email)

        # Create new verification
        new_verification, code = OTPService.create_verification(user)

        # Deactivate old one
        old_verification.is_locked = True
        old_verification.save()

        # Send new OTP
        OTPService.send_otp_email(email, code)
        record_resend_otp(_client_ip(request), email)

        return Response({
            'pending_2fa_token': new_verification.pending_token,
            'email': email
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error in otp_resend view: %s", e, exc_info=True)
        return Response({'error': 'An unexpected error occurred during code resend.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
