import logging
from io import BytesIO

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from audit.models import AuditLog
from audit.services import log_audit
from common.upload_validation import DOCUMENT_EXTENSIONS, UploadValidationError, validate_upload
from firms.access import get_firm_or_403
from firms.permissions import HasFirmAccess
from invoices.services import InvoiceStorageService
from vault.models import CloudVaultEntry

from .models import EwayBillRecord
from .tasks import extract_eway_bill_data

logger = logging.getLogger(__name__)


def _serialize_eway_bill(record):
    return {
        'id': record.id,
        'file_name': record.file_name,
        'file_url': record.file_url,
        'file_size': record.file_size,
        'status': record.status,
        'eway_bill_number': record.eway_bill_number,
        'be_number': record.be_number,
        'vehicle_number': record.vehicle_number,
        'raw_data': record.raw_data,
        'extraction_failed': record.extraction_failed,
        'validation_warnings': record.validation_warnings or [],
        'uploaded_at': record.uploaded_at.isoformat(),
    }


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_eway_bills(request, firm_id):
    """
    POST /api/firms/{firm_id}/eway-bills/upload
    Uploads multiple files (PDF/JPG/PNG) as E-Way Bills.
    """
    firm = get_firm_or_403(request, firm_id)
    if isinstance(firm, Response):
        return firm

    files = request.FILES.getlist('files') or request.FILES.getlist('file')
    if not files:
        return Response({'error': 'No files provided.'}, status=status.HTTP_400_BAD_REQUEST)

    uploaded_records = []
    errors = []

    for f in files:
        try:
            file_bytes, _ext = validate_upload(f, allowed_extensions=DOCUMENT_EXTENSIONS)
        except UploadValidationError as exc:
            errors.append(f"'{f.name}': {exc}")
            continue

        try:
            # Save file using export storage
            file_url = InvoiceStorageService.upload_export(file_bytes, f.name, firm.id)

            record = EwayBillRecord.objects.create(
                firm=firm,
                file_name=f.name,
                file_url=file_url,
                file_size=len(file_bytes),
                status='processing',
                uploaded_by=request.user
            )

            CloudVaultEntry.objects.create(
                firm=firm,
                eway_bill=record,
                file_name=f.name,
                file_url=file_url,
                module='eway_bills',
                is_finalized=False
            )

            extract_eway_bill_data.delay(record.id)

            log_audit(
                user=request.user,
                firm=firm,
                resource_type=AuditLog.RESOURCE_EWAY_BILL,
                resource_id=record.id,
                action=AuditLog.ACTION_UPLOAD,
                details={'file_name': record.file_name},
                request=request,
            )

            uploaded_records.append(_serialize_eway_bill(record))

        except Exception as e:
            logger.error("Upload failed for E-Way Bill '%s': %s", f.name, e, exc_info=True)
            errors.append(f"'{f.name}': upload failed — {str(e)}")

    return Response(
        {'uploaded': uploaded_records, 'errors': errors},
        status=status.HTTP_201_CREATED if uploaded_records else status.HTTP_400_BAD_REQUEST
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_eway_bills(request, firm_id):
    """
    GET /api/firms/{firm_id}/eway-bills
    Lists all non-deleted E-Way Bill records.
    """
    firm = get_firm_or_403(request, firm_id)
    if isinstance(firm, Response):
        return firm

    qs = EwayBillRecord.objects.filter(firm=firm, is_deleted=False)

    search = request.GET.get('search', '').strip()
    if search:
        qs = qs.filter(
            eway_bill_number__icontains=search
        ) | EwayBillRecord.objects.filter(
            firm=firm, is_deleted=False, be_number__icontains=search
        )
        qs = qs.distinct()

    status_param = request.GET.get('status', '').strip()
    if status_param:
        qs = qs.filter(status=status_param)

    data = [_serialize_eway_bill(rec) for rec in qs]
    return Response(data, status=status.HTTP_200_OK)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_eway_bill(request, pk):
    """
    PUT /api/eway-bills/{pk}
    Allows updating fields manually (inline edit).
    """
    try:
        record = EwayBillRecord.objects.get(pk=pk, is_deleted=False)
    except EwayBillRecord.DoesNotExist:
        return Response({'error': 'Record not found.'}, status=status.HTTP_404_NOT_FOUND)

    perm = HasFirmAccess()
    if not perm.has_object_permission(request, None, record.firm):
        return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)

    raw_data_update = request.data.get('raw_data') or request.data

    if 'eway_bill_number' in raw_data_update:
        record.eway_bill_number = str(raw_data_update['eway_bill_number'] or '')[:100] or None
    if 'be_number' in raw_data_update:
        record.be_number = str(raw_data_update['be_number'] or '')[:100] or None
    if 'vehicle_number' in raw_data_update:
        record.vehicle_number = str(raw_data_update['vehicle_number'] or '')[:50] or None

    record.save()

    log_audit(
        user=request.user,
        firm=record.firm,
        resource_type=AuditLog.RESOURCE_EWAY_BILL,
        resource_id=record.id,
        action=AuditLog.ACTION_EDIT,
        details={'fields': list(raw_data_update.keys())},
        request=request,
    )
    return Response(_serialize_eway_bill(record))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_eway_bill(request, pk):
    """
    POST /api/eway-bills/{pk}/verify
    Marks the E-Way bill as verified.
    """
    try:
        record = EwayBillRecord.objects.get(pk=pk, is_deleted=False)
    except EwayBillRecord.DoesNotExist:
        return Response({'error': 'Record not found.'}, status=status.HTTP_404_NOT_FOUND)

    perm = HasFirmAccess()
    if not perm.has_object_permission(request, None, record.firm):
        return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)

    record.status = 'verified'
    record.save()

    CloudVaultEntry.objects.filter(
        firm=record.firm,
        eway_bill=record,
        is_deleted=False
    ).update(is_finalized=True)

    log_audit(
        user=request.user,
        firm=record.firm,
        resource_type=AuditLog.RESOURCE_EWAY_BILL,
        resource_id=record.id,
        action=AuditLog.ACTION_VERIFY,
        request=request,
    )
    return Response(_serialize_eway_bill(record))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def retry_eway_bill_extraction(request, pk):
    """
    POST /api/eway-bills/{pk}/retry-extraction
    Retries parsing E-Way bill.
    """
    try:
        record = EwayBillRecord.objects.get(pk=pk, is_deleted=False)
    except EwayBillRecord.DoesNotExist:
        return Response({'error': 'Record not found.'}, status=status.HTTP_404_NOT_FOUND)

    perm = HasFirmAccess()
    if not perm.has_object_permission(request, None, record.firm):
        return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)

    record.status = 'processing'
    record.extraction_failed = False
    record.validation_warnings = []
    record.save()

    extract_eway_bill_data.delay(record.id)

    log_audit(
        user=request.user,
        firm=record.firm,
        resource_type=AuditLog.RESOURCE_EWAY_BILL,
        resource_id=record.id,
        action=AuditLog.ACTION_RETRY,
        request=request,
    )
    return Response(_serialize_eway_bill(record))


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_eway_bill(request, pk):
    """
    DELETE /api/eway-bills/{pk}
    Soft-deletes E-Way bill and its cloud vault entry.
    """
    try:
        record = EwayBillRecord.objects.get(pk=pk)
    except EwayBillRecord.DoesNotExist:
        return Response({'error': 'Record not found.'}, status=status.HTTP_404_NOT_FOUND)

    perm = HasFirmAccess()
    if not perm.has_object_permission(request, None, record.firm):
        return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)

    record.is_deleted = True
    record.save()

    CloudVaultEntry.objects.filter(eway_bill=record).update(is_deleted=True)

    log_audit(
        user=request.user,
        firm=record.firm,
        resource_type=AuditLog.RESOURCE_EWAY_BILL,
        resource_id=record.id,
        action=AuditLog.ACTION_DELETE,
        request=request,
    )
    return Response({'message': 'E-way bill deleted.'}, status=status.HTTP_200_OK)
