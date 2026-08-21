"""
Cash-flow forecasting engine — Weighted Moving Average model.

Builds a transparent, explainable 30/60/90-day cash position forecast
from a firm's Transaction ledger.  Every forecast number is traceable
back to specific line items and each risk explanation is generated from
the actual contributing transactions, never templates with placeholders.

Algorithm (three layers):
1. **Known obligations** — invoices/POs with due_dates in the forecast
   window that are not yet fully matched with payments.
2. **Historical payment behaviour** — weighted moving average of how
   quickly receivables are actually collected and payables are actually
   paid (the "DSO/DPO layer").  Recent behaviour is weighted more
   heavily (exponential decay, α=0.7).
3. **Pressure detection** — identifies the calendar day with the lowest
   projected balance and constructs a plain-English explanation citing
   the specific receivable delays and vendor obligations that cause it.
"""
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone

from .models import (
    FinancialSnapshot,
    RiskSignal,
    Transaction,
)

logger = logging.getLogger(__name__)

_ZERO = Decimal("0.00")
_EWM_ALPHA = Decimal("0.70")   # exponential weight for recent periods


# ---------------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------------

@dataclass
class ForecastDay:
    day: date
    projected_inflows: Decimal = _ZERO
    projected_outflows: Decimal = _ZERO
    net_position: Decimal = _ZERO
    cumulative_position: Decimal = _ZERO
    inflow_items: list = field(default_factory=list)
    outflow_items: list = field(default_factory=list)


