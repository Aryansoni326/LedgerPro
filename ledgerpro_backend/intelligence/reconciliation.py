"""
ReconciliationEngine — three-pass matching algorithm for financial
document reconciliation.

Pass 1 (Exact): amount + date + vendor/customer match → confidence 1.0
Pass 2 (Fuzzy): amount within tolerance + date within window + same
                vendor/customer → confidence 0.65–0.95
Pass 3 (Diagnosis): classify unmatched/partial pairs by likely cause

All matches are recorded as ``ReconciliationLink`` rows; mismatches
produce ``ReconciliationException`` rows queued for human review.
"""
import logging
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from .fx import annotate_transaction_fx, snapshot_settlement_fx
from .models import (
    ReconciliationException,
    ReconciliationLink,
    ReconciliationRun,
    RiskSignal,
    Transaction,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration (overridable per-run via kwargs)
# ---------------------------------------------------------------------------

@dataclass
class ReconConfig:
    # Fuzzy amount tolerance: ratio of the larger amount (e.g. 0.03 = 3%)
    amount_tolerance_pct: Decimal = Decimal("0.03")
    # Absolute amount tolerance floor (catches tiny amounts where % is noisy)
    amount_tolerance_abs: Decimal = Decimal("5.00")
    # Date window for fuzzy matching (calendar days)
    date_window_days: int = 7
    # Bank-charge typical threshold (INR)
    bank_charge_threshold: Decimal = Decimal("500.00")
    # TDS standard deduction rates
    tds_rates: tuple[Decimal, ...] = (
        Decimal("0.01"), Decimal("0.02"), Decimal("0.05"),
        Decimal("0.10"), Decimal("0.20"),
    )
    # Discount typical cap (% of invoice amount)
    discount_cap_pct: Decimal = Decimal("0.10")

    def to_dict(self) -> dict:
        return {
            'amount_tolerance_pct': str(self.amount_tolerance_pct),
            'amount_tolerance_abs': str(self.amount_tolerance_abs),
            'date_window_days': self.date_window_days,
            'bank_charge_threshold': str(self.bank_charge_threshold),
        }


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------

@dataclass
class _MatchCandidate:
    txn: Transaction
    score: Decimal = Decimal("0")
    method: str = "rule_based"


@dataclass
class _MatchResult:
    txn_a: Transaction
    txn_b: Transaction
    confidence: Decimal
    method: str
    match_group: uuid.UUID = field(default_factory=uuid.uuid4)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class ReconciliationEngine:
    """Stateless matching engine.  Entry point: ``match(firm_id, **kwargs)``."""

    def __init__(self, config: ReconConfig | None = None):
        self.cfg = config or ReconConfig()

    # ── Public entry point ────────────────────────────────────────────

    def match(self, firm_id: int) -> ReconciliationRun:
        """Run the full reconciliation pipeline for a firm.

        Returns the ``ReconciliationRun`` audit record.
        """
        from firms.models import Firm
        firm = Firm.objects.get(pk=firm_id)

        run = ReconciliationRun.objects.create(
            firm=firm, status=ReconciliationRun.RunStatus.RUNNING,
            config=self.cfg.to_dict(),
        )

        try:
            stats = self._execute(firm, run)
            run.status = ReconciliationRun.RunStatus.COMPLETED
            run.completed_at = timezone.now()
            run.total_transactions = stats['total']
            run.exact_matches = stats['exact']
            run.fuzzy_matches = stats['fuzzy']
            run.exceptions_created = stats['exceptions']
            run.unmatched = stats['unmatched']
            run.save()
        except Exception as exc:
            logger.exception("Reconciliation failed for firm %s", firm_id)
            run.status = ReconciliationRun.RunStatus.FAILED
            run.completed_at = timezone.now()
            run.error_message = str(exc)[:2000]
            run.save()
            raise

        return run

    # ── Core algorithm ────────────────────────────────────────────────

    def _execute(self, firm, run: ReconciliationRun) -> dict:
        # Load unmatched transactions grouped by type
        base_qs = Transaction.objects.filter(
            firm=firm,
            status__in=[
                Transaction.Status.PENDING,
                Transaction.Status.COMPLETED,
                Transaction.Status.PARTIALLY_MATCHED,
            ],
        ).select_related('vendor', 'customer')

        invoices = list(base_qs.filter(txn_type=Transaction.TxnType.INVOICE))
        payments = list(base_qs.filter(txn_type=Transaction.TxnType.PAYMENT))
        purchase_orders = list(base_qs.filter(txn_type=Transaction.TxnType.PURCHASE_ORDER))
        bank_txns = list(base_qs.filter(txn_type=Transaction.TxnType.BANK_TRANSACTION))

        total = len(invoices) + len(payments) + len(purchase_orders) + len(bank_txns)

        exact_matches: list[_MatchResult] = []
        fuzzy_matches: list[_MatchResult] = []
        matched_ids: set[int] = set()

        # ── Pass 1 & 2: Invoice ↔ Payment ─────────────────────────
        self._match_pairs(
            invoices, payments, matched_ids,
            exact_matches, fuzzy_matches,
        )

        # ── Pass 1 & 2: Invoice ↔ Purchase Order ──────────────────
        self._match_pairs(
            invoices, purchase_orders, matched_ids,
            exact_matches, fuzzy_matches,
        )

        # ── Pass 1 & 2: Payment ↔ Bank Transaction ────────────────
        self._match_pairs(
            payments, bank_txns, matched_ids,
            exact_matches, fuzzy_matches,
        )

        # ── Pass 1 & 2: Invoice ↔ Bank Transaction (direct pay) ──
        self._match_pairs(
            invoices, bank_txns, matched_ids,
            exact_matches, fuzzy_matches,
        )

        # ── Persist matches ───────────────────────────────────────
        all_matches = exact_matches + fuzzy_matches
        self._persist_matches(firm, all_matches)

        # ── Pass 3: Diagnose unmatched ────────────────────────────
        all_txns = invoices + payments + purchase_orders + bank_txns
        unmatched_txns = [t for t in all_txns if t.id not in matched_ids]

        # Also diagnose fuzzy matches (they may have mismatches to flag)
        exceptions = self._diagnose_fuzzy(firm, fuzzy_matches)
        exceptions += self._diagnose_unmatched(firm, unmatched_txns, all_txns, matched_ids)

        self._persist_exceptions(firm, exceptions)

        # ── Create risk signals for significant exceptions ────────
        self._create_risk_signals(firm, exceptions)

        return {
            'total': total,
            'exact': len(exact_matches),
            'fuzzy': len(fuzzy_matches),
            'exceptions': len(exceptions),
            'unmatched': len(unmatched_txns),
        }

    # ── Pass 1+2: Pair matching ──────────────────────────────────────

    def _match_pairs(
        self,
        group_a: list[Transaction],
        group_b: list[Transaction],
        matched_ids: set[int],
        exact_out: list[_MatchResult],
        fuzzy_out: list[_MatchResult],
    ):
        """Try to match each txn in group_a with a txn in group_b."""

        # Build lookup for group_b by (vendor_id, amount) for fast exact
        available_b = [t for t in group_b if t.id not in matched_ids]

        for txn_a in group_a:
            if txn_a.id in matched_ids:
                continue

            best: _MatchCandidate | None = None

            for txn_b in available_b:
                if txn_b.id in matched_ids:
                    continue

                score = self._score_pair(txn_a, txn_b)
                if score <= 0:
                    continue

                if best is None or score > best.score:
                    best = _MatchCandidate(txn=txn_b, score=score)

            if best is None:
                continue

            mg = uuid.uuid4()
            result = _MatchResult(
                txn_a=txn_a,
                txn_b=best.txn,
                confidence=best.score,
                method="rule_based",
                match_group=mg,
            )

            if best.score >= Decimal("0.98"):
                exact_out.append(result)
            else:
                fuzzy_out.append(result)

            matched_ids.add(txn_a.id)
            matched_ids.add(best.txn.id)

    def _score_pair(self, a: Transaction, b: Transaction) -> Decimal:
        """Score a candidate pair from 0 (no match) to 1 (perfect).

        Scoring dimensions:
        - Amount (50% weight): exact=0.50, within tolerance=0.25–0.45
        - Date (25% weight):   same day=0.25, within window=0.10–0.20
        - Counterparty (25%):  same vendor/customer=0.25, either null=0.10
        """
        score = Decimal("0")

        # ── Amount ────────────────────────────────────────────────
        amt_a = self._comparison_amount(a)
        amt_b = self._comparison_amount(b)
        if amt_a == 0 and amt_b == 0:
            return Decimal("0")

        max_amt = max(amt_a, amt_b)
        diff = abs(amt_a - amt_b)
        tol = max(
            max_amt * self.cfg.amount_tolerance_pct,
            self.cfg.amount_tolerance_abs,
        )

        if diff == 0:
            score += Decimal("0.50")
        elif diff <= tol:
            ratio = Decimal("1") - (diff / tol)
            score += Decimal("0.25") + ratio * Decimal("0.20")
        else:
            return Decimal("0")

        # ── Date ──────────────────────────────────────────────────
        day_diff = abs((a.txn_date - b.txn_date).days)
        if day_diff == 0:
            score += Decimal("0.25")
        elif day_diff <= self.cfg.date_window_days:
            ratio = Decimal("1") - Decimal(str(day_diff)) / Decimal(str(self.cfg.date_window_days))
            score += Decimal("0.10") + ratio * Decimal("0.10")
        else:
            return Decimal("0")

        # ── Counterparty ──────────────────────────────────────────
        vendor_match = (
            a.vendor_id is not None
            and a.vendor_id == b.vendor_id
        )
        customer_match = (
            a.customer_id is not None
            and a.customer_id == b.customer_id
        )
        if vendor_match or customer_match:
            score += Decimal("0.25")
        elif a.vendor_id is None or b.vendor_id is None:
            # One side has no counterparty — give partial credit
            score += Decimal("0.10")
        else:
            # Both have different counterparties — not a match
            return Decimal("0")

        return score

    # ── Pass 3a: Diagnose fuzzy matches ──────────────────────────────

    def _diagnose_fuzzy(
        self, firm, fuzzy_matches: list[_MatchResult],
    ) -> list[dict]:
        """For each fuzzy match, classify the likely mismatch cause."""
        exceptions = []
        for m in fuzzy_matches:
            diag = self._classify_difference(m.txn_a, m.txn_b)
            exceptions.append({
                'firm': firm,
                'transaction': m.txn_a,
                'candidate_transaction': m.txn_b,
                'match_group': m.match_group,
                **diag,
            })
        return exceptions

    # ── Pass 3b: Diagnose fully unmatched ────────────────────────────

    def _diagnose_unmatched(
        self, firm, unmatched: list[Transaction],
        all_txns: list[Transaction], matched_ids: set[int],
    ) -> list[dict]:
        """For unmatched transactions, find the nearest candidate and explain why it didn't match."""
        exceptions = []
        for txn in unmatched:
            # Find the closest transaction of a complementary type
            best_candidate = None
            best_score = Decimal("-1")

            complementary = self._complementary_types(txn.txn_type)
            candidates = [
                t for t in all_txns
                if t.id != txn.id
                and t.txn_type in complementary
            ]

            for c in candidates:
                s = self._lenient_score(txn, c)
                if s > best_score:
                    best_score = s
                    best_candidate = c

            mg = uuid.uuid4()
            if best_candidate and best_score > Decimal("0"):
                diag = self._classify_difference(txn, best_candidate)
                exceptions.append({
                    'firm': firm,
                    'transaction': txn,
                    'candidate_transaction': best_candidate,
                    'match_group': mg,
                    **diag,
                })
            else:
                exceptions.append({
                    'firm': firm,
                    'transaction': txn,
                    'candidate_transaction': None,
                    'match_group': mg,
                    'mismatch_cause': ReconciliationException.MismatchCause.MISSING_COUNTERPART,
                    'confidence': Decimal("0.9000"),
                    'reason': (
                        f"No matching {'/'.join(complementary)} found for "
                        f"{txn.txn_type} #{txn.reference_number or txn.id} "
                        f"of {txn.currency} {txn.amount} on {txn.txn_date}."
                    ),
                    'expected_amount': txn.amount,
                    'actual_amount': None,
                    'difference': None,
                })
        return exceptions

    def _complementary_types(self, txn_type: str) -> list[str]:
        T = Transaction.TxnType
        return {
            T.INVOICE: [T.PAYMENT, T.BANK_TRANSACTION, T.PURCHASE_ORDER],
            T.PAYMENT: [T.INVOICE, T.BANK_TRANSACTION],
            T.PURCHASE_ORDER: [T.INVOICE],
            T.BANK_TRANSACTION: [T.PAYMENT, T.INVOICE],
            T.CREDIT_NOTE: [T.INVOICE],
            T.DEBIT_NOTE: [T.INVOICE],
        }.get(txn_type, [])

    def _lenient_score(self, a: Transaction, b: Transaction) -> Decimal:
        """Score without the hard cutoffs — used only for finding the
        *closest* candidate for diagnostic purposes."""
        score = Decimal("0")
        amt_a, amt_b = self._comparison_amount(a), self._comparison_amount(b)
        max_amt = max(amt_a, amt_b) or Decimal("1")
        diff = abs(amt_a - amt_b)
        score += max(Decimal("0"), Decimal("0.50") - (diff / max_amt))

        day_diff = abs((a.txn_date - b.txn_date).days)
        score += max(Decimal("0"), Decimal("0.25") - Decimal(str(day_diff)) / Decimal("30"))

        if a.vendor_id and a.vendor_id == b.vendor_id:
            score += Decimal("0.25")
        elif a.customer_id and a.customer_id == b.customer_id:
            score += Decimal("0.25")

        return score

    # ── Mismatch classification ──────────────────────────────────────

    def _classify_difference(self, txn_a: Transaction, txn_b: Transaction) -> dict:
        """Diagnose the likely cause of a mismatch between two transactions."""
        amt_a = self._comparison_amount(txn_a)
        amt_b = self._comparison_amount(txn_b)
        diff = amt_a - amt_b  # positive = txn_a is larger
        abs_diff = abs(diff)

        result = {
            'expected_amount': amt_a,
            'actual_amount': amt_b,
            'difference': diff,
        }

        # Exact amount but different vendors
        if abs_diff == 0 and txn_a.vendor_id != txn_b.vendor_id:
            if txn_a.vendor_id and txn_b.vendor_id:
                result.update({
                    'mismatch_cause': ReconciliationException.MismatchCause.VENDOR_MISMATCH,
                    'confidence': Decimal("0.8500"),
                    'reason': (
                        f"Amount matches ({txn_a.currency} {amt_a}) but vendor/party "
                        f"differs between {txn_a.txn_type} and {txn_b.txn_type}."
                    ),
                })
                return result

        # Date-only mismatch (amounts match)
        if abs_diff == 0:
            day_diff = abs((txn_a.txn_date - txn_b.txn_date).days)
            if day_diff > 0:
                result.update({
                    'mismatch_cause': ReconciliationException.MismatchCause.DATE_MISMATCH,
                    'confidence': Decimal("0.9000"),
                    'reason': (
                        f"Amounts match ({txn_a.currency} {amt_a}) but dates differ by "
                        f"{day_diff} day(s): {txn_a.txn_date} vs {txn_b.txn_date}."
                    ),
                })
                return result

        # Currency mismatch
        if txn_a.currency != txn_b.currency:
            result.update({
                'mismatch_cause': ReconciliationException.MismatchCause.CURRENCY_MISMATCH,
                'confidence': Decimal("0.9500"),
                'reason': (
                    f"Currency mismatch: {txn_a.currency} {txn_a.amount} vs "
                    f"{txn_b.currency} {txn_b.amount}."
                ),
            })
            return result

        # Bank charges: small deduction on the payment/bank side
        if Decimal("0") < abs_diff <= self.cfg.bank_charge_threshold:
            result.update({
                'mismatch_cause': ReconciliationException.MismatchCause.BANK_CHARGES,
                'confidence': Decimal("0.8000"),
                'reason': (
                    f"Difference of {txn_a.currency} {abs_diff} likely bank charges/fees. "
                    f"Invoice: {amt_a}, Payment: {amt_b}."
                ),
            })
            return result

        # TDS / tax deduction: diff matches a standard TDS rate applied to the larger amount
        for rate in self.cfg.tds_rates:
            expected_tds = (amt_a * rate).quantize(Decimal("0.01"))
            if abs(abs_diff - expected_tds) <= Decimal("1.00"):
                pct = rate * 100
                result.update({
                    'mismatch_cause': ReconciliationException.MismatchCause.TAX_DEDUCTION,
                    'confidence': Decimal("0.8500"),
                    'reason': (
                        f"Difference of {txn_a.currency} {abs_diff} matches TDS @ {pct}% "
                        f"on {amt_a} (expected deduction: {expected_tds})."
                    ),
                })
                return result

        # Discount: payment is less than invoice by ≤ discount cap
        if diff > 0 and amt_a > 0:
            discount_pct = diff / amt_a
            if discount_pct <= self.cfg.discount_cap_pct:
                result.update({
                    'mismatch_cause': ReconciliationException.MismatchCause.DISCOUNT,
                    'confidence': Decimal("0.7500"),
                    'reason': (
                        f"Payment is {discount_pct * 100:.1f}% less than invoice "
                        f"({txn_a.currency} {abs_diff} discount). "
                        f"Invoice: {amt_a}, Payment: {amt_b}."
                    ),
                })
                return result

        # Partial payment: payment < 50% of invoice
        if diff > 0 and amt_b < amt_a * Decimal("0.95"):
            result.update({
                'mismatch_cause': ReconciliationException.MismatchCause.PARTIAL_PAYMENT,
                'confidence': Decimal("0.8000"),
                'reason': (
                    f"Payment of {txn_b.currency} {amt_b} is significantly less than "
                    f"invoice of {txn_a.currency} {amt_a} "
                    f"(shortfall: {abs_diff}, {(diff / amt_a * 100):.1f}%)."
                ),
            })
            return result

        # Incorrect payment (catch-all for amount mismatches)
        result.update({
            'mismatch_cause': ReconciliationException.MismatchCause.INCORRECT_PAYMENT,
            'confidence': Decimal("0.6500"),
            'reason': (
                f"Amount mismatch of {txn_a.currency} {abs_diff} between "
                f"{txn_a.txn_type} ({amt_a}) and {txn_b.txn_type} ({amt_b}). "
                f"No standard deduction pattern detected."
            ),
        })
        return result

    def _comparison_amount(self, txn: Transaction) -> Decimal:
        """Use base-currency amounts when available so cross-currency pairs can reconcile."""
        if txn.base_currency_amount is not None:
            return abs(Decimal(str(txn.base_currency_amount)))
        if txn.exchange_rate is None:
            annotate_transaction_fx(txn)
            if txn.base_currency_amount is not None:
                return abs(Decimal(str(txn.base_currency_amount)))
        return abs(Decimal(str(txn.amount)))

    # ── Persistence ──────────────────────────────────────────────────

    def _persist_matches(self, firm, matches: list[_MatchResult]):
        if not matches:
            return

        links = []
        txn_ids_to_update = {}

        for m in matches:
            snapshot = ReconciliationLink(
                firm=firm,
                match_group=m.match_group,
                transaction=m.txn_a,
                matched_transaction=m.txn_b,
                match_confidence=m.confidence,
                match_method=ReconciliationLink.MatchMethod.RULE_BASED,
            )
            snapshot_settlement_fx(snapshot, m.txn_a, m.txn_b)
            links.append(ReconciliationLink(
                firm=snapshot.firm,
                match_group=snapshot.match_group,
                transaction=snapshot.transaction,
                matched_transaction=snapshot.matched_transaction,
                match_confidence=snapshot.match_confidence,
                match_method=snapshot.match_method,
                settlement_currency=snapshot.settlement_currency,
                settlement_exchange_rate=snapshot.settlement_exchange_rate,
                original_base_amount=snapshot.original_base_amount,
                settlement_base_amount=snapshot.settlement_base_amount,
                fx_difference=snapshot.fx_difference,
                settled_at=timezone.now(),
            ))
            new_status = (
                Transaction.Status.FULLY_MATCHED
                if m.confidence >= Decimal("0.98")
                else Transaction.Status.PARTIALLY_MATCHED
            )
            txn_ids_to_update[m.txn_a.id] = new_status
            txn_ids_to_update[m.txn_b.id] = new_status

        with db_transaction.atomic():
            ReconciliationLink.objects.bulk_create(links, ignore_conflicts=True)
            for status_val in (Transaction.Status.FULLY_MATCHED, Transaction.Status.PARTIALLY_MATCHED):
                ids = [tid for tid, s in txn_ids_to_update.items() if s == status_val]
                if ids:
                    Transaction.objects.filter(id__in=ids).update(
                        status=status_val, updated_at=timezone.now(),
                    )

    def _persist_exceptions(self, firm, exceptions: list[dict]):
        if not exceptions:
            return

        objs = [
            ReconciliationException(
                firm=exc['firm'],
                transaction=exc['transaction'],
                candidate_transaction=exc.get('candidate_transaction'),
                match_group=exc['match_group'],
                mismatch_cause=exc['mismatch_cause'],
                confidence=exc['confidence'],
                reason=exc['reason'],
                expected_amount=exc.get('expected_amount'),
                actual_amount=exc.get('actual_amount'),
                difference=exc.get('difference'),
            )
            for exc in exceptions
        ]
        ReconciliationException.objects.bulk_create(objs)

    def _create_risk_signals(self, firm, exceptions: list[dict]):
        """Create RiskSignal entries for high-confidence mismatches."""
        signals = []
        for exc in exceptions:
            cause = exc['mismatch_cause']
            conf = exc['confidence']
            if conf < Decimal("0.70"):
                continue

            severity = 'low'
            if cause in ('incorrect_payment', 'currency_mismatch'):
                severity = 'high'
            elif cause in ('partial_payment', 'tax_deduction', 'vendor_mismatch'):
                severity = 'medium'

            txn = exc['transaction']
            signals.append(RiskSignal(
                firm=firm,
                severity=severity,
                category=RiskSignal.Category.CUSTOM,
                status=RiskSignal.Status.OPEN,
                title=f"Reconciliation: {exc['mismatch_cause'].replace('_', ' ').title()}",
                description=exc['reason'],
                confidence=conf,
                entity_type='transaction',
                entity_id=txn.id,
                vendor=txn.vendor,
                customer=txn.customer,
            ))

        if signals:
            RiskSignal.objects.bulk_create(signals)
