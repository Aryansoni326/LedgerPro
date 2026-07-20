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
from vault.models import CloudVaultEntry

from .models import ImportExportRecord
from .services import TradeDocStorageService
from .tasks import extract_trade_doc_data

logger = logging.getLogger(__name__)


def _serialize_record(record):
    """Serialize an ImportExportRecord to a dict for API responses."""
    return {
        'id': record.id,
        'file_name': record.file_name,
        'file_url': record.file_url,
        'file_size': record.file_size,
        'status': record.status,
        'extraction_failed': record.extraction_failed,
        'validation_warnings': record.validation_warnings or [],
        'raw_data': record.raw_data,
        'uploaded_at': record.uploaded_at.isoformat(),
        # Canonical typed columns (fast access for grid)
        'be_number': record.be_number,
        'be_date': record.be_date.isoformat() if record.be_date else None,
        'port_code': record.port_code,
        'container_id': record.container_id,
        'gross_weight': float(record.gross_weight) if record.gross_weight is not None else None,
        'net_weight': float(record.net_weight) if record.net_weight is not None else None,
        'currency': record.currency,
        'assessable_value': float(record.assessable_value) if record.assessable_value is not None else None,
        'shipper_name': record.shipper_name,
    }


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_trade_docs(request, firm_id):
    """
    POST /api/firms/{firm_id}/trade-docs/upload

    Accepts multiple files (PDF/JPG/PNG, max 10 MB each).
    For each file: uploads to storage, creates an ImportExportRecord at
    status='processing', enqueues extract_trade_doc_data, and creates a
    CloudVaultEntry under module='import_export'.
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
            buffer = BytesIO(file_bytes)
            buffer.name = f.name
            file_url = TradeDocStorageService.upload_trade_doc(buffer, firm.id)

            record = ImportExportRecord.objects.create(
                firm=firm,
                file_name=f.name,
                file_url=file_url,
                file_size=len(file_bytes),
                status='processing',
                uploaded_by=request.user
            )

            CloudVaultEntry.objects.create(
                firm=firm,
                trade_doc=record,
                file_name=f.name,
                file_url=file_url,
                module='import_export',
                is_finalized=False
            )

            extract_trade_doc_data.delay(record.id)

            log_audit(
                user=request.user,
                firm=firm,
                resource_type=AuditLog.RESOURCE_IMPORT_EXPORT,
                resource_id=record.id,
                action=AuditLog.ACTION_UPLOAD,
                details={'file_name': record.file_name},
                request=request,
            )

            uploaded_records.append(_serialize_record(record))

        except Exception as e:
            logger.error("Upload failed for '%s': %s", f.name, e, exc_info=True)
            errors.append(f"'{f.name}': upload failed — {str(e)}")

    return Response(
        {'uploaded': uploaded_records, 'errors': errors},
        status=status.HTTP_201_CREATED if uploaded_records else status.HTTP_400_BAD_REQUEST
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_trade_docs(request, firm_id):
    """
    GET /api/firms/{firm_id}/trade-docs
    Query params: search, status, start_date, end_date
    """
    firm = get_firm_or_403(request, firm_id)
    if isinstance(firm, Response):
        return firm

    qs = ImportExportRecord.objects.filter(firm=firm, is_deleted=False)

    search = request.GET.get('search', '').strip()
    if search:
        qs = qs.filter(
            be_number__icontains=search
        ) | ImportExportRecord.objects.filter(
            firm=firm, is_deleted=False, shipper_name__icontains=search
        )
        qs = qs.distinct()

    status_param = request.GET.get('status', '').strip()
    if status_param:
        qs = qs.filter(status=status_param)

    start_date = request.GET.get('start_date', '').strip()
    if start_date:
        qs = qs.filter(uploaded_at__date__gte=start_date)

    end_date = request.GET.get('end_date', '').strip()
    if end_date:
        qs = qs.filter(uploaded_at__date__lte=end_date)

    return Response([_serialize_record(r) for r in qs.order_by('-uploaded_at')])


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def manage_trade_doc(request, pk):
    """
    GET    /api/trade-docs/{pk}  → retrieve single record
    PATCH  /api/trade-docs/{pk}  → inline field edits; re-runs validation
    DELETE /api/trade-docs/{pk}  → soft-delete
    """
    try:
        record = ImportExportRecord.objects.select_related('firm').get(pk=pk, is_deleted=False)
    except ImportExportRecord.DoesNotExist:
        return Response({'error': 'Record not found.'}, status=status.HTTP_404_NOT_FOUND)

    perm = HasFirmAccess()
    if not perm.has_object_permission(request, None, record.firm):
        return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        return Response(_serialize_record(record))

    if request.method == 'DELETE':
        record.is_deleted = True
        record.save()
        CloudVaultEntry.objects.filter(
            firm=record.firm,
            file_url=record.file_url,
            is_finalized=False
        ).update(is_deleted=True)

        log_audit(
            user=request.user,
            firm=record.firm,
            resource_type=AuditLog.RESOURCE_IMPORT_EXPORT,
            resource_id=record.id,
            action=AuditLog.ACTION_DELETE,
            details={'file_name': record.file_name},
            request=request,
        )
        return Response({'message': 'Trade doc soft-deleted.'}, status=status.HTTP_200_OK)

    if request.method == 'PATCH':
        raw_data_update = request.data.get('raw_data', {})
        existing = record.raw_data or {}
        existing.update(raw_data_update)
        record.raw_data = existing

        # Promote patched fields to typed columns
        be_date_str = existing.get('be_date')
        be_date_parsed = None
        if be_date_str:
            try:
                from datetime import datetime
                be_date_parsed = datetime.strptime(str(be_date_str)[:10], '%Y-%m-%d').date()
            except ValueError:
                pass

        record.be_number = str(existing.get('be_number') or '')[:100] or None
        record.be_date = be_date_parsed
        record.port_code = str(existing.get('port_code') or '')[:20] or None
        record.container_id = str(existing.get('container_id') or '')[:1000] or None
        record.gross_weight = _safe_float(existing.get('gross_weight')) or None
        record.net_weight = _safe_float(existing.get('net_weight')) or None
        record.currency = str(existing.get('currency') or '')[:10] or None
        record.assessable_value = _safe_float(existing.get('assessable_value')) or None
        record.shipper_name = str(existing.get('shipper_name') or '')[:255] or None

        # Re-run server-side validation
        warnings = []
        gross = float(record.gross_weight or 0.0)
        net = float(record.net_weight or 0.0)
        if net > gross > 0:
            warnings.append(f"Weight inconsistency: net weight ({net} KG) exceeds gross weight ({gross} KG).")
        assessable = float(record.assessable_value or 0.0)
        if assessable <= 0:
            warnings.append("Assessable value is zero or missing — please verify the document.")

        record.validation_warnings = warnings
        record.save()

        log_audit(
            user=request.user,
            firm=record.firm,
            resource_type=AuditLog.RESOURCE_IMPORT_EXPORT,
            resource_id=record.id,
            action=AuditLog.ACTION_EDIT,
            details={'fields': list(raw_data_update.keys())},
            request=request,
        )
        return Response(_serialize_record(record))


def _safe_float(val):
    try:
        return float(val) if val is not None else None
    except (ValueError, TypeError):
        return None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_trade_doc(request, pk):
    """
    POST /api/trade-docs/{pk}/verify
    Marks the record as verified. Only allowed when status='needs_review'.
    """
    try:
        record = ImportExportRecord.objects.get(pk=pk, is_deleted=False)
    except ImportExportRecord.DoesNotExist:
        return Response({'error': 'Record not found.'}, status=status.HTTP_404_NOT_FOUND)

    perm = HasFirmAccess()
    if not perm.has_object_permission(request, None, record.firm):
        return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)

    if record.status not in ('needs_review', 'approved'):
        return Response(
            {'error': f"Cannot verify a record with status '{record.status}'."},
            status=status.HTTP_400_BAD_REQUEST
        )

    record.status = 'verified'
    record.save()

    CloudVaultEntry.objects.filter(
        firm=record.firm,
        file_url=record.file_url,
        is_finalized=False,
        is_deleted=False
    ).update(is_finalized=True)

    log_audit(
        user=request.user,
        firm=record.firm,
        resource_type=AuditLog.RESOURCE_IMPORT_EXPORT,
        resource_id=record.id,
        action=AuditLog.ACTION_VERIFY,
        request=request,
    )

    return Response(_serialize_record(record))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def retry_trade_doc_extraction(request, pk):
    """
    POST /api/trade-docs/{pk}/retry-extraction
    Re-enqueues the Gemini extraction task for a failed or stuck record.
    """
    try:
        record = ImportExportRecord.objects.get(pk=pk, is_deleted=False)
    except ImportExportRecord.DoesNotExist:
        return Response({'error': 'Record not found.'}, status=status.HTTP_404_NOT_FOUND)

    perm = HasFirmAccess()
    if not perm.has_object_permission(request, None, record.firm):
        return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)

    record.status = 'processing'
    record.extraction_failed = False
    record.validation_warnings = []
    record.save()

    extract_trade_doc_data.delay(record.id)

    log_audit(
        user=request.user,
        firm=record.firm,
        resource_type=AuditLog.RESOURCE_IMPORT_EXPORT,
        resource_id=record.id,
        action=AuditLog.ACTION_RETRY,
        request=request,
    )
    return Response({'message': 'Extraction re-queued.', 'id': record.id})
