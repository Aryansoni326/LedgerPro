"""
Centralized firm-scoped resource access checks.

Every firm-bound endpoint should resolve resources through these helpers so
cross-accountant access is blocked consistently. Firm owners (matched by
owner_email) receive read-only access.
"""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from firms.models import Firm
from firms.permissions import HasFirmAccess, is_firm_creator, is_firm_owner_email


def _deny():
    return Response(
        {'error': 'You do not have access to this firm.'},
        status=status.HTTP_403_FORBIDDEN,
    )


def _deny_write():
    return Response(
        {'error': 'Owner accounts have read-only access. Changes must be made by your accountant.'},
        status=status.HTTP_403_FORBIDDEN,
    )


def firms_queryset_for_user(user):
    """Firms the user created or owns via owner_email."""
    return Firm.objects.filter(
        Q(created_by=user) | Q(owner_email__iexact=user.email)
    ).distinct()


def get_firm_or_403(request, firm_id: int, *, require_write: bool = False) -> Firm | Response:
    """Return the firm if the authenticated user may access it, else a 403 Response."""
    from rest_framework.permissions import SAFE_METHODS

    try:
        firm = Firm.objects.get(pk=firm_id)
    except Firm.DoesNotExist:
        return Response({'error': 'Firm not found.'}, status=status.HTTP_404_NOT_FOUND)

    if is_firm_creator(request.user, firm):
        return firm

    if is_firm_owner_email(request.user, firm):
        if require_write or request.method not in SAFE_METHODS:
            return _deny_write()
        return firm

    return _deny()


def get_firm_object_or_403(request, obj) -> bool:
    """Return True if user may access obj.firm, else False (caller returns 403)."""
    firm = getattr(obj, 'firm', None)
    if firm is None:
        return False
    return HasFirmAccess().has_object_permission(request, None, firm)


def firm_filter_for_user(user) -> Q:
    return Q(firm__created_by=user) | Q(firm__owner_email__iexact=user.email)


def get_bill_for_user(user, pk: int, *, include_deleted: bool = False):
    qs = __import__('invoices.models', fromlist=['Bill']).Bill.objects.select_related('firm')
    if not include_deleted:
        qs = qs.filter(is_deleted=False)
    return get_object_or_404(qs.filter(firm_filter_for_user(user)), pk=pk)


def get_trade_doc_for_user(user, pk: int):
    from trade_docs.models import ImportExportRecord
    return get_object_or_404(
        ImportExportRecord.objects.select_related('firm').filter(
            firm_filter_for_user(user),
            is_deleted=False,
        ),
        pk=pk,
    )


def get_eway_bill_for_user(user, pk: int):
    from eway_bills.models import EwayBillRecord
    return get_object_or_404(
        EwayBillRecord.objects.select_related('firm').filter(
            firm_filter_for_user(user),
            is_deleted=False,
        ),
        pk=pk,
    )


def get_vault_entry_for_user(user, pk: int):
    from vault.models import CloudVaultEntry
    return get_object_or_404(
        CloudVaultEntry.objects.select_related('firm').filter(
            firm_filter_for_user(user),
            is_deleted=False,
        ),
        pk=pk,
    )


def assert_can_write_firm(user, firm) -> Response | None:
    """Return a 403 Response if user cannot mutate the firm, else None."""
    if is_firm_creator(user, firm):
        return None
    if is_firm_owner_email(user, firm):
        return _deny_write()
    return _deny()
