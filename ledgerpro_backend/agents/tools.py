"""
Agent tool registry.

Each tool is a plain function that calls an existing service/queryset and
returns a JSON-serialisable dict.  Agents select tools by name from their
allowed set — they never import services directly.

Tool categories:
    READ  — safe, no side effects, any agent can call these.
    WRITE — mutating, ALWAYS gated by PendingApproval.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# READ tools — safe queries that return evidence
# ═══════════════════════════════════════════════════════════════════════

def tool_risk_summary(firm_id: int, **kwargs) -> dict:
    """Aggregate risk signals by severity and category for a firm."""
    from intelligence.models import RiskSignal
    qs = RiskSignal.objects.filter(firm_id=firm_id)

    status_filter = kwargs.get('status', 'open')
    if status_filter != 'all':
        qs = qs.filter(status=status_filter)

    by_severity = dict(qs.values_list('severity').annotate(c=Count('id')).order_by())
    by_category = dict(qs.values_list('category').annotate(c=Count('id')).order_by())
    total = qs.count()

    top_signals = list(
        qs.order_by('-severity', '-created_at')[:5].values(
            'id', 'severity', 'category', 'title', 'description', 'confidence',
        )
    )
    for s in top_signals:
        s['confidence'] = str(s['confidence'])

    return {
        'total': total, 'by_severity': by_severity,
        'by_category': by_category, 'top_signals': top_signals,
    }


def tool_reconciliation_status(firm_id: int, **kwargs) -> dict:
    """Latest reconciliation run results for a firm."""
    from intelligence.models import ReconciliationRun, ReconciliationException
    run = ReconciliationRun.objects.filter(firm_id=firm_id).order_by('-started_at').first()
    if not run:
        return {'status': 'no_runs', 'message': 'No reconciliation has been run for this firm.'}

    pending_exceptions = ReconciliationException.objects.filter(
        firm_id=firm_id, review_status='pending',
    ).count()

    top_exceptions = list(
        ReconciliationException.objects.filter(firm_id=firm_id, review_status='pending')
        .order_by('-confidence')[:5]
        .values('id', 'mismatch_cause', 'confidence', 'reason',
                'expected_amount', 'actual_amount', 'difference')
    )
    for e in top_exceptions:
        for k in ('confidence', 'expected_amount', 'actual_amount', 'difference'):
            if e[k] is not None:
                e[k] = str(e[k])

    return {
        'run_id': run.id,
        'status': run.status,
        'started_at': run.started_at.isoformat(),
        'exact_matches': run.exact_matches,
        'fuzzy_matches': run.fuzzy_matches,
        'exceptions_created': run.exceptions_created,
        'unmatched': run.unmatched,
        'pending_exceptions': pending_exceptions,
        'top_exceptions': top_exceptions,
    }


def tool_cashflow_forecast(firm_id: int, **kwargs) -> dict:
    """Current cash-flow forecast for a firm."""
    from intelligence.forecasting import CashFlowForecaster
    forecaster = CashFlowForecaster()
    result = forecaster.forecast(firm_id, as_of=date.today())
    return {
        'current_balance': str(result.current_balance),
        'position_30d': str(result.position_30d),
        'position_60d': str(result.position_60d),
        'position_90d': str(result.position_90d),
        'pressure_day': result.pressure_day,
        'pressure_amount': str(result.pressure_amount) if result.pressure_amount else None,
        'risk_explanation': result.risk_explanation,
        'health_score': str(result.health_score),
        'avg_collection_days': str(result.avg_collection_days),
        'avg_payment_days': str(result.avg_payment_days),
        'top_delayed_receivables': result.top_delayed_receivables,
        'top_upcoming_payables': result.top_upcoming_payables,
    }


def tool_vendor_scores(firm_id: int, **kwargs) -> dict:
    """All vendor scores for a firm."""
    from intelligence.models import VendorScore
    qs = VendorScore.objects.filter(firm_id=firm_id).select_related('vendor').order_by('-overall_score')
    limit = kwargs.get('limit', 10)
    results = []
    for vs in qs[:limit]:
        results.append({
            'vendor_id': vs.vendor_id,
            'vendor_name': vs.vendor.name,
            'overall_score': str(vs.overall_score),
            'breakdown': vs.breakdown,
        })
    return {'count': qs.count(), 'results': results}


def tool_customer_scores(firm_id: int, **kwargs) -> dict:
    """All customer scores for a firm."""
    from intelligence.models import CustomerScore
    qs = CustomerScore.objects.filter(firm_id=firm_id).select_related('customer').order_by('-overall_score')
    limit = kwargs.get('limit', 10)
    results = []
    for cs in qs[:limit]:
        results.append({
            'customer_id': cs.customer_id,
            'customer_name': cs.customer.name,
            'overall_score': str(cs.overall_score),
            'breakdown': cs.breakdown,
        })
    return {'count': qs.count(), 'results': results}


def tool_vendor_detail(firm_id: int, vendor_id: int = None, **kwargs) -> dict:
    """Detailed vendor score breakdown."""
    from intelligence.models import VendorScore
    try:
        vs = VendorScore.objects.select_related('vendor').get(
            firm_id=firm_id, vendor_id=vendor_id,
        )
    except VendorScore.DoesNotExist:
        return {'error': f'No score for vendor {vendor_id}.'}
    return {
        'vendor_id': vs.vendor_id, 'vendor_name': vs.vendor.name,
        'overall_score': str(vs.overall_score),
        'previous_score': str(vs.previous_score) if vs.previous_score else None,
        'sub_metrics': {
            'invoice_consistency': str(vs.invoice_consistency),
            'payment_history': str(vs.payment_history),
            'price_stability': str(vs.price_stability),
            'document_quality': str(vs.document_quality),
            'bank_change_frequency': str(vs.bank_change_frequency),
            'anomaly_history': str(vs.anomaly_history),
        },
        'breakdown': vs.breakdown,
    }


def tool_customer_detail(firm_id: int, customer_id: int = None, **kwargs) -> dict:
    """Detailed customer score breakdown."""
    from intelligence.models import CustomerScore
    try:
        cs = CustomerScore.objects.select_related('customer').get(
            firm_id=firm_id, customer_id=customer_id,
        )
    except CustomerScore.DoesNotExist:
        return {'error': f'No score for customer {customer_id}.'}
    return {
        'customer_id': cs.customer_id, 'customer_name': cs.customer.name,
        'overall_score': str(cs.overall_score),
        'previous_score': str(cs.previous_score) if cs.previous_score else None,
        'sub_metrics': {
            'payment_history': str(cs.payment_history),
            'avg_payment_time_trend': str(cs.avg_payment_time_trend),
            'credit_exposure': str(cs.credit_exposure),
            'revenue_contribution': str(cs.revenue_contribution),
        },
        'breakdown': cs.breakdown,
    }


def tool_overdue_receivables(firm_id: int, **kwargs) -> dict:
    """Outstanding overdue receivables for a firm."""
    from intelligence.models import Transaction
    today = date.today()
    qs = Transaction.objects.filter(
        firm_id=firm_id, direction='inflow', txn_type='invoice',
        status__in=['pending', 'partially_matched'],
        due_date__lt=today,
    ).select_related('customer').order_by('-amount')

    items = []
    entity_refs = []
    total = Decimal('0')
    for t in qs[:20]:
        items.append({
            'id': t.id, 'reference': t.reference_number,
            'amount': str(t.amount), 'currency': t.currency,
            'due_date': str(t.due_date),
            'days_overdue': (today - t.due_date).days,
            'customer': t.customer.name if t.customer else '',
            'customer_id': t.customer_id,
        })
        entity_refs.append({'type': 'transaction', 'id': t.id, 'url': f'/transactions/{t.id}'})
        if t.customer_id:
            entity_refs.append({'type': 'customer', 'id': t.customer_id, 'url': f'/customers/{t.customer_id}'})
        total += t.amount
    return {'total_overdue': str(total), 'count': qs.count(), 'items': items, 'entity_refs': entity_refs}


def tool_payables_due(firm_id: int, **kwargs) -> dict:
    """Upcoming payables in the next 90 days."""
    from intelligence.models import Transaction
    today = date.today()
    window = today + timedelta(days=int(kwargs.get('days', 90)))
    qs = Transaction.objects.filter(
        firm_id=firm_id, direction='outflow',
        status__in=['pending', 'completed', 'partially_matched'],
        due_date__gt=today, due_date__lte=window,
    ).select_related('vendor').order_by('due_date')

    items = []
    entity_refs = []
    total = Decimal('0')
    for t in qs[:20]:
        items.append({
            'id': t.id, 'reference': t.reference_number,
            'amount': str(t.amount), 'currency': t.currency,
            'due_date': str(t.due_date),
            'days_until_due': (t.due_date - today).days,
            'vendor': t.vendor.name if t.vendor else '',
            'vendor_id': t.vendor_id,
        })
        entity_refs.append({'type': 'transaction', 'id': t.id, 'url': f'/transactions/{t.id}'})
        if t.vendor_id:
            entity_refs.append({'type': 'vendor', 'id': t.vendor_id, 'url': f'/vendors/{t.vendor_id}'})
        total += t.amount
    return {'total_due': str(total), 'count': qs.count(), 'items': items, 'entity_refs': entity_refs}


def tool_audit_trail(firm_id: int, **kwargs) -> dict:
    """Recent audit log entries for a firm."""
    from audit.models import AuditLog
    limit = kwargs.get('limit', 20)
    qs = AuditLog.objects.filter(firm_id=firm_id).order_by('-timestamp')[:limit]
    return {
        'entries': [{
            'id': a.id, 'action': a.action,
            'resource_type': a.resource_type,
            'resource_id': a.resource_id,
            'user': a.user.email if a.user else 'system',
            'timestamp': a.timestamp.isoformat(),
            'details': a.details,
        } for a in qs]
    }


def tool_recon_exceptions(firm_id: int, **kwargs) -> dict:
    """Unresolved reconciliation exceptions."""
    from intelligence.models import ReconciliationException
    status_filter = kwargs.get('review_status', 'pending')
    qs = ReconciliationException.objects.filter(
        firm_id=firm_id, review_status=status_filter,
    ).order_by('-confidence')

    items = []
    for e in qs[:15]:
        items.append({
            'id': e.id,
            'mismatch_cause': e.mismatch_cause,
            'confidence': str(e.confidence),
            'reason': e.reason,
            'expected_amount': str(e.expected_amount) if e.expected_amount else None,
            'actual_amount': str(e.actual_amount) if e.actual_amount else None,
            'difference': str(e.difference) if e.difference else None,
            'transaction_id': e.transaction_id,
        })
    return {'count': qs.count(), 'items': items}


def tool_biggest_expenses(firm_id: int, **kwargs) -> dict:
    """Top expenses by amount for a firm (answers 'biggest expenses')."""
    from intelligence.models import Transaction
    days = int(kwargs.get('days', 90))
    today = date.today()
    qs = Transaction.objects.filter(
        firm_id=firm_id, direction='outflow',
        status__in=['completed', 'fully_matched'],
        txn_date__gte=today - timedelta(days=days),
    ).select_related('vendor').order_by('-amount')

    items = []
    entity_refs = []
    total = Decimal('0')
    for t in qs[:15]:
        items.append({
            'id': t.id, 'reference': t.reference_number,
            'amount': str(t.amount), 'currency': t.currency,
            'txn_date': str(t.txn_date), 'txn_type': t.txn_type,
            'description': t.description[:100],
            'vendor': t.vendor.name if t.vendor else '',
            'vendor_id': t.vendor_id,
        })
        entity_refs.append({'type': 'transaction', 'id': t.id, 'url': f'/transactions/{t.id}'})
        if t.vendor_id:
            entity_refs.append({'type': 'vendor', 'id': t.vendor_id, 'url': f'/vendors/{t.vendor_id}'})
        total += t.amount
    return {
        'period_days': days, 'total_expenses': str(total),
        'count': qs.count(), 'items': items, 'entity_refs': entity_refs,
    }


def tool_customers_owing(firm_id: int, **kwargs) -> dict:
    """Customers with outstanding receivables (answers 'who owes money')."""
    from intelligence.models import Transaction
    from django.db.models import Sum as DSum
    today = date.today()
    qs = (
        Transaction.objects.filter(
            firm_id=firm_id, direction='inflow',
            status__in=['pending', 'partially_matched'],
            customer__isnull=False,
        )
        .values('customer_id', 'customer__name')
        .annotate(total_owed=DSum('amount'))
        .order_by('-total_owed')
    )

    items = []
    entity_refs = []
    for row in qs[:15]:
        items.append({
            'customer_id': row['customer_id'],
            'customer_name': row['customer__name'],
            'total_owed': str(row['total_owed']),
        })
        entity_refs.append({
            'type': 'customer', 'id': row['customer_id'],
            'url': f'/customers/{row["customer_id"]}',
        })

    grand_total = sum(Decimal(i['total_owed']) for i in items)
    return {
        'grand_total_owed': str(grand_total),
        'count': len(items), 'items': items, 'entity_refs': entity_refs,
    }


def tool_profit_analysis(firm_id: int, **kwargs) -> dict:
    """Simple profit/loss analysis (answers 'why profit decreased')."""
    from intelligence.models import Transaction
    days = int(kwargs.get('days', 90))
    today = date.today()
    current_start = today - timedelta(days=days)
    prior_start = current_start - timedelta(days=days)

    def _period_totals(start, end):
        base = Transaction.objects.filter(
            firm_id=firm_id, txn_date__gte=start, txn_date__lt=end,
            status__in=['completed', 'fully_matched'],
        )
        inflows = base.filter(direction='inflow').aggregate(
            s=Sum('amount', default=Decimal('0')))['s']
        outflows = base.filter(direction='outflow').aggregate(
            s=Sum('amount', default=Decimal('0')))['s']
        return inflows, outflows

    curr_in, curr_out = _period_totals(current_start, today)
    prev_in, prev_out = _period_totals(prior_start, current_start)

    curr_profit = curr_in - curr_out
    prev_profit = prev_in - prev_out
    change = curr_profit - prev_profit

    # Identify top contributors to change
    top_outflow_increase = list(
        Transaction.objects.filter(
            firm_id=firm_id, direction='outflow',
            status__in=['completed', 'fully_matched'],
            txn_date__gte=current_start,
        ).select_related('vendor').order_by('-amount')[:5].values(
            'id', 'amount', 'vendor__name', 'txn_type', 'description',
        )
    )
    entity_refs = []
    for t in top_outflow_increase:
        t['amount'] = str(t['amount'])
        entity_refs.append({'type': 'transaction', 'id': t['id'], 'url': f'/transactions/{t["id"]}'})

    return {
        'period_days': days,
        'current_revenue': str(curr_in), 'current_expenses': str(curr_out),
        'current_profit': str(curr_profit),
        'prior_revenue': str(prev_in), 'prior_expenses': str(prev_out),
        'prior_profit': str(prev_profit),
        'profit_change': str(change),
        'top_expense_contributors': top_outflow_increase,
        'entity_refs': entity_refs,
    }


def tool_transaction_detail(firm_id: int, transaction_id: int = None, **kwargs) -> dict:
    """Look up a specific transaction by ID (for drill-down from prior evidence)."""
    from intelligence.models import Transaction
    if not transaction_id:
        return {'error': 'transaction_id required.'}
    try:
        t = Transaction.objects.select_related('vendor', 'customer').get(
            pk=transaction_id, firm_id=firm_id,
        )
    except Transaction.DoesNotExist:
        return {'error': f'Transaction {transaction_id} not found.'}
    return {
        'id': t.id, 'txn_type': t.txn_type, 'direction': t.direction,
        'status': t.status, 'reference': t.reference_number,
        'amount': str(t.amount), 'currency': t.currency,
        'txn_date': str(t.txn_date),
        'due_date': str(t.due_date) if t.due_date else None,
        'description': t.description,
        'vendor': t.vendor.name if t.vendor else None,
        'vendor_id': t.vendor_id,
        'customer': t.customer.name if t.customer else None,
        'customer_id': t.customer_id,
        'metadata': t.metadata,
        'entity_refs': [
            {'type': 'transaction', 'id': t.id, 'url': f'/transactions/{t.id}'},
        ],
    }


# ═══════════════════════════════════════════════════════════════════════
# WRITE tools — always gated by PendingApproval
# ═══════════════════════════════════════════════════════════════════════

def tool_flag_transaction(firm_id: int, transaction_id: int = None, reason: str = '', **kwargs) -> dict:
    """Propose flagging a transaction for review. Returns a PendingApproval.

    When ``transaction_id`` is omitted, auto-selects the highest-severity open
    risk signal linked to a transaction (duplicate / unusual amount first).
    """
    from intelligence.models import RiskSignal

    resolved_id = transaction_id
    resolved_reason = reason
    if not resolved_id:
        from django.db.models import Case, IntegerField, When

        signal = (
            RiskSignal.objects.filter(
                firm_id=firm_id,
                status=RiskSignal.Status.OPEN,
                entity_type='transaction',
                category__in=[
                    RiskSignal.Category.DUPLICATE_INVOICE,
                    RiskSignal.Category.UNUSUAL_AMOUNT,
                    RiskSignal.Category.VENDOR_RISK,
                ],
            )
            .annotate(
                _prio=Case(
                    When(category=RiskSignal.Category.DUPLICATE_INVOICE, then=0),
                    When(category=RiskSignal.Category.UNUSUAL_AMOUNT, then=1),
                    When(category=RiskSignal.Category.VENDOR_RISK, then=2),
                    default=9,
                    output_field=IntegerField(),
                ),
                _sev=Case(
                    When(severity='critical', then=0),
                    When(severity='high', then=1),
                    When(severity='medium', then=2),
                    default=3,
                    output_field=IntegerField(),
                ),
            )
            .order_by('_prio', '_sev', '-confidence', '-created_at')
            .first()
        )
        if signal:
            resolved_id = signal.entity_id
            resolved_reason = resolved_reason or signal.title

    if not resolved_id:
        return {'error': 'No transaction_id provided and no open risk signals to flag.'}

    return _propose_action(
        firm_id=firm_id,
        action='flag_transaction',
        params={'transaction_id': resolved_id, 'reason': resolved_reason or 'Flagged from risk review'},
        reason=resolved_reason or 'Flagged from risk review',
    )


def tool_send_payment_reminder(firm_id: int, customer_id: int = None, invoice_ids: list = None, **kwargs) -> dict:
    """Propose sending a payment reminder. Auto-picks top overdue customer when omitted."""
    from datetime import date

    from intelligence.models import Transaction

    resolved_customer = customer_id
    resolved_invoices = list(invoice_ids or [])
    if not resolved_customer:
        overdue = (
            Transaction.objects.filter(
                firm_id=firm_id,
                direction='inflow',
                txn_type='invoice',
                status__in=['pending', 'partially_matched'],
                due_date__lt=date.today(),
                customer_id__isnull=False,
            )
            .order_by('-amount')
            .first()
        )
        if overdue:
            resolved_customer = overdue.customer_id
            resolved_invoices = [overdue.id]

    if not resolved_customer:
        return {'error': 'No customer_id provided and no overdue receivables found.'}

    return _propose_action(
        firm_id=firm_id,
        action='send_payment_reminder',
        params={'customer_id': resolved_customer, 'invoice_ids': resolved_invoices},
        reason=kwargs.get('reason', 'Overdue invoices detected — collection reminder proposed.'),
    )


def tool_update_risk_status(firm_id: int, signal_id: int = None, new_status: str = '', **kwargs) -> dict:
    """Propose changing a risk signal's status. Auto-picks top open signal when omitted."""
    from intelligence.models import RiskSignal

    resolved_id = signal_id
    resolved_status = new_status or 'acknowledged'
    if not resolved_id:
        signal = (
            RiskSignal.objects.filter(firm_id=firm_id, status=RiskSignal.Status.OPEN)
            .order_by('-severity', '-created_at')
            .first()
        )
        if signal:
            resolved_id = signal.id

    if not resolved_id:
        return {'error': 'No signal_id provided and no open risk signals found.'}

    return _propose_action(
        firm_id=firm_id,
        action='update_risk_status',
        params={'signal_id': resolved_id, 'new_status': resolved_status},
        reason=kwargs.get('reason', f'Propose status → {resolved_status}'),
    )


