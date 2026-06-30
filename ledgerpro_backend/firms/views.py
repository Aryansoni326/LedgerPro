import logging
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import OTPResendTracker, OTPVerification
from accounts.otp_helpers import _client_ip, verify_otp_session
from accounts.rate_limit import RateLimitExceeded, check_resend_ip_limit, record_resend_otp
from accounts.services import OTPService

from .models import Firm
from .permissions import HasFirmAccess

logger = logging.getLogger(__name__)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def list_create_firms(request):
    """
    GET: List all active and pending firms created by the accountant.
    POST: Create a pending firm and initiate owner email OTP 2FA verification.
    """
    if request.method == 'GET':
        firms = Firm.objects.filter(created_by=request.user).order_by('-created_at')
        firm_list = [{
            'id': firm.id,
            'name': firm.name,
            'gstin': firm.gstin,
            'state': firm.state,
            'city': firm.city,
            'owner_email': firm.owner_email,
            'status': firm.status,
            'created_at': firm.created_at
        } for firm in firms]
        return Response(firm_list, status=status.HTTP_200_OK)

    elif request.method == 'POST':
        name = request.data.get('name')
        gstin = request.data.get('gstin', '')
        state = request.data.get('state')
        city = request.data.get('city')
        owner_email = request.data.get('owner_email')

        if not name or not state or not city or not owner_email:
            return Response(
                {'error': 'Name, State, City, and Owner Email are required fields.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Build Firm instance and validate format (GSTIN regex checks via full_clean)
        firm = Firm(
            name=name,
            gstin=gstin.upper() if gstin else None,
            state=state,
            city=city,
            owner_email=owner_email,
            created_by=request.user,
            status='pending_verification'
        )

        try:
            firm.full_clean()
        except ValidationError as ve:
            # Flatten validation errors
            errors = {field: messages[0] for field, messages in ve.message_dict.items()}
            return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

        firm.save()

        # Create OTP Verification session for firm owner
        verification, code = OTPService.create_verification(
            email=owner_email,
            purpose='firm_owner_verify'
        )

        # Send OTP code
        OTPService.send_otp_email(owner_email, code)

        return Response({
            'id': firm.id,
            'pending_token': verification.pending_token,
            'owner_email': owner_email,
            'message': 'Firm registered in pending status. Verification OTP sent to owner.'
        }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated, HasFirmAccess])
def firm_detail(request, pk):
    """
    GET: Retrieve details of a specific firm. Restricted by HasFirmAccess.
    """
    try:
        firm = Firm.objects.get(pk=pk)
    except Firm.DoesNotExist:
        return Response({'error': 'Firm not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Check HasFirmAccess permission manually in FBV
    permission = HasFirmAccess()
    if not permission.has_object_permission(request, None, firm):
        return Response({'error': 'You do not have permission to access this firm.'}, status=status.HTTP_403_FORBIDDEN)

    return Response({
        'id': firm.id,
        'name': firm.name,
        'gstin': firm.gstin,
        'state': firm.state,
        'city': firm.city,
        'owner_email': firm.owner_email,
        'status': firm.status,
        'created_at': firm.created_at
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_firm_otp(request, pk):
    """
    POST: Verify the 4-digit OTP code to activate the pending firm.
    Accepts pending_token and code.
    """
    try:
        firm = Firm.objects.get(pk=pk, created_by=request.user)
    except Firm.DoesNotExist:
        return Response({'error': 'Firm not found or access denied.'}, status=status.HTTP_404_NOT_FOUND)

    if firm.status == 'active':
        return Response({'error': 'Firm is already verified and active.'}, status=status.HTTP_400_BAD_REQUEST)

    pending_token = request.data.get('pending_token')
    code = request.data.get('code')

    if not pending_token or not code:
        return Response(
            {'error': 'Both pending_token and code are required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        try:
            verification = OTPVerification.objects.get(
                pending_token=pending_token,
                purpose='firm_owner_verify',
                email=firm.owner_email
            )
        except OTPVerification.DoesNotExist:
            return Response({'error': 'Invalid verification session token.'}, status=status.HTTP_400_BAD_REQUEST)

        failure = verify_otp_session(
            request,
            verification,
            str(code).strip(),
            email_for_limit=firm.owner_email,
        )
        if failure is not None:
            return failure

        firm.status = 'active'
        firm.save()

        return Response({
            'status': 'active',
            'message': f"Firm '{firm.name}' successfully verified and activated."
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error in verify_firm_otp: %s", e, exc_info=True)
        return Response({'error': 'An unexpected error occurred during firm verification.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def resend_firm_otp(request, pk):
    """
    POST: Resend verification OTP code to the firm owner's email address.
    Rate-limited (max 3 resends per 10 minutes).
    """
    try:
        firm = Firm.objects.get(pk=pk, created_by=request.user)
    except Firm.DoesNotExist:
        return Response({'error': 'Firm not found.'}, status=status.HTTP_404_NOT_FOUND)

    if firm.status == 'active':
        return Response({'error': 'Firm is already verified and active.'}, status=status.HTTP_400_BAD_REQUEST)

    pending_token = request.data.get('pending_token')
    if not pending_token:
        return Response({'error': 'pending_token is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        try:
            old_verification = OTPVerification.objects.get(
                pending_token=pending_token,
                purpose='firm_owner_verify',
                email=firm.owner_email
            )
        except OTPVerification.DoesNotExist:
            return Response({'error': 'Verification session not found.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            check_resend_ip_limit(_client_ip(request))
        except RateLimitExceeded as exc:
            return Response({'error': str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Rate limit checks (max 3 in last 10m)
        ten_minutes_ago = timezone.now() - timedelta(minutes=10)
        recent_resends = OTPResendTracker.objects.filter(email=firm.owner_email, timestamp__gte=ten_minutes_ago).count()

        if recent_resends >= 3:
            return Response(
                {'error': 'Rate limit exceeded. Maximum 3 resend attempts allowed per 10 minutes.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        # Log resend
        OTPResendTracker.objects.create(email=firm.owner_email)

        # Generate new verification code and session
        new_verification, code = OTPService.create_verification(
            email=firm.owner_email,
            purpose='firm_owner_verify'
        )

        # Lock old verification session
        old_verification.is_locked = True
        old_verification.save()

        # Send new OTP
        OTPService.send_otp_email(firm.owner_email, code)
        record_resend_otp(_client_ip(request), firm.owner_email)

        return Response({
            'pending_token': new_verification.pending_token,
            'message': 'A fresh code has been sent to the owner email.'
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error in resend_firm_otp: %s", e, exc_info=True)
        return Response({'error': 'An unexpected error occurred during OTP resending.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
