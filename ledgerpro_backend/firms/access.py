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


def _scoped_get_or_404(model, *, user, pk, select_related=None, q_filter=None, **extra_filters):
    """Generic helper for firm-scoped resources.

    `q_filter` defaults to the standard `firm_filter_for_user(user)` for models
    with a direct `firm` FK. Models that scope through a parent relation (for
    example `AgentAction -> conversation -> firm`) can provide a custom filter.
    """
    qs = model.objects.all()
    if select_related:
        qs = qs.select_related(*select_related)
    if q_filter is None:
        q_filter = firm_filter_for_user(user)
    return get_object_or_404(qs.filter(q_filter, **extra_filters), pk=pk)


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


def get_vendor_for_user(user, pk: int):
    from intelligence.models import Vendor
    return _scoped_get_or_404(
        Vendor,
        user=user,
        pk=pk,
        select_related=('firm',),
    )


def get_customer_for_user(user, pk: int):
    from intelligence.models import Customer
    return _scoped_get_or_404(
        Customer,
        user=user,
        pk=pk,
        select_related=('firm',),
    )


def get_transaction_for_user(user, pk: int):
    from intelligence.models import Transaction
    return _scoped_get_or_404(
        Transaction,
        user=user,
        pk=pk,
        select_related=('firm',),
    )


def get_risk_signal_for_user(user, pk: int):
    from intelligence.models import RiskSignal
    return _scoped_get_or_404(
        RiskSignal,
        user=user,
        pk=pk,
        select_related=('firm',),
    )


def get_document_for_user(user, pk: int):
    from intelligence.models import Document
    return _scoped_get_or_404(
        Document,
        user=user,
        pk=pk,
        select_related=('firm',),
        is_deleted=False,
    )


def get_reconciliation_link_for_user(user, pk: int):
    from intelligence.models import ReconciliationLink
    return _scoped_get_or_404(
        ReconciliationLink,
        user=user,
        pk=pk,
        select_related=('firm', 'transaction', 'matched_transaction'),
        is_deleted=False,
    )


def get_reconciliation_exception_for_user(user, pk: int):
    from intelligence.models import ReconciliationException
    return _scoped_get_or_404(
        ReconciliationException,
        user=user,
        pk=pk,
        select_related=('firm', 'transaction', 'candidate_transaction'),
        is_deleted=False,
    )


def get_reconciliation_run_for_user(user, pk: int):
    from intelligence.models import ReconciliationRun
    return _scoped_get_or_404(
        ReconciliationRun,
        user=user,
        pk=pk,
        select_related=('firm',),
        is_deleted=False,
    )


def get_financial_snapshot_for_user(user, pk: int):
    from intelligence.models import FinancialSnapshot
    return _scoped_get_or_404(
        FinancialSnapshot,
        user=user,
        pk=pk,
        select_related=('firm',),
        is_deleted=False,
    )


def get_vendor_score_for_user(user, pk: int):
    from intelligence.models import VendorScore
    return _scoped_get_or_404(
        VendorScore,
        user=user,
        pk=pk,
        select_related=('firm', 'vendor'),
        is_deleted=False,
    )


def get_customer_score_for_user(user, pk: int):
    from intelligence.models import CustomerScore
    return _scoped_get_or_404(
        CustomerScore,
        user=user,
        pk=pk,
        select_related=('firm', 'customer'),
        is_deleted=False,
    )


def get_trade_finance_link_for_user(user, pk: int):
    from intelligence.models import TradeFinanceLink
    return _scoped_get_or_404(
        TradeFinanceLink,
        user=user,
        pk=pk,
        select_related=('firm', 'vendor', 'invoice_txn', 'payment_txn', 'purchase_order_txn', 'trade_doc'),
        is_deleted=False,
    )


def get_agent_conversation_for_user(user, pk):
    from agents.models import AgentConversation
    return _scoped_get_or_404(
        AgentConversation,
        user=user,
        pk=pk,
        select_related=('firm', 'user', 'session'),
    )


def get_agent_action_for_user(user, pk: int):
    from agents.models import AgentAction
    return _scoped_get_or_404(
        AgentAction,
        user=user,
        pk=pk,
        select_related=('conversation', 'conversation__firm'),
        q_filter=Q(conversation__firm__created_by=user) | Q(conversation__firm__owner_email__iexact=user.email),
    )


def get_pending_approval_for_user(user, pk):
    from agents.models import PendingApproval
    return _scoped_get_or_404(
        PendingApproval,
        user=user,
        pk=pk,
        select_related=('firm', 'conversation'),
    )


def get_chat_session_for_user(user, pk):
    from agents.models import ChatSession
    return _scoped_get_or_404(
        ChatSession,
        user=user,
        pk=pk,
        select_related=('firm', 'user'),
    )


def assert_can_write_firm(user, firm) -> Response | None:
    """Return a 403 Response if user cannot mutate the firm, else None."""
    if is_firm_creator(user, firm):
        return None
    if is_firm_owner_email(user, firm):
        return _deny_write()
    return _deny()
