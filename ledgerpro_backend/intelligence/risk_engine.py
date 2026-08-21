"""
RiskEngine — deterministic detectors for labeled risk categories.

Produces ``RiskSignal`` rows for:
  - duplicate_invoice  (same vendor + amount + near dates, or identical reference)
  - unusual_amount     (invoice amount far from vendor historical baseline)
  - late_payment       (overdue unpaid invoices past grace period)

Designed for evaluation: detections are keyed by ``(category, entity_id)``
where ``entity_type`` is always ``transaction``.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from django.db import transaction as db_transaction
from django.utils import timezone

from .models import RiskSignal, Transaction

logger = logging.getLogger(__name__)

_ZERO = Decimal("0.00")


@dataclass
class RiskEngineConfig:
    duplicate_date_window_days: int = 14
    unusual_amount_min_history: int = 3
    unusual_amount_multiplier: Decimal = Decimal("3.0")
    late_payment_grace_days: int = 1
    persist: bool = True


@dataclass
class Detection:
    category: str
    entity_id: int
    reference_number: str
    severity: str
    title: str
    description: str
    confidence: Decimal
    vendor_id: int | None = None
    customer_id: int | None = None

    def key(self) -> tuple[str, int]:
        return (self.category, self.entity_id)


class RiskEngine:
    """Stateless risk detector. Entry point: ``scan(firm_id, **kwargs)``."""

    def __init__(self, config: RiskEngineConfig | None = None):
        self.cfg = config or RiskEngineConfig()

    def scan(self, firm_id: int, as_of: date | None = None) -> list[Detection]:
        from firms.models import Firm

        firm = Firm.objects.get(pk=firm_id)
        today = as_of or date.today()

        invoices = list(
            Transaction.objects.filter(
                firm=firm,
                txn_type=Transaction.TxnType.INVOICE,
                status__in=[
                    Transaction.Status.PENDING,
                    Transaction.Status.COMPLETED,
                    Transaction.Status.PARTIALLY_MATCHED,
                    Transaction.Status.FULLY_MATCHED,
                ],
            ).select_related("vendor", "customer")
        )

        detections: list[Detection] = []
        detections.extend(self._detect_duplicates(invoices))
        detections.extend(self._detect_unusual_amounts(invoices))
        detections.extend(self._detect_late_payments(invoices, today))
        detections.extend(self._detect_vendor_bank_changes(firm))

        # Deduplicate identical (category, entity_id)
        seen: set[tuple[str, int]] = set()
        unique: list[Detection] = []
        for d in detections:
            if d.key() in seen:
                continue
            seen.add(d.key())
            unique.append(d)

        if self.cfg.persist and unique:
            self._persist(firm, unique)

        return unique

    # ── Detectors ────────────────────────────────────────────────────

    def _detect_duplicates(self, invoices: list[Transaction]) -> list[Detection]:
        """Flag later invoices that collide with an earlier twin."""
        by_ref: dict[str, list[Transaction]] = defaultdict(list)
        by_fingerprint: dict[tuple, list[Transaction]] = defaultdict(list)

        for inv in invoices:
            ref = (inv.reference_number or "").strip().upper()
            if ref:
                by_ref[ref].append(inv)
            if inv.vendor_id:
                key = (inv.vendor_id, inv.amount, inv.currency)
                by_fingerprint[key].append(inv)

        flagged: dict[int, Detection] = {}

        for ref, group in by_ref.items():
            if len(group) < 2:
                continue
            ordered = sorted(group, key=lambda t: (t.txn_date, t.id))
            for dup in ordered[1:]:
                flagged[dup.id] = self._dup_detection(dup, ordered[0], f"identical reference '{ref}'")

        window = timedelta(days=self.cfg.duplicate_date_window_days)
        for _key, group in by_fingerprint.items():
            if len(group) < 2:
                continue
            ordered = sorted(group, key=lambda t: (t.txn_date, t.id))
            for i, cand in enumerate(ordered):
                if cand.id in flagged:
                    continue
                for prior in ordered[:i]:
                    if abs((cand.txn_date - prior.txn_date).days) <= window.days:
                        flagged[cand.id] = self._dup_detection(
                            cand,
                            prior,
                            (
                                f"same vendor/amount within "
                                f"{self.cfg.duplicate_date_window_days} days"
                            ),
                        )
                        break

        return list(flagged.values())

    def _dup_detection(self, dup: Transaction, original: Transaction, reason: str) -> Detection:
        return Detection(
            category=RiskSignal.Category.DUPLICATE_INVOICE,
            entity_id=dup.id,
            reference_number=dup.reference_number or "",
            severity=RiskSignal.Severity.HIGH,
            title="Duplicate Invoice Detected",
            description=(
                f"Invoice {dup.reference_number or dup.id} ({dup.currency} {dup.amount}) "
                f"appears to duplicate {original.reference_number or original.id} "
                f"({reason})."
            ),
            confidence=Decimal("0.9200"),
            vendor_id=dup.vendor_id,
            customer_id=dup.customer_id,
        )

    def _detect_unusual_amounts(self, invoices: list[Transaction]) -> list[Detection]:
        by_vendor: dict[int | None, list[Transaction]] = defaultdict(list)
        for inv in invoices:
            by_vendor[inv.vendor_id].append(inv)

        out: list[Detection] = []
        for vendor_id, group in by_vendor.items():
            if vendor_id is None or len(group) < self.cfg.unusual_amount_min_history + 1:
                continue
            amounts = [t.amount for t in group]
            # Baseline excludes the candidate itself via leave-one-out median
            for cand in group:
                peers = [a for t, a in zip(group, amounts) if t.id != cand.id]
                if len(peers) < self.cfg.unusual_amount_min_history:
                    continue
                base = Decimal(str(median(peers)))
                if base <= _ZERO:
                    continue
                if cand.amount >= base * self.cfg.unusual_amount_multiplier:
                    ratio = (cand.amount / base).quantize(Decimal("0.01"))
                    out.append(
                        Detection(
                            category=RiskSignal.Category.UNUSUAL_AMOUNT,
                            entity_id=cand.id,
                            reference_number=cand.reference_number or "",
                            severity=RiskSignal.Severity.MEDIUM,
                            title="Unusual Invoice Amount",
                            description=(
                                f"Invoice {cand.reference_number or cand.id} amount "
                                f"{cand.currency} {cand.amount} is {ratio}× the vendor "
                                f"median of {base}."
                            ),
                            confidence=Decimal("0.8000"),
                            vendor_id=cand.vendor_id,
                            customer_id=cand.customer_id,
                        )
                    )
        return out

    def _detect_late_payments(
        self, invoices: list[Transaction], today: date
    ) -> list[Detection]:
        grace = timedelta(days=self.cfg.late_payment_grace_days)
        out: list[Detection] = []
        open_statuses = {
            Transaction.Status.PENDING,
            Transaction.Status.PARTIALLY_MATCHED,
        }
        for inv in invoices:
            if inv.direction != Transaction.Direction.INFLOW:
                continue
            if inv.status not in open_statuses:
                continue
            if not inv.due_date:
                continue
            if inv.due_date + grace >= today:
                continue
            days_late = (today - inv.due_date).days
            severity = RiskSignal.Severity.HIGH if days_late >= 60 else RiskSignal.Severity.MEDIUM
            out.append(
                Detection(
                    category=RiskSignal.Category.LATE_PAYMENT,
                    entity_id=inv.id,
                    reference_number=inv.reference_number or "",
                    severity=severity,
                    title="Late Receivable",
                    description=(
                        f"Invoice {inv.reference_number or inv.id} was due {inv.due_date} "
                        f"and is {days_late} day(s) overdue "
                        f"({inv.currency} {inv.amount})."
                    ),
                    confidence=Decimal("0.9500"),
                    vendor_id=inv.vendor_id,
                    customer_id=inv.customer_id,
                )
            )
        return out

    def _detect_vendor_bank_changes(self, firm) -> list[Detection]:
        """Flag vendors whose metadata shows a recent bank-account change."""
        from .models import Vendor

        out: list[Detection] = []
        for vendor in Vendor.objects.filter(firm=firm):
            meta = vendor.metadata if isinstance(vendor.metadata, dict) else {}
            history = meta.get("bank_account_history") or []
            changes = int(meta.get("bank_detail_changes") or 0)
            if changes < 1 and len(history) < 2:
                continue

            # Anchor entity_id to the vendor id; entity_type stays vendor via persist override
            latest = history[-1] if history else {}
            previous = history[-2] if len(history) >= 2 else {}
            out.append(
                Detection(
                    category=RiskSignal.Category.VENDOR_RISK,
                    entity_id=vendor.id,
                    reference_number=str(latest.get("account_mask") or vendor.name),
                    severity=RiskSignal.Severity.HIGH,
                    title="Vendor Bank Account Change",
                    description=(
                        f"Vendor '{vendor.name}' changed payout account "
                        f"from {previous.get('account_mask', 'unknown')} "
                        f"to {latest.get('account_mask', 'unknown')} "
                        f"on {latest.get('changed_on', 'recent date')} "
                        f"({changes or max(len(history) - 1, 1)} recorded change(s))."
                    ),
                    confidence=Decimal("0.9000"),
                    vendor_id=vendor.id,
                )
            )
        return out

    # ── Persistence ──────────────────────────────────────────────────

    def _persist(self, firm, detections: list[Detection]) -> None:
        existing = set(
            RiskSignal.objects.filter(
                firm=firm,
                status=RiskSignal.Status.OPEN,
                category__in=[
                    RiskSignal.Category.DUPLICATE_INVOICE,
                    RiskSignal.Category.UNUSUAL_AMOUNT,
                    RiskSignal.Category.LATE_PAYMENT,
                    RiskSignal.Category.VENDOR_RISK,
                    RiskSignal.Category.CASH_FLOW_RISK,
                ],
            ).values_list("category", "entity_type", "entity_id")
        )
        to_create = []
        for d in detections:
            entity_type = (
                "vendor"
                if d.category == RiskSignal.Category.VENDOR_RISK
                else "transaction"
            )
            key = (d.category, entity_type, d.entity_id)
            if key in existing:
                continue
            to_create.append(
                RiskSignal(
                    firm=firm,
                    severity=d.severity,
                    category=d.category,
                    status=RiskSignal.Status.OPEN,
                    title=d.title,
                    description=d.description,
                    confidence=d.confidence,
                    entity_type=entity_type,
                    entity_id=d.entity_id,
                    vendor_id=d.vendor_id,
                    customer_id=d.customer_id,
                    ai_reasoning={"engine": "RiskEngine", "as_of": timezone.now().isoformat()},
                )
            )
        if to_create:
            with db_transaction.atomic():
                RiskSignal.objects.bulk_create(to_create)
            logger.info("RiskEngine persisted %s signals for firm %s", len(to_create), firm.id)
