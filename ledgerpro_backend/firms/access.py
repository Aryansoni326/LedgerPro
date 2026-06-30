"""
Centralized firm-scoped resource access checks.

Every firm-bound endpoint should resolve resources through these helpers so
cross-accountant access is blocked consistently.
"""
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from firms.models import Firm
from firms.permissions import HasFirmAccess


def _deny():
    return Response(
        {'error': 'You do not have access to this firm.'},
        status=status.HTTP_403_FORBIDDEN,
    )


def get_firm_or_403(request, firm_id: int) -> Firm | Response:
    """Return the firm if the authenticated user owns it, else a 403 Response."""
    try:
        firm = Firm.objects.get(pk=firm_id)
    except Firm.DoesNotExist:
        return Response({'error': 'Firm not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not HasFirmAccess().has_object_permission(request, None, firm):
        return _deny()
    return firm


def get_firm_object_or_403(request, obj) -> bool:
    """Return True if user may access obj.firm, else False (caller returns 403)."""
    firm = getattr(obj, 'firm', None)
    if firm is None:
        return False
    return HasFirmAccess().has_object_permission(request, None, firm)


def get_bill_for_user(user, pk: int, *, include_deleted: bool = False):
    qs = __import__('invoices.models', fromlist=['Bill']).Bill.objects.select_related('firm')
    if not include_deleted:
        qs = qs.filter(is_deleted=False)
    return get_object_or_404(qs, pk=pk, firm__created_by=user)


def get_trade_doc_for_user(user, pk: int):
    from trade_docs.models import ImportExportRecord
    return get_object_or_404(
        ImportExportRecord.objects.select_related('firm'),
        pk=pk,
        is_deleted=False,
        firm__created_by=user,
    )


def get_eway_bill_for_user(user, pk: int):
    from eway_bills.models import EwayBillRecord
    return get_object_or_404(
        EwayBillRecord.objects.select_related('firm'),
        pk=pk,
        is_deleted=False,
        firm__created_by=user,
    )


def get_vault_entry_for_user(user, pk: int):
    from vault.models import CloudVaultEntry
    return get_object_or_404(
        CloudVaultEntry.objects.select_related('firm'),
        pk=pk,
        is_deleted=False,
        firm__created_by=user,
    )
