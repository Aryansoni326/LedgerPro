"""
Vendor & Customer scoring engine — transparent, auditable credit/risk scores.

Every sub-metric is computed from concrete ledger data, documented with
its weight and reasoning, and stored in a JSON ``breakdown`` so SME
users and accountants can trust and audit the number.

┌──────────────────────────────────────────────────────────────────────┐
│  VENDOR SCORE (0–100)                                               │
│  ════════════════════                                                │
│  invoice_consistency   ×0.20  — regularity + accuracy of invoices   │
│  payment_history       ×0.25  — on-time payment ratio for vendor    │
│  price_stability       ×0.15  — coefficient of variation of prices  │
│  document_quality      ×0.15  — extraction success rate             │
│  bank_change_frequency ×0.10  — how often bank details change       │
│  anomaly_history       ×0.15  — count/severity of risk signals      │
├──────────────────────────────────────────────────────────────────────┤
│  CUSTOMER SCORE (0–100)                                             │
│  ══════════════════════                                              │
│  payment_history         ×0.30  — on-time vs late ratio             │
│  avg_payment_time_trend  ×0.20  — getting faster/slower?            │
│  credit_exposure         ×0.25  — outstanding vs total volume       │
│  revenue_contribution    ×0.25  — share of firm revenue             │
└──────────────────────────────────────────────────────────────────────┘
"""
import logging
import statistics
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Avg, Count, F, Q, Sum
from django.utils import timezone

from .models import (
    Customer,
    CustomerScore,
    Document,
    RiskSignal,
    Transaction,
    Vendor,
    VendorScore,
)

logger = logging.getLogger(__name__)

_ZERO = Decimal("0.00")
_HUNDRED = Decimal("100.00")
_Q = Decimal("0.01")


def _clamp(val: Decimal) -> Decimal:
    return max(_ZERO, min(_HUNDRED, val)).quantize(_Q, rounding=ROUND_HALF_UP)


# ═══════════════════════════════════════════════════════════════════════
# Vendor Scoring
# ═══════════════════════════════════════════════════════════════════════

VENDOR_WEIGHTS = {
    'invoice_consistency': Decimal("0.20"),
    'payment_history': Decimal("0.25"),
    'price_stability': Decimal("0.15"),
    'document_quality': Decimal("0.15"),
    'bank_change_frequency': Decimal("0.10"),
    'anomaly_history': Decimal("0.15"),
}