@dataclass
class ForecastResult:
    firm_id: int
    as_of: date
    current_balance: Decimal
    position_30d: Decimal
    position_60d: Decimal
    position_90d: Decimal
    daily_forecast: list[ForecastDay]
    risk_explanation: str
    pressure_day: int | None          # days from today
    pressure_amount: Decimal | None
    top_delayed_receivables: list[dict]
    top_upcoming_payables: list[dict]
    avg_collection_days: Decimal
    avg_payment_days: Decimal
    health_score: Decimal


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class CashFlowForecaster:

    def forecast(self, firm_id: int, as_of: date | None = None) -> ForecastResult:
        from firms.models import Firm
        firm = Firm.objects.get(pk=firm_id)
        today = as_of or date.today()

        # ── 1. Compute current cash position from bank transactions ──
        current_balance = self._current_balance(firm, today)

        # ── 2. Compute historical DSO / DPO via weighted moving avg ──
        avg_collection = self._weighted_avg_days(firm, today, 'inflow')
        avg_payment = self._weighted_avg_days(firm, today, 'outflow')

        # ── 3. Build 90-day daily projection ─────────────────────────
        daily = self._build_daily_forecast(
            firm, today, current_balance, avg_collection, avg_payment,
        )

        # ── 4. Read off 30/60/90 cumulative positions ────────────────
        pos_30 = daily[29].cumulative_position if len(daily) >= 30 else daily[-1].cumulative_position
        pos_60 = daily[59].cumulative_position if len(daily) >= 60 else daily[-1].cumulative_position
        pos_90 = daily[89].cumulative_position if len(daily) >= 90 else daily[-1].cumulative_position

        # ── 5. Find pressure point (lowest cumulative position) ──────
        min_day = min(daily, key=lambda d: d.cumulative_position)
        pressure_day = None
        pressure_amount = None
        if min_day.cumulative_position < _ZERO:
            pressure_day = (min_day.day - today).days
            pressure_amount = min_day.cumulative_position

        # ── 6. Build top-N driver lists ──────────────────────────────
        top_delayed = self._top_delayed_receivables(firm, today)
        top_payables = self._top_upcoming_payables(firm, today)

        # ── 7. Generate explanation from ACTUAL line items ───────────
        explanation = self._generate_explanation(
            today, current_balance, pos_30, pos_60, pos_90,
            pressure_day, pressure_amount,
            top_delayed, top_payables,
            avg_collection, avg_payment,
        )

        # ── 8. Health score (0-100) ──────────────────────────────────
        health = self._compute_health_score(
            current_balance, pos_30, pos_60, pos_90,
            top_delayed, top_payables,
        )

        return ForecastResult(
            firm_id=firm_id,
            as_of=today,
            current_balance=current_balance,
            position_30d=pos_30,
            position_60d=pos_60,
            position_90d=pos_90,
            daily_forecast=daily,
            risk_explanation=explanation,
            pressure_day=pressure_day,
            pressure_amount=pressure_amount,
            top_delayed_receivables=top_delayed,
            top_upcoming_payables=top_payables,
            avg_collection_days=avg_collection,
            avg_payment_days=avg_payment,
            health_score=health,
        )

    # ── Current balance ──────────────────────────────────────────────

    def _current_balance(self, firm, today: date) -> Decimal:
        """Net of all completed inflows minus outflows up to today."""
        agg = Transaction.objects.filter(
            firm=firm,
            txn_date__lte=today,
            status__in=['completed', 'fully_matched'],
        ).aggregate(
            inflows=Sum('amount', filter=Q(direction='inflow'), default=_ZERO),
            outflows=Sum('amount', filter=Q(direction='outflow'), default=_ZERO),
        )
        return (agg['inflows'] or _ZERO) - (agg['outflows'] or _ZERO)

    # ── Weighted average collection / payment days ───────────────────

    def _weighted_avg_days(
        self, firm, today: date, direction: str,
    ) -> Decimal:
        """Exponentially weighted moving average of days-to-settle.

        Looks at the last 6 months of matched transactions: for each,
        the settlement delay = (payment_date - invoice_date).  Recent
        months carry weight α^0, α^1, α^2, … (α = 0.70).
        """
        six_months_ago = today - timedelta(days=180)
        matched = Transaction.objects.filter(
            firm=firm,
            direction=direction,
            status='fully_matched',
            txn_date__gte=six_months_ago,
            txn_date__lte=today,
        ).values_list('txn_date', 'due_date', 'amount')

        if not matched:
            return Decimal("30")  # default DSO/DPO

        # Group by month, compute average days per month
        monthly: dict[str, list[int]] = defaultdict(list)
        for txn_date, due_date, _amount in matched:
            if due_date and txn_date:
                days = abs((txn_date - due_date).days)
            else:
                days = 30
            month_key = txn_date.strftime('%Y-%m')
            monthly[month_key].append(days)

        if not monthly:
            return Decimal("30")

        sorted_months = sorted(monthly.keys(), reverse=True)
        weighted_sum = _ZERO
        weight_sum = _ZERO
        for i, month in enumerate(sorted_months):
            month_avg = Decimal(str(sum(monthly[month]))) / Decimal(str(len(monthly[month])))
            weight = _EWM_ALPHA ** i
            weighted_sum += month_avg * weight
            weight_sum += weight

        return (weighted_sum / weight_sum).quantize(Decimal("0.1")) if weight_sum else Decimal("30")

    # ── Daily projection ─────────────────────────────────────────────

    def _build_daily_forecast(
        self, firm, today: date, starting_balance: Decimal,
        avg_collection: Decimal, avg_payment: Decimal,
    ) -> list[ForecastDay]:
        """Build 90 daily ForecastDay entries.

        Layer 1: Known obligations (invoices with due_dates in window).
        Layer 2: Probabilistic inflows — overdue receivables weighted by
                 how far past their expected collection date they are.
        """
        end = today + timedelta(days=90)

        # Known future outflows (pending payables with due dates)
        future_outflows = list(
            Transaction.objects.filter(
                firm=firm,
                direction='outflow',
                status__in=['pending', 'completed', 'partially_matched'],
                due_date__gt=today,
                due_date__lte=end,
            ).values('id', 'reference_number', 'amount', 'due_date', 'description',
                     'vendor__name')
        )

        # Known future inflows (receivables with due dates)
        future_inflows = list(
            Transaction.objects.filter(
                firm=firm,
                direction='inflow',
                status__in=['pending', 'completed', 'partially_matched'],
                due_date__gt=today,
                due_date__lte=end,
            ).values('id', 'reference_number', 'amount', 'due_date', 'description',
                     'customer__name')
        )

        # Overdue receivables (past due, not yet collected)
        overdue_receivables = list(
            Transaction.objects.filter(
                firm=firm,
                direction='inflow',
                status__in=['pending', 'partially_matched'],
                due_date__lte=today,
            ).values('id', 'reference_number', 'amount', 'due_date', 'txn_date',
                     'description', 'customer__name')
        )

        # Build day-indexed maps
        outflow_by_day: dict[date, list[dict]] = defaultdict(list)
        for o in future_outflows:
            outflow_by_day[o['due_date']].append(o)

        inflow_by_day: dict[date, list[dict]] = defaultdict(list)
        for i in future_inflows:
            inflow_by_day[i['due_date']].append(i)

        # Spread overdue receivables across near-term days based on
        # historical collection delay.  If avg collection is 45 days and
        # this receivable is 30 days overdue, expect it in ~15 more days.
        for rec in overdue_receivables:
            due = rec['due_date']
            if due is None:
                due = rec['txn_date']
            days_overdue = (today - due).days
            est_remaining = max(1, int(avg_collection) - days_overdue)
            expected_day = today + timedelta(days=min(est_remaining, 90))
            if expected_day > end:
                expected_day = end
            rec['_estimated'] = True
            inflow_by_day[expected_day].append(rec)

        # Assemble daily entries
        days: list[ForecastDay] = []
        cumulative = starting_balance

        for offset in range(1, 91):
            d = today + timedelta(days=offset)
            fd = ForecastDay(day=d)

            for item in inflow_by_day.get(d, []):
                amt = Decimal(str(item['amount']))
                fd.projected_inflows += amt
                fd.inflow_items.append({
                    'id': item['id'],
                    'ref': item.get('reference_number', ''),
                    'amount': str(amt),
                    'party': item.get('customer__name', ''),
                    'estimated': item.get('_estimated', False),
                })

            for item in outflow_by_day.get(d, []):
                amt = Decimal(str(item['amount']))
                fd.projected_outflows += amt
                fd.outflow_items.append({
                    'id': item['id'],
                    'ref': item.get('reference_number', ''),
                    'amount': str(amt),
                    'party': item.get('vendor__name', ''),
                })

            fd.net_position = fd.projected_inflows - fd.projected_outflows
            cumulative += fd.net_position
            fd.cumulative_position = cumulative
            days.append(fd)

        return days

    # ── Top drivers ──────────────────────────────────────────────────

    def _top_delayed_receivables(self, firm, today: date, limit: int = 5) -> list[dict]:
        qs = Transaction.objects.filter(
            firm=firm,
            direction='inflow',
            txn_type='invoice',
            status__in=['pending', 'partially_matched'],
            due_date__lt=today,
        ).select_related('customer').order_by('-amount')[:limit]

        return [{
            'id': t.id,
            'reference': t.reference_number,
            'amount': str(t.amount),
            'currency': t.currency,
            'due_date': str(t.due_date),
            'days_overdue': (today - t.due_date).days if t.due_date else 0,
            'customer': t.customer.name if t.customer else '',
        } for t in qs]

    def _top_upcoming_payables(self, firm, today: date, limit: int = 5) -> list[dict]:
        window_end = today + timedelta(days=90)
        qs = Transaction.objects.filter(
            firm=firm,
            direction='outflow',
            status__in=['pending', 'completed', 'partially_matched'],
            due_date__gt=today,
            due_date__lte=window_end,
        ).select_related('vendor').order_by('-amount')[:limit]

        return [{
            'id': t.id,
            'reference': t.reference_number,
            'amount': str(t.amount),
            'currency': t.currency,
            'due_date': str(t.due_date),
            'days_until_due': (t.due_date - today).days if t.due_date else 0,
            'vendor': t.vendor.name if t.vendor else '',
        } for t in qs]

    # ── Explanation generator (from ACTUAL line items) ────────────────

    def _generate_explanation(
        self,
        today: date,
        current: Decimal,
        pos_30: Decimal,
        pos_60: Decimal,
        pos_90: Decimal,
        pressure_day: int | None,
        pressure_amount: Decimal | None,
        delayed: list[dict],
        payables: list[dict],
        avg_collection: Decimal,
        avg_payment: Decimal,
    ) -> str:
        parts: list[str] = []

        # Current position
        parts.append(f"Current estimated cash position: {_fmt(current)}.")

        # 30/60/90 outlook
        trajectory = []
        for label, val in [("30-day", pos_30), ("60-day", pos_60), ("90-day", pos_90)]:
            trajectory.append(f"{label}: {_fmt(val)}")
        parts.append("Projected positions — " + ", ".join(trajectory) + ".")

        # Pressure point
        if pressure_day is not None and pressure_amount is not None:
            parts.append(
                f"Potential cash-flow pressure in {pressure_day} days "
                f"(projected balance: {_fmt(pressure_amount)})."
            )

            # Cite specific drivers
            drivers: list[str] = []

            if delayed:
                total_delayed = sum(Decimal(d['amount']) for d in delayed)
                top_names = [
                    f"{d['customer'] or 'Unknown'} ({_fmt(Decimal(d['amount']))}, "
                    f"{d['days_overdue']}d overdue)"
                    for d in delayed[:3]
                ]
                drivers.append(
                    f"{_fmt(total_delayed)} in delayed receivables "
                    f"(top: {'; '.join(top_names)})"
                )

            if payables:
                total_payable = sum(Decimal(p['amount']) for p in payables)
                top_vendors = [
                    f"{p['vendor'] or 'Unknown'} ({_fmt(Decimal(p['amount']))}, "
                    f"due in {p['days_until_due']}d)"
                    for p in payables[:3]
                ]
                drivers.append(
                    f"{_fmt(total_payable)} in upcoming vendor payments "
                    f"(top: {'; '.join(top_vendors)})"
                )

            if drivers:
                parts.append("Driven by: " + " and ".join(drivers) + ".")
        else:
            parts.append("No cash-flow pressure detected in the 90-day window.")

        # Collection/payment behaviour
        parts.append(
            f"Average collection period: {avg_collection} days. "
            f"Average payment period: {avg_payment} days."
        )

        return " ".join(parts)

    # ── Health score ─────────────────────────────────────────────────

    def _compute_health_score(
        self, current: Decimal, pos_30: Decimal, pos_60: Decimal,
        pos_90: Decimal, delayed: list, payables: list,
    ) -> Decimal:
        score = Decimal("100")

        # Deduct for negative positions
        if pos_30 < 0:
            score -= Decimal("20")
        if pos_60 < 0:
            score -= Decimal("15")
        if pos_90 < 0:
            score -= Decimal("10")
        if current < 0:
            score -= Decimal("25")

        # Deduct for overdue receivables
        if delayed:
            total_overdue = sum(Decimal(d['amount']) for d in delayed)
            if current > 0 and total_overdue > current * Decimal("0.5"):
                score -= Decimal("15")
            elif total_overdue > 0:
                score -= Decimal("5")

        return max(score, _ZERO).quantize(Decimal("0.01"))

    # ── Persist as FinancialSnapshot ─────────────────────────────────

    def save_snapshot(self, firm_id: int, result: ForecastResult):
        from firms.models import Firm
        firm = Firm.objects.get(pk=firm_id)

        # Compute totals for snapshot fields
        overdue_recv = sum(
            Decimal(d['amount']) for d in result.top_delayed_receivables
        )
        upcoming_pay = sum(
            Decimal(p['amount']) for p in result.top_upcoming_payables
        )

        total_receivables = Transaction.objects.filter(
            firm=firm, direction='inflow',
            status__in=['pending', 'partially_matched'],
        ).aggregate(s=Sum('amount', default=_ZERO))['s']

        total_payables = Transaction.objects.filter(
            firm=firm, direction='outflow',
            status__in=['pending', 'completed', 'partially_matched'],
        ).aggregate(s=Sum('amount', default=_ZERO))['s']

        open_risks = RiskSignal.objects.filter(
            firm=firm, status='open',
        ).count()

        forecast_payload = {
            'as_of': str(result.as_of),
            'current_balance': str(result.current_balance),
            'position_30d': str(result.position_30d),
            'position_60d': str(result.position_60d),
            'position_90d': str(result.position_90d),
            'pressure_day': result.pressure_day,
            'pressure_amount': str(result.pressure_amount) if result.pressure_amount else None,
            'risk_explanation': result.risk_explanation,
            'avg_collection_days': str(result.avg_collection_days),
            'avg_payment_days': str(result.avg_payment_days),
            'top_delayed_receivables': result.top_delayed_receivables,
            'top_upcoming_payables': result.top_upcoming_payables,
        }

        breakdown = {
            'overdue_receivables_detail': result.top_delayed_receivables,
            'upcoming_payables_detail': result.top_upcoming_payables,
            'daily_positions': [
                {
                    'day': str(d.day),
                    'inflows': str(d.projected_inflows),
                    'outflows': str(d.projected_outflows),
                    'cumulative': str(d.cumulative_position),
                }
                for d in result.daily_forecast
            ],
        }

        snapshot, _created = FinancialSnapshot.all_objects.update_or_create(
            firm=firm,
            snapshot_type=FinancialSnapshot.SnapshotType.DAILY,
            snapshot_date=result.as_of,
            is_deleted=False,
            defaults={
                'total_receivables': total_receivables,
                'total_payables': total_payables,
                'net_cash_flow': result.position_30d - result.current_balance,
                'overdue_receivables': overdue_recv,
                'overdue_payables': _ZERO,
                'open_risk_signals': open_risks,
                'health_score': result.health_score,
                'cashflow_forecast': forecast_payload,
                'breakdown': breakdown,
            },
        )
        return snapshot


def _fmt(amount: Decimal) -> str:
    """Format an amount in Indian ₹ lakhs notation for readability."""
    abs_val = abs(amount)
    sign = "-" if amount < 0 else ""
    if abs_val >= 10_000_000:
        return f"{sign}₹{abs_val / Decimal('10000000'):.2f}Cr"
    if abs_val >= 100_000:
        return f"{sign}₹{abs_val / Decimal('100000'):.1f}L"
    if abs_val >= 1000:
        return f"{sign}₹{abs_val / Decimal('1000'):.1f}K"
    return f"{sign}₹{abs_val:.0f}"
