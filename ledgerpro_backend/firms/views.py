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
from audit.models import AuditLog, FirmAccessLog
from firms.access import firms_queryset_for_user
from firms.permissions import HasFirmAccess, is_firm_creator, is_firm_owner_email

from .models import Firm

logger = logging.getLogger(__name__)


def _serialize_firm(firm, user):
    access = 'full' if is_firm_creator(user, firm) else 'read_only'
    return {
        'id': firm.id,
        'name': firm.name,
        'gstin': firm.gstin,
        'state': firm.state,
        'city': firm.city,
        'owner_email': firm.owner_email,
        'status': firm.status,
        'created_at': firm.created_at,
        'access_mode': access,
        'accountant_email': firm.created_by.email if firm.created_by_id else None,
    }


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def list_create_firms(request):
    """
    GET: List firms the user created or owns (via owner_email).
    POST: Create a pending firm (accountants only) and initiate owner email OTP.
    """
    if request.method == 'GET':
        firms = firms_queryset_for_user(request.user).select_related('created_by').order_by('-created_at')
        return Response(
            [_serialize_firm(firm, request.user) for firm in firms],
            status=status.HTTP_200_OK,
        )

    elif request.method == 'POST':
        if request.user.role == 'owner':
            return Response(
                {'error': 'Owner accounts are read-only and cannot register new firms.'},
                status=status.HTTP_403_FORBIDDEN,
            )

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
            errors = {field: messages[0] for field, messages in ve.message_dict.items()}
            return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

        firm.save()

        verification, code = OTPService.create_verification(
            email=owner_email,
            purpose='firm_owner_verify'
        )
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
    """GET: Retrieve details of a specific firm. Restricted by HasFirmAccess."""
    try:
        firm = Firm.objects.select_related('created_by').get(pk=pk)
    except Firm.DoesNotExist:
        return Response({'error': 'Firm not found.'}, status=status.HTTP_404_NOT_FOUND)

    permission = HasFirmAccess()
    if not permission.has_object_permission(request, None, firm):
        return Response({'error': 'You do not have permission to access this firm.'}, status=status.HTTP_403_FORBIDDEN)

    return Response(_serialize_firm(firm, request.user), status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def firm_activity(request, pk):
    """
    GET: Activity feed for a firm — logins, uploads, edits, and other work.
    Available to accountants (creators) and owners (owner_email match).
    """
    try:
        firm = Firm.objects.get(pk=pk)
    except Firm.DoesNotExist:
        return Response({'error': 'Firm not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not (is_firm_creator(request.user, firm) or is_firm_owner_email(request.user, firm)):
        return Response({'error': 'You do not have permission to access this firm.'}, status=status.HTTP_403_FORBIDDEN)

    limit = min(int(request.query_params.get('limit', 100)), 300)

    access_logs = (
        FirmAccessLog.objects.filter(firm=firm)
        .select_related('user')
        .order_by('-timestamp')[:limit]
    )
    audit_logs = (
        AuditLog.objects.filter(firm=firm)
        .select_related('user')
        .order_by('-timestamp')[:limit]
    )

    events = []
    for entry in access_logs:
        events.append({
            'id': f'access-{entry.id}',
            'kind': 'login',
            'action': 'login',
            'actor_email': entry.user.email if entry.user else None,
            'actor_name': (
                entry.user.get_full_name() or entry.user.email.split('@')[0]
            ) if entry.user else 'Unknown',
            'actor_role': entry.user.role if entry.user else None,
            'resource_type': None,
            'resource_id': None,
            'details': {
                'ip_address': entry.ip_address,
                'user_agent': entry.user_agent,
            },
            'timestamp': entry.timestamp,
        })

    resource_labels = {
        'bill': 'Invoice / Bill',
        'import_export_record': 'Import-Export document',
        'eway_bill_record': 'E-Way Bill',
    }
    for entry in audit_logs:
        events.append({
            'id': f'audit-{entry.id}',
            'kind': 'work',
            'action': entry.action,
            'actor_email': entry.user.email if entry.user else None,
            'actor_name': (
                entry.user.get_full_name() or entry.user.email.split('@')[0]
            ) if entry.user else 'System',
            'actor_role': entry.user.role if entry.user else None,
            'resource_type': entry.resource_type,
            'resource_label': resource_labels.get(entry.resource_type, entry.resource_type),
            'resource_id': entry.resource_id,
            'details': entry.details or {},
            'timestamp': entry.timestamp,
        })

    events.sort(key=lambda e: e['timestamp'], reverse=True)
    events = events[:limit]

    uploads = [e for e in events if e['kind'] == 'work' and e['action'] == 'upload']

    return Response({
        'firm_id': firm.id,
        'firm_name': firm.name,
        'events': events,
        'uploads': uploads,
        'login_count': FirmAccessLog.objects.filter(firm=firm).count(),
        'work_count': AuditLog.objects.filter(firm=firm).count(),
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_firm_otp(request, pk):
    """POST: Verify the OTP code to activate the pending firm."""
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
    """POST: Resend verification OTP to the firm owner's email."""
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

        ten_minutes_ago = timezone.now() - timedelta(minutes=10)
        recent_resends = OTPResendTracker.objects.filter(email=firm.owner_email, timestamp__gte=ten_minutes_ago).count()

        if recent_resends >= 3:
            return Response(
                {'error': 'Rate limit exceeded. Maximum 3 resend attempts allowed per 10 minutes.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        OTPResendTracker.objects.create(email=firm.owner_email)

        new_verification, code = OTPService.create_verification(
            email=firm.owner_email,
            purpose='firm_owner_verify'
        )

        old_verification.is_locked = True
        old_verification.save()

        OTPService.send_otp_email(firm.owner_email, code)
        record_resend_otp(_client_ip(request), firm.owner_email)

        return Response({
            'pending_token': new_verification.pending_token,
            'message': 'A fresh code has been sent to the owner email.'
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error in resend_firm_otp: %s", e, exc_info=True)
        return Response({'error': 'An unexpected error occurred during OTP resending.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