def compute_vendor_score(vendor: Vendor, as_of: date | None = None) -> VendorScore:
    """Compute or update the VendorScore for a single vendor."""
    today = as_of or date.today()
    firm = vendor.firm

    txns = Transaction.objects.filter(
        firm=firm, vendor=vendor,
    ).exclude(status='cancelled')

    breakdown: dict = {}
    metrics: dict[str, Decimal] = {}

    # ── 1. Invoice consistency (20%) ─────────────────────────────────
    inv_txns = txns.filter(txn_type='invoice')
    inv_count = inv_txns.count()

    if inv_count == 0:
        metrics['invoice_consistency'] = Decimal("50")
        breakdown['invoice_consistency'] = {
            'score': '50.00', 'reason': 'No invoices on record — neutral score.',
            'invoice_count': 0,
        }
    else:
        dates = list(inv_txns.order_by('txn_date').values_list('txn_date', flat=True))
        if len(dates) >= 2:
            gaps = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
            avg_gap = statistics.mean(gaps)
            gap_cv = statistics.stdev(gaps) / avg_gap if avg_gap > 0 and len(gaps) > 1 else 0
            regularity_score = max(0, 100 - gap_cv * 30)
        else:
            regularity_score = 70

        metrics['invoice_consistency'] = _clamp(Decimal(str(regularity_score)))
        breakdown['invoice_consistency'] = {
            'score': str(metrics['invoice_consistency']),
            'reason': f'{inv_count} invoices over {(dates[-1] - dates[0]).days if len(dates) >= 2 else 0} days.',
            'invoice_count': inv_count,
        }

    # ── 2. Payment history (25%) ─────────────────────────────────────
    pay_txns = txns.filter(
        txn_type__in=['payment', 'bank_transaction'],
        direction='outflow',
        status__in=['completed', 'fully_matched'],
    )
    pay_count = pay_txns.count()

    if pay_count == 0:
        metrics['payment_history'] = Decimal("50")
        breakdown['payment_history'] = {
            'score': '50.00', 'reason': 'No payment history — neutral.',
            'total_payments': 0, 'on_time': 0, 'late': 0,
        }
    else:
        on_time = pay_txns.filter(
            Q(due_date__isnull=True) | Q(txn_date__lte=F('due_date'))
        ).count()
        late = pay_count - on_time
        ratio = on_time / pay_count
        raw = Decimal(str(ratio * 100))
        metrics['payment_history'] = _clamp(raw)
        breakdown['payment_history'] = {
            'score': str(metrics['payment_history']),
            'reason': f'{on_time}/{pay_count} payments on time ({ratio:.0%}).',
            'total_payments': pay_count, 'on_time': on_time, 'late': late,
        }

    # ── 3. Price stability (15%) ─────────────────────────────────────
    amounts = list(
        inv_txns.values_list('amount', flat=True)
    ) if inv_count > 0 else []

    if len(amounts) < 2:
        metrics['price_stability'] = Decimal("70")
        breakdown['price_stability'] = {
            'score': '70.00', 'reason': 'Not enough invoices to assess stability.',
        }
    else:
        float_amounts = [float(a) for a in amounts]
        mean_amt = statistics.mean(float_amounts)
        cv = statistics.stdev(float_amounts) / mean_amt if mean_amt > 0 else 0
        raw = max(0, 100 - cv * 100)
        metrics['price_stability'] = _clamp(Decimal(str(raw)))
        breakdown['price_stability'] = {
            'score': str(metrics['price_stability']),
            'reason': f'Coefficient of variation: {cv:.2f} across {len(amounts)} invoices.',
            'cv': round(cv, 4),
        }

    # ── 4. Document quality (15%) ────────────────────────────────────
    docs = Document.objects.filter(firm=firm).filter(
        Q(raw_data__vendor_name__icontains=vendor.name) |
        Q(raw_data__party_name__icontains=vendor.name)
    )
    total_docs = docs.count()
    if total_docs == 0:
        metrics['document_quality'] = Decimal("70")
        breakdown['document_quality'] = {
            'score': '70.00', 'reason': 'No linked documents found — neutral.',
        }
    else:
        failed = docs.filter(extraction_failed=True).count()
        success_rate = (total_docs - failed) / total_docs
        raw = Decimal(str(success_rate * 100))
        metrics['document_quality'] = _clamp(raw)
        breakdown['document_quality'] = {
            'score': str(metrics['document_quality']),
            'reason': f'{total_docs - failed}/{total_docs} documents extracted successfully.',
            'total_docs': total_docs, 'failed': failed,
        }

    # ── 5. Bank change frequency (10%) ───────────────────────────────
    bank_changes = 0
    if vendor.metadata and isinstance(vendor.metadata, dict):
        bank_changes = vendor.metadata.get('bank_detail_changes', 0)

    if bank_changes == 0:
        metrics['bank_change_frequency'] = _HUNDRED
        breakdown['bank_change_frequency'] = {
            'score': '100.00', 'reason': 'No bank detail changes recorded.',
        }
    else:
        raw = max(0, 100 - bank_changes * 25)
        metrics['bank_change_frequency'] = _clamp(Decimal(str(raw)))
        breakdown['bank_change_frequency'] = {
            'score': str(metrics['bank_change_frequency']),
            'reason': f'{bank_changes} bank detail change(s) detected — higher frequency lowers trust.',
            'changes': bank_changes,
        }

    # ── 6. Anomaly history (15%) ─────────────────────────────────────
    signals = RiskSignal.objects.filter(firm=firm, vendor=vendor)
    sig_count = signals.count()
    critical = signals.filter(severity__in=['critical', 'high']).count()

    if sig_count == 0:
        metrics['anomaly_history'] = _HUNDRED
        breakdown['anomaly_history'] = {
            'score': '100.00', 'reason': 'No risk signals associated with this vendor.',
        }
    else:
        penalty = min(100, sig_count * 8 + critical * 15)
        raw = 100 - penalty
        metrics['anomaly_history'] = _clamp(Decimal(str(raw)))
        breakdown['anomaly_history'] = {
            'score': str(metrics['anomaly_history']),
            'reason': f'{sig_count} risk signal(s), {critical} high/critical.',
            'total_signals': sig_count, 'critical': critical,
        }

    # ── Weighted composite ───────────────────────────────────────────
    overall = sum(
        metrics[k] * VENDOR_WEIGHTS[k] for k in VENDOR_WEIGHTS
    ).quantize(_Q, rounding=ROUND_HALF_UP)

    # Persist
    score_obj, _created = VendorScore.all_objects.update_or_create(
        firm=firm, vendor=vendor, is_deleted=False,
        defaults={
            'previous_score': None,
            'invoice_consistency': metrics['invoice_consistency'],
            'payment_history': metrics['payment_history'],
            'price_stability': metrics['price_stability'],
            'document_quality': metrics['document_quality'],
            'bank_change_frequency': metrics['bank_change_frequency'],
            'anomaly_history': metrics['anomaly_history'],
            'overall_score': overall,
            'breakdown': breakdown,
            'last_computed_at': timezone.now(),
        },
    )

    # Set previous_score on update (not on first creation)
    if not _created:
        VendorScore.all_objects.filter(pk=score_obj.pk).update(
            previous_score=score_obj.overall_score,
        )

    logger.info("VendorScore %s (%s): %s", vendor.name, firm.name, overall)
    return score_obj


