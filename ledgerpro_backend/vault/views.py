import logging

from django.db.models.functions import ExtractDay, ExtractMonth, ExtractYear
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from audit.models import AuditLog
from audit.services import log_audit
from common.upload_validation import STUB_EXTENSIONS, UploadValidationError, validate_upload
from eway_bills.models import EwayBillRecord
from firms.access import get_firm_or_403
from firms.permissions import HasFirmAccess
from invoices.services import InvoiceStorageService

from .models import CloudVaultEntry

logger = logging.getLogger(__name__)


def _vault_firm(request, firm_id):
    firm = get_firm_or_403(request, firm_id)
    return firm


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_vault_years(request, firm_id):
    firm = _vault_firm(request, firm_id)
    if isinstance(firm, Response):
        return firm

    years = CloudVaultEntry.objects.filter(
        firm=firm,
        is_deleted=False
    ).annotate(
        year=ExtractYear('uploaded_at')
    ).values_list('year', flat=True).distinct().order_by('-year')

    return Response(list(years), status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_vault_months(request, firm_id, year):
    firm = _vault_firm(request, firm_id)
    if isinstance(firm, Response):
        return firm

    months = CloudVaultEntry.objects.filter(
        firm=firm,
        is_deleted=False,
        uploaded_at__year=year
    ).annotate(
        month=ExtractMonth('uploaded_at')
    ).values_list('month', flat=True).distinct().order_by('month')

    return Response(list(months), status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_vault_days(request, firm_id, year, month):
    firm = _vault_firm(request, firm_id)
    if isinstance(firm, Response):
        return firm

    days = CloudVaultEntry.objects.filter(
        firm=firm,
        is_deleted=False,
        uploaded_at__year=year,
        uploaded_at__month=month
    ).annotate(
        day=ExtractDay('uploaded_at')
    ).values_list('day', flat=True).distinct().order_by('day')

    return Response(list(days), status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_vault_day_files(request, firm_id, year, month, day):
    firm = _vault_firm(request, firm_id)
    if isinstance(firm, Response):
        return firm

    entries = CloudVaultEntry.objects.filter(
        firm=firm,
        is_deleted=False,
        uploaded_at__year=year,
        uploaded_at__month=month,
        uploaded_at__day=day
    ).order_by('-uploaded_at')

    module_filter = request.query_params.get('module')
    if module_filter:
        entries = entries.filter(module=module_filter)

    data = []
    for entry in entries:
        item = {
            'id': entry.id,
            'file_name': entry.file_name,
            'file_url': entry.file_url,
            'module': entry.module,
            'is_finalized': entry.is_finalized,
            'uploaded_at': entry.uploaded_at.isoformat(),
        }
        if entry.bill:
            item['bill'] = {
                'id': entry.bill.id,
                'status': entry.bill.status,
                'validation_warnings': entry.bill.validation_warnings,
                'raw_data': entry.bill.raw_data,
            }
        if entry.trade_doc:
            item['trade_doc'] = {
                'id': entry.trade_doc.id,
                'status': entry.trade_doc.status,
                'validation_warnings': entry.trade_doc.validation_warnings,
                'raw_data': entry.trade_doc.raw_data,
            }
        data.append(item)

    return Response(data, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_vault_entry(request, pk):
    try:
        entry = CloudVaultEntry.objects.select_related('firm', 'bill', 'trade_doc', 'eway_bill').get(pk=pk)
    except CloudVaultEntry.DoesNotExist:
        return Response({'error': 'Vault entry not found.'}, status=status.HTTP_404_NOT_FOUND)

    permission = HasFirmAccess()
    if not permission.has_object_permission(request, None, entry.firm):
        return Response({'error': 'You do not have access to this firm.'}, status=status.HTTP_403_FORBIDDEN)

    entry.is_deleted = True
    entry.save()

    if entry.bill:
        entry.bill.is_deleted = True
        entry.bill.save()
        log_audit(
            user=request.user,
            firm=entry.firm,
            resource_type=AuditLog.RESOURCE_BILL,
            resource_id=entry.bill.id,
            action=AuditLog.ACTION_DELETE,
            details={'via': 'vault_entry', 'vault_entry_id': entry.id},
            request=request,
        )

    if entry.trade_doc:
        entry.trade_doc.is_deleted = True
        entry.trade_doc.save()
        log_audit(
            user=request.user,
            firm=entry.firm,
            resource_type=AuditLog.RESOURCE_IMPORT_EXPORT,
            resource_id=entry.trade_doc.id,
            action=AuditLog.ACTION_DELETE,
            details={'via': 'vault_entry', 'vault_entry_id': entry.id},
            request=request,
        )

    if entry.eway_bill:
        entry.eway_bill.is_deleted = True
        entry.eway_bill.save()
        log_audit(
            user=request.user,
            firm=entry.firm,
            resource_type=AuditLog.RESOURCE_EWAY_BILL,
            resource_id=entry.eway_bill.id,
            action=AuditLog.ACTION_DELETE,
            details={'via': 'vault_entry', 'vault_entry_id': entry.id},
            request=request,
        )

    return Response({'message': 'Vault entry soft-deleted successfully.'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_stub_file(request, firm_id):
    firm = _vault_firm(request, firm_id)
    if isinstance(firm, Response):
        return firm

    if 'file' not in request.FILES:
        return Response({'error': 'No file uploaded.'}, status=status.HTTP_400_BAD_REQUEST)

    module = request.data.get('module')
    if module not in ['import_export', 'eway_bills']:
        return Response({'error': 'Invalid module for stub upload.'}, status=status.HTTP_400_BAD_REQUEST)

    f = request.FILES['file']
    try:
        file_data, _ext = validate_upload(f, allowed_extensions=STUB_EXTENSIONS)
    except UploadValidationError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    file_url = InvoiceStorageService.upload_export(file_data, f.name, firm.id)

    eway_record = None
    if module == 'eway_bills':
        eway_record = EwayBillRecord.objects.create(
            firm=firm,
            file_name=f.name,
            file_url=file_url,
            file_size=len(file_data),
            uploaded_by=request.user,
            status='uploaded',
        )
        log_audit(
            user=request.user,
            firm=firm,
            resource_type=AuditLog.RESOURCE_EWAY_BILL,
            resource_id=eway_record.id,
            action=AuditLog.ACTION_UPLOAD,
            details={'file_name': f.name, 'module': module},
            request=request,
        )

    entry = CloudVaultEntry.objects.create(
        firm=firm,
        file_name=f.name,
        file_url=file_url,
        module=module,
        is_finalized=True,
        eway_bill=eway_record,
    )

    return Response({
        'id': entry.id,
        'file_name': entry.file_name,
        'file_url': entry.file_url,
        'module': entry.module,
        'eway_bill_id': eway_record.id if eway_record else None,
        'uploaded_at': entry.uploaded_at.isoformat()
    }, status=status.HTTP_201_CREATED)