def tool_risk_signal_graph(firm_id: int, signal_id: int = None, **kwargs) -> dict:
    """Full entity graph connected to a risk signal."""
    from intelligence.graph import risk_signal_graph
    if not signal_id:
        return {'error': 'signal_id is required'}
    return risk_signal_graph(firm_id, signal_id)


def tool_vendor_graph(firm_id: int, vendor_id: int = None, **kwargs) -> dict:
    """Full relationship history graph for a vendor."""
    from intelligence.graph import vendor_history
    if not vendor_id:
        return {'error': 'vendor_id is required'}
    return vendor_history(firm_id, vendor_id)


def tool_customer_graph(firm_id: int, customer_id: int = None, **kwargs) -> dict:
    """Full relationship history graph for a customer."""
    from intelligence.graph import customer_history
    if not customer_id:
        return {'error': 'customer_id is required'}
    return customer_history(firm_id, customer_id)


def tool_evidence_drilldown(firm_id: int, entity_type: str = '', entity_id: int = None, **kwargs) -> dict:
    """Evidence chain from any entity type."""
    from intelligence.graph import evidence_drilldown
    if not entity_type or not entity_id:
        return {'error': 'entity_type and entity_id are required'}
    return evidence_drilldown(firm_id, entity_type, entity_id)