# ═══════════════════════════════════════════════════════════════════════
# Customer Scoring
# ═══════════════════════════════════════════════════════════════════════

CUSTOMER_WEIGHTS = {
    'payment_history': Decimal("0.30"),
    'avg_payment_time_trend': Decimal("0.20"),
    'credit_exposure': Decimal("0.25"),
    'revenue_contribution': Decimal("0.25"),
}


def compute_customer_score(customer: Customer, as_of: date | None = None) -> CustomerScore:
    """Compute or update the CustomerScore for a single customer."""
    today = as_of or date.today()
    firm = customer.firm

    txns = Transaction.objects.filter(
        firm=firm, customer=customer,
    ).exclude(status='cancelled')

    breakdown: dict = {}
    metrics: dict[str, Decimal] = {}

    # ── 1. Payment history (30%) ─────────────────────────────────────
    inv_txns = txns.filter(txn_type='invoice', direction='inflow')
    matched = inv_txns.filter(status='fully_matched')
    matched_count = matched.count()
    total_inv = inv_txns.count()

    if total_inv == 0:
        metrics['payment_history'] = Decimal("50")
        breakdown['payment_history'] = {
            'score': '50.00', 'reason': 'No invoices to assess.',
            'total_invoices': 0,
        }
    else:
        # Check how many matched invoices were paid by due date
        on_time = 0
        late = 0
        for inv in matched.filter(due_date__isnull=False):
            payments = Transaction.objects.filter(
                firm=firm, customer=customer,
                txn_type='payment', direction='inflow',
                status__in=['completed', 'fully_matched'],
                txn_date__lte=inv.due_date,
            )
            if payments.exists():
                on_time += 1
            else:
                late += 1

        pending = total_inv - matched_count
        if matched_count > 0:
            ratio = on_time / matched_count
        else:
            ratio = 0.5

        raw = Decimal(str(ratio * 100))
        if pending > total_inv * 0.5:
            raw = raw * Decimal("0.8")

        metrics['payment_history'] = _clamp(raw)
        breakdown['payment_history'] = {
            'score': str(metrics['payment_history']),
            'reason': f'{on_time} on-time, {late} late, {pending} pending out of {total_inv} invoices.',
            'total_invoices': total_inv, 'on_time': on_time, 'late': late, 'pending': pending,
        }

    # ── 2. Average payment time trend (20%) ──────────────────────────
    six_months_ago = today - timedelta(days=180)
    recent_paid = matched.filter(txn_date__gte=six_months_ago, due_date__isnull=False)
    older_paid = matched.filter(txn_date__lt=six_months_ago, due_date__isnull=False)

    def _avg_days(qs):
        delays = []
        for t in qs:
            delays.append(abs((t.txn_date - t.due_date).days))
        return statistics.mean(delays) if delays else 30.0

    recent_avg = _avg_days(recent_paid)
    older_avg = _avg_days(older_paid)

    if older_avg > 0 and recent_paid.exists() and older_paid.exists():
        improvement = (older_avg - recent_avg) / older_avg
        raw = 50 + improvement * 50  # -1→0, 0→50, +1→100
        raw = max(0, min(100, raw))
    else:
        raw = 50

    metrics['avg_payment_time_trend'] = _clamp(Decimal(str(raw)))
    breakdown['avg_payment_time_trend'] = {
        'score': str(metrics['avg_payment_time_trend']),
        'reason': f'Recent avg: {recent_avg:.0f}d, older avg: {older_avg:.0f}d.',
        'recent_avg_days': round(recent_avg, 1),
        'older_avg_days': round(older_avg, 1),
    }

    # ── 3. Credit exposure (25%) ─────────────────────────────────────
    outstanding = txns.filter(
        direction='inflow',
        status__in=['pending', 'partially_matched'],
    ).aggregate(s=Sum('amount', default=_ZERO))['s']

    total_volume = txns.filter(direction='inflow').aggregate(
        s=Sum('amount', default=_ZERO),
    )['s']

    if total_volume > 0:
        exposure_ratio = float(outstanding / total_volume)
        raw = max(0, 100 - exposure_ratio * 150)
    else:
        raw = 50

    metrics['credit_exposure'] = _clamp(Decimal(str(raw)))
    breakdown['credit_exposure'] = {
        'score': str(metrics['credit_exposure']),
        'reason': f'₹{outstanding:,.0f} outstanding of ₹{total_volume:,.0f} total volume ({exposure_ratio * 100:.0f}% exposure).' if total_volume > 0 else 'No transaction volume.',
        'outstanding': str(outstanding),
        'total_volume': str(total_volume),
    }

    # ── 4. Revenue contribution (25%) ────────────────────────────────
    firm_total_revenue = Transaction.objects.filter(
        firm=firm, direction='inflow',
    ).exclude(status='cancelled').aggregate(
        s=Sum('amount', default=_ZERO),
    )['s']

    cust_revenue = txns.filter(direction='inflow').aggregate(
        s=Sum('amount', default=_ZERO),
    )['s']

    if firm_total_revenue > 0:
        share = float(cust_revenue / firm_total_revenue)
        raw = min(100, share * 200)  # 50% share → 100 score
    else:
        raw = 50

    metrics['revenue_contribution'] = _clamp(Decimal(str(raw)))
    breakdown['revenue_contribution'] = {
        'score': str(metrics['revenue_contribution']),
        'reason': f'₹{cust_revenue:,.0f} revenue ({share * 100:.1f}% of firm total).' if firm_total_revenue > 0 else 'No firm revenue data.',
        'customer_revenue': str(cust_revenue),
        'firm_total_revenue': str(firm_total_revenue),
    }

    # ── Weighted composite ───────────────────────────────────────────
    overall = sum(
        metrics[k] * CUSTOMER_WEIGHTS[k] for k in CUSTOMER_WEIGHTS
    ).quantize(_Q, rounding=ROUND_HALF_UP)

    score_obj, _created = CustomerScore.all_objects.update_or_create(
        firm=firm, customer=customer, is_deleted=False,
        defaults={
            'previous_score': None,
            'payment_history': metrics['payment_history'],
            'avg_payment_time_trend': metrics['avg_payment_time_trend'],
            'credit_exposure': metrics['credit_exposure'],
            'revenue_contribution': metrics['revenue_contribution'],
            'overall_score': overall,
            'breakdown': breakdown,
            'last_computed_at': timezone.now(),
        },
    )

    if not _created:
        CustomerScore.all_objects.filter(pk=score_obj.pk).update(
            previous_score=score_obj.overall_score,
        )

    logger.info("CustomerScore %s (%s): %s", customer.name, firm.name, overall)
    return score_obj


# ═══════════════════════════════════════════════════════════════════════
# Batch helpers (used by Celery tasks)
# ═══════════════════════════════════════════════════════════════════════

def score_all_vendors_for_firm(firm_id: int):
    from firms.models import Firm
    firm = Firm.objects.get(pk=firm_id)
    vendors = Vendor.objects.filter(firm=firm)
    results = []
    for v in vendors:
        try:
            s = compute_vendor_score(v)
            results.append({'vendor_id': v.id, 'score': str(s.overall_score)})
        except Exception:
            logger.exception("Failed scoring vendor %s", v.id)
    return results


def score_all_customers_for_firm(firm_id: int):
    from firms.models import Firm
    firm = Firm.objects.get(pk=firm_id)
    customers = Customer.objects.filter(firm=firm)
    results = []
    for c in customers:
        try:
            s = compute_customer_score(c)
            results.append({'customer_id': c.id, 'score': str(s.overall_score)})
        except Exception:
            logger.exception("Failed scoring customer %s", c.id)
    return results
