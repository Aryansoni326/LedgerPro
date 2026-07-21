import logging
import re
import urllib.parse
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.http import HttpResponseRedirect
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


@api_view(['GET'])
@permission_classes([AllowAny])
def health(request):
    """Lightweight health check for Render / load balancers."""
    return Response({'status': 'ok'})


@api_view(['GET'])
@permission_classes([AllowAny])
def google_initiate(request):
    """
    Redirect the browser to Google's OAuth 2.0 authorization URL.
    The frontend calls this endpoint to kick off the OAuth flow.
    """
    client_id = getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', None)
    redirect_uri = getattr(settings, 'GOOGLE_OAUTH_REDIRECT_URI', None)

    if not client_id or not redirect_uri:
        return Response(
            {'error': 'Google OAuth is not configured. Please set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_REDIRECT_URI in your .env file.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    params = urllib.parse.urlencode({
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'access_type': 'offline',
        'prompt': 'select_account',
        'state': request.GET.get('flow', 'login'),
    })
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"
    return HttpResponseRedirect(google_auth_url)


@api_view(['POST'])
@permission_classes([AllowAny])
def google_callback(request):
    """
    Callback endpoint for Google OAuth authentication.
    Accepts either:
      - 'code'       : Authorization code from the OAuth redirect (real flow)
      - 'credential' : Google ID Token (legacy / dev mock flow)
    Creates/gets user, generates OTP 2FA, and returns a pending token.
    """
    code = request.data.get('code')
    credential = request.data.get('credential')

    if not code and not credential:
        return Response(
            {'error': 'Either code or credential is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        check_issue_ip_limit(_client_ip(request))
    except RateLimitExceeded as exc:
        return Response({'error': str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)

    try:
        if code:
            profile = GoogleAuthService.exchange_code(code)
        else:
            profile = GoogleAuthService.verify_token(credential)

        email = profile['email']
        google_sub = profile['sub']
        full_name = profile.get('name', '')
        avatar_url = profile.get('picture', '')

        try:
            user = User.objects.get(email=email)
            if not user.is_profile_complete:
                return Response(
                    {'error': 'Your registration is incomplete. Please click Get Started to register.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except User.DoesNotExist:
            return Response(
                {'error': 'No account found with this Google email. Please click Get Started to register.'},
                status=status.HTTP_400_BAD_REQUEST
            )

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

        verification, otp_code = OTPService.create_verification(user, purpose='login')
        OTPService.send_otp_email(user.email, otp_code)
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
def email_login(request):
    """
    Email-only login for accountants.
    Validates that the email belongs to a registered user, then sends an OTP.
    """
    email = request.data.get('email', '').strip().lower()
    if not email:
        return Response({'error': 'Email address is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        check_issue_ip_limit(_client_ip(request))
    except RateLimitExceeded as exc:
        return Response({'error': str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # Return a generic message to avoid email enumeration
        return Response(
            {'error': 'No account found with that email address. Please sign in with Google to register.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not user.is_active:
        return Response({'error': 'This account has been deactivated.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        verification, otp_code = OTPService.create_verification(user, purpose='login')
        OTPService.send_otp_email(user.email, otp_code)
        record_issue_otp(_client_ip(request), user.email)

        return Response({
            'pending_2fa_token': verification.pending_token,
            'email': user.email
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error in email_login view: %s", e, exc_info=True)
        return Response({'error': 'Failed to send verification code. Please try again.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def owner_login(request):
    """
    Owner login: only emails listed as Firm.owner_email may authenticate.
    Creates a lightweight owner user on first login, then sends OTP.
    """
    from firms.models import Firm

    email = request.data.get('email', '').strip().lower()
    if not email:
        return Response({'error': 'Email address is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        check_issue_ip_limit(_client_ip(request))
    except RateLimitExceeded as exc:
        return Response({'error': str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)

    owned_firms = Firm.objects.filter(owner_email__iexact=email)
    if not owned_firms.exists():
        return Response(
            {
                'error': (
                    'No firm is registered with this owner email. '
                    'Use the same email your accountant entered when adding your firm.'
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            'username': email,
            'role': 'owner',
            'is_profile_complete': True,
            'is_active': True,
        },
    )
    if not user.is_active:
        return Response({'error': 'This account has been deactivated.'}, status=status.HTTP_403_FORBIDDEN)

    if created or user.role != 'owner':
        # Keep accountants who also own firms as accountants for write access on firms they created;
        # owner login still grants read-only on firms matched by owner_email.
        if created:
            user.role = 'owner'
            user.is_profile_complete = True
            user.save(update_fields=['role', 'is_profile_complete'])

    try:
        verification, otp_code = OTPService.create_verification(user, purpose='owner_login')
        OTPService.send_otp_email(user.email, otp_code)
        record_issue_otp(_client_ip(request), user.email)

        return Response({
            'pending_2fa_token': verification.pending_token,
            'email': user.email,
            'access_mode': 'read_only',
            'firm_count': owned_firms.count(),
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error in owner_login view: %s", e, exc_info=True)
        return Response({'error': 'Failed to send verification code. Please try again.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def otp_verify(request):
    """
    Verify the 6-digit OTP code against the pending token.
    On success, issues a signed JWT session token.
    """
    from audit.services import log_firm_access_for_user_firms
    from firms.access import firms_queryset_for_user
    from firms.models import Firm

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

        user = verification.user
        if user is None:
            return Response({'error': 'Invalid verification session.'}, status=status.HTTP_400_BAD_REQUEST)

        is_owner_session = verification.purpose == 'owner_login'
        access_mode = 'read_only' if is_owner_session else 'full'

        session_payload = {
            'user_id': user.id,
            'email': user.email,
            'access_mode': access_mode,
            'exp_timestamp': (timezone.now() + timedelta(days=7)).timestamp()
        }
        token = signing.dumps(session_payload, key=settings.SECRET_KEY)

        # Record firm login activity for owner visibility
        if is_owner_session:
            firms = Firm.objects.filter(owner_email__iexact=user.email)
        else:
            firms = firms_queryset_for_user(user)
        log_firm_access_for_user_firms(user=user, firms=firms, request=request)

        return Response({
            'token': token,
            'access_mode': access_mode,
            'user': {
                'email': user.email,
                'name': user.get_full_name() or user.email.split('@')[0].capitalize(),
                'avatar': user.avatar_url,
                'role': user.role,
                'access_mode': access_mode,
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
        try:
            old_verification = OTPVerification.objects.get(pending_token=pending_token)
        except OTPVerification.DoesNotExist:
            return Response({'error': 'Verification session not found.'}, status=status.HTTP_400_BAD_REQUEST)

        if old_verification.is_verified:
            return Response({'error': 'Session already verified.'}, status=status.HTTP_400_BAD_REQUEST)

        user = old_verification.user
        email = user.email

        try:
            check_resend_ip_limit(_client_ip(request))
        except RateLimitExceeded as exc:
            return Response({'error': str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        ten_minutes_ago = timezone.now() - timedelta(minutes=10)
        recent_resends = OTPResendTracker.objects.filter(email=email, timestamp__gte=ten_minutes_ago).count()

        if recent_resends >= 3:
            return Response(
                {'error': 'Rate limit exceeded. Maximum 3 resend attempts allowed per 10 minutes. Please try again later.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        OTPResendTracker.objects.create(email=email)
        new_verification, otp_code = OTPService.create_verification(user)
        old_verification.is_locked = True
        old_verification.save()
        OTPService.send_otp_email(email, otp_code)
        record_resend_otp(_client_ip(request), email)

        return Response({
            'pending_2fa_token': new_verification.pending_token,
            'email': email
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error in otp_resend view: %s", e, exc_info=True)
        return Response({'error': 'An unexpected error occurred during code resend.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def register_with_google(request):
    """
    Register a new user via Google OAuth.
    Accepts an authorization code, exchanges it for a profile,
    creates a provisional user, and returns a registration token
    for the profile-completion step.
    """
    code = request.data.get('code')
    if not code:
        return Response(
            {'error': 'Authorization code is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        check_issue_ip_limit(_client_ip(request))
    except RateLimitExceeded as exc:
        return Response({'error': str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)

    try:
        profile = GoogleAuthService.exchange_code(code)

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
                'is_active': True,
                'is_profile_complete': False,
            }
        )

        if not created:
            # If the user already completed registration, redirect to login
            if user.is_profile_complete:
                return Response(
                    {'error': 'Account already exists. Please use login instead.'},
                    status=status.HTTP_409_CONFLICT
                )

            # User exists but profile is incomplete — allow resuming registration
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

        # Generate a temporary registration token (30-minute expiry)
        registration_payload = {
            'user_id': user.id,
            'email': email,
            'purpose': 'registration',
            'exp_timestamp': (timezone.now() + timedelta(minutes=30)).timestamp(),
        }
        registration_token = signing.dumps(registration_payload, key=settings.SECRET_KEY)

        return Response({
            'registration_token': registration_token,
            'email': email,
            'name': full_name,
            'avatar': avatar_url,
        }, status=status.HTTP_200_OK)

    except ValueError as ve:
        return Response({'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("Error in register_with_google view: %s", e, exc_info=True)
        return Response({'error': 'An unexpected authentication error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def register_with_email(request):
    """
    Register a new user via email.
    Creates a provisional user account, sends an OTP for email verification,
    and returns a registration token for the profile-completion step.
    """
    email = request.data.get('email', '').strip().lower()
    if not email:
        return Response({'error': 'Email address is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        check_issue_ip_limit(_client_ip(request))
    except RateLimitExceeded as exc:
        return Response({'error': str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)

    try:
        # Check if user already completed registration
        try:
            existing_user = User.objects.get(email=email)
            if existing_user.is_profile_complete:
                return Response(
                    {'error': 'Account already exists. Please use login instead.'},
                    status=status.HTTP_409_CONFLICT
                )
        except User.DoesNotExist:
            pass

        # Get or create provisional user
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'is_profile_complete': False,
                'is_active': True,
            }
        )

        # Generate a temporary registration token (30-minute expiry)
        registration_payload = {
            'user_id': user.id,
            'email': email,
            'purpose': 'registration',
            'exp_timestamp': (timezone.now() + timedelta(minutes=30)).timestamp(),
        }
        registration_token = signing.dumps(registration_payload, key=settings.SECRET_KEY)

        # Send OTP for email verification
        verification, otp_code = OTPService.create_verification(user)
        OTPService.send_otp_email(user.email, otp_code)
        record_issue_otp(_client_ip(request), user.email)

        return Response({
            'registration_token': registration_token,
            'email': email,
            'pending_2fa_token': verification.pending_token,
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error in register_with_email view: %s", e, exc_info=True)
        return Response({'error': 'An unexpected error occurred during registration.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def complete_profile(request):
    """
    Complete the user's profile after initial registration.
    Validates the registration token, updates profile fields,
    then sends an OTP for final verification.
    """
    registration_token = request.data.get('registration_token')
    if not registration_token:
        return Response(
            {'error': 'Registration token is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Decode and verify the registration token
    try:
        payload = signing.loads(registration_token, key=settings.SECRET_KEY)
    except signing.BadSignature:
        return Response({'error': 'Invalid or tampered registration token.'}, status=status.HTTP_400_BAD_REQUEST)

    if payload.get('purpose') != 'registration':
        return Response({'error': 'Invalid token purpose.'}, status=status.HTTP_400_BAD_REQUEST)

    if timezone.now().timestamp() > payload.get('exp_timestamp', 0):
        return Response({'error': 'Registration token has expired. Please start registration again.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(id=payload['user_id'])
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Validate required fields
    name = request.data.get('name', '').strip()
    phone_number = request.data.get('phone_number', '').strip()
    role = request.data.get('role', '').strip().lower()
    pan_number = request.data.get('pan_number', '').strip().upper() if request.data.get('pan_number') else None
    location = request.data.get('location', '').strip() or None
    organization = request.data.get('organization', '').strip() or None

    if not name:
        return Response({'error': 'Name is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if not phone_number:
        return Response({'error': 'Phone number is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if role not in ('accountant', 'owner', 'auditor'):
        return Response({'error': 'Role must be one of: accountant, owner, auditor.'}, status=status.HTTP_400_BAD_REQUEST)

    # Validate PAN format if provided
    if pan_number and not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', pan_number):
        return Response({'error': 'Invalid PAN format. Expected format: ABCDE1234F.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Update user profile
        user.first_name = name
        user.phone_number = phone_number
        user.pan_number = pan_number
        user.role = role
        user.location = location
        user.organization = organization
        user.is_profile_complete = True
        user.save()

        # Create OTP verification and send OTP email
        verification, otp_code = OTPService.create_verification(user)
        OTPService.send_otp_email(user.email, otp_code)
        record_issue_otp(_client_ip(request), user.email)

        return Response({
            'pending_2fa_token': verification.pending_token,
            'email': user.email,
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error in complete_profile view: %s", e, exc_info=True)
        return Response({'error': 'An unexpected error occurred while completing your profile.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