def _propose_action(firm_id: int, action: str, params: dict, reason: str) -> dict:
    """Shared helper — marks the action as requiring approval, NOT executing it."""
    return {
        '_requires_approval': True,
        'proposed_action': action,
        'action_params': params,
        'reason': reason,
        'message': f'Action "{action}" requires human approval before execution.',
    }


# ═══════════════════════════════════════════════════════════════════════
# Registry
# ═══════════════════════════════════════════════════════════════════════

TOOL_REGISTRY: dict[str, dict] = {
    # READ tools
    'risk_summary':          {'fn': tool_risk_summary, 'write': False, 'description': 'Aggregate risk signals by severity and category.'},
    'reconciliation_status': {'fn': tool_reconciliation_status, 'write': False, 'description': 'Latest reconciliation run results and top exceptions.'},
    'cashflow_forecast':     {'fn': tool_cashflow_forecast, 'write': False, 'description': 'Current and projected 30/60/90-day cash positions.'},
    'vendor_scores':         {'fn': tool_vendor_scores, 'write': False, 'description': 'Ranked vendor scores with breakdowns.'},
    'customer_scores':       {'fn': tool_customer_scores, 'write': False, 'description': 'Ranked customer scores with breakdowns.'},
    'vendor_detail':         {'fn': tool_vendor_detail, 'write': False, 'description': 'Detailed vendor score breakdown by sub-metric.'},
    'customer_detail':       {'fn': tool_customer_detail, 'write': False, 'description': 'Detailed customer score breakdown by sub-metric.'},
    'overdue_receivables':   {'fn': tool_overdue_receivables, 'write': False, 'description': 'Outstanding overdue invoices.'},
    'payables_due':          {'fn': tool_payables_due, 'write': False, 'description': 'Upcoming payables in next N days.'},
    'audit_trail':           {'fn': tool_audit_trail, 'write': False, 'description': 'Recent audit log entries for a firm.'},
    'recon_exceptions':      {'fn': tool_recon_exceptions, 'write': False, 'description': 'Unresolved reconciliation exceptions.'},
    'biggest_expenses':      {'fn': tool_biggest_expenses, 'write': False, 'description': 'Top expenses by amount.'},
    'customers_owing':       {'fn': tool_customers_owing, 'write': False, 'description': 'Customers with outstanding receivables.'},
    'profit_analysis':       {'fn': tool_profit_analysis, 'write': False, 'description': 'Profit/loss analysis with period comparison.'},
    'transaction_detail':    {'fn': tool_transaction_detail, 'write': False, 'description': 'Look up a specific transaction for drill-down.'},
    'risk_signal_graph':     {'fn': tool_risk_signal_graph, 'write': False, 'description': 'Full entity graph connected to a risk signal.'},
    'vendor_graph':          {'fn': tool_vendor_graph, 'write': False, 'description': 'Full relationship history graph for a vendor.'},
    'customer_graph':        {'fn': tool_customer_graph, 'write': False, 'description': 'Full relationship history graph for a customer.'},
    'evidence_drilldown':    {'fn': tool_evidence_drilldown, 'write': False, 'description': 'Evidence chain from any entity (transaction, risk_signal, vendor, customer, trade_doc).'},
    # WRITE tools
    'flag_transaction':      {'fn': tool_flag_transaction, 'write': True, 'description': 'Flag a transaction for review (requires approval).'},
    'send_payment_reminder': {'fn': tool_send_payment_reminder, 'write': True, 'description': 'Send a payment reminder to a customer (requires approval).'},
    'update_risk_status':    {'fn': tool_update_risk_status, 'write': True, 'description': 'Change a risk signal status (requires approval).'},
}
