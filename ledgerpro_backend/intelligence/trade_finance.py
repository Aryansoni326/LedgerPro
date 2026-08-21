"""
Trade-finance analysis engine.

Connects PO → Invoice → Customs (ImportExportRecord) → Payment and
detects two categories of risk:

1. **Value mismatch**: invoice amount deviates from customs-declared
   assessable value beyond a configurable tolerance.
2. **Payment before shipment**: payment due date falls before the
   expected date of shipment realization (BE date + transit buffer).

All findings are persisted as ``RiskSignal`` rows so they appear on the
existing risk dashboard — no parallel alerting system.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from .models import (
    RiskSignal,
    TradeFinanceLink,
    Transaction,
    Vendor,
)

logger = logging.getLogger(__name__)

VALUE_MISMATCH_TOLERANCE_PCT = Decimal("0.05")
TRANSIT_BUFFER_DAYS = 14


@dataclass
class TradeFinanceConfig:
    value_tolerance_pct: Decimal = VALUE_MISMATCH_TOLERANCE_PCT
    transit_buffer_days: int = TRANSIT_BUFFER_DAYS


class TradeFinanceAnalyser:
    """Stateless engine.  Entry point: ``analyse(firm_id)``."""

    def __init__(self, config: TradeFinanceConfig | None = None):
        self.cfg = config or TradeFinanceConfig()

    def analyse(self, firm_id: int) -> dict:
        """Run full trade-finance risk detection for a firm."""
        from firms.models import Firm
        from trade_docs.models import ImportExportRecord

        firm = Firm.objects.get(pk=firm_id)

        trade_docs = list(
            ImportExportRecord.objects.filter(
                firm=firm,
                is_deleted=False,
                status__in=["needs_review", "verified"],
                assessable_value__isnull=False,
            ).order_by("-be_date")
        )

        links_created = 0
        signals_created = 0
        signals = []

        for td in trade_docs:
            existing = TradeFinanceLink.objects.filter(
                firm=firm, trade_doc=td, is_deleted=False,
            ).first()
            if existing and existing.last_analysed_at:
                continue

            link, inv_txn, pay_txn, po_txn = self._build_link(firm, td)
            link.save()
            links_created += 1

            new_signals = self._detect_risks(firm, link, td)
            signals.extend(new_signals)

            link.last_analysed_at = timezone.now()
            link.status = (
                TradeFinanceLink.LinkStatus.FLAGGED
                if new_signals
                else (
                    TradeFinanceLink.LinkStatus.COMPLETE
                    if link.invoice_txn and link.payment_txn
                    else TradeFinanceLink.LinkStatus.PARTIAL
                )
            )
            link.save()

        if signals:
            RiskSignal.objects.bulk_create(signals)
            signals_created = len(signals)

        return {
            "firm_id": firm_id,
            "trade_docs_scanned": len(trade_docs),
            "links_created": links_created,
            "signals_created": signals_created,
        }

    # ── Link building ────────────────────────────────────────────

    def _build_link(self, firm, td):
        """Find related transactions and build a TradeFinanceLink."""
        vendor = self._match_vendor(firm, td)

        inv_txn = self._find_invoice_txn(firm, td, vendor)
        pay_txn = self._find_payment_txn(firm, td, vendor, inv_txn)
        po_txn = self._find_po_txn(firm, td, vendor)

        inv_amount = inv_txn.amount if inv_txn else None
        inv_currency = inv_txn.currency if inv_txn else ""

        customs_value = td.assessable_value
        customs_currency = (td.currency or "").upper()

        diff = None
        diff_pct = None
        if inv_amount is not None and customs_value:
            if (inv_currency or "").upper() == customs_currency:
                diff = inv_amount - customs_value
                if customs_value > 0:
                    diff_pct = (abs(diff) / customs_value * Decimal("100")).quantize(Decimal("0.0001"))

        expected_shipment = None
        if td.be_date:
            expected_shipment = td.be_date + timedelta(days=self.cfg.transit_buffer_days)

        payment_due = None
        pbs = False
        if pay_txn and pay_txn.due_date:
            payment_due = pay_txn.due_date
        elif inv_txn and inv_txn.due_date:
            payment_due = inv_txn.due_date

        if payment_due and expected_shipment and payment_due < expected_shipment:
            pbs = True

        link = TradeFinanceLink(
            firm=firm,
            purchase_order_txn=po_txn,
            invoice_txn=inv_txn,
            trade_doc=td,
            payment_txn=pay_txn,
            vendor=vendor,
            invoice_amount=inv_amount,
            invoice_currency=inv_currency,
            customs_declared_value=customs_value,
            customs_currency=customs_currency,
            value_difference=diff,
            value_difference_pct=diff_pct,
            expected_shipment_date=expected_shipment,
            payment_due_date=payment_due,
            payment_before_shipment=pbs,
        )
        return link, inv_txn, pay_txn, po_txn

    # ── Transaction matching helpers ─────────────────────────────

    def _match_vendor(self, firm, td):
        if not td.shipper_name:
            return None
        return (
            Vendor.objects.filter(firm=firm, name__iexact=td.shipper_name.strip())
            .first()
        )

    def _find_invoice_txn(self, firm, td, vendor):
        qs = Transaction.objects.filter(
            firm=firm,
            txn_type=Transaction.TxnType.INVOICE,
            is_deleted=False,
        )
        if vendor:
            qs = qs.filter(vendor=vendor)
        if td.be_date:
            qs = qs.filter(txn_date__gte=td.be_date - timedelta(days=90))
        qs = qs.filter(trade_doc__isnull=True)

        if td.assessable_value and td.currency:
            exact = qs.filter(
                amount=td.assessable_value, currency__iexact=td.currency,
            ).first()
            if exact:
                return exact

        return qs.order_by("-txn_date").first()

    def _find_payment_txn(self, firm, td, vendor, inv_txn):
        qs = Transaction.objects.filter(
            firm=firm,
            txn_type=Transaction.TxnType.PAYMENT,
            direction=Transaction.Direction.OUTFLOW,
            is_deleted=False,
        )
        if vendor:
            qs = qs.filter(vendor=vendor)
        elif inv_txn and inv_txn.vendor:
            qs = qs.filter(vendor=inv_txn.vendor)
        else:
            return None

        if inv_txn:
            qs = qs.filter(txn_date__gte=inv_txn.txn_date - timedelta(days=30))

        return qs.order_by("-txn_date").first()

    def _find_po_txn(self, firm, td, vendor):
        qs = Transaction.objects.filter(
            firm=firm,
            txn_type=Transaction.TxnType.PURCHASE_ORDER,
            is_deleted=False,
        )
        if vendor:
            qs = qs.filter(vendor=vendor)
        if td.be_date:
            qs = qs.filter(txn_date__lte=td.be_date)
        return qs.order_by("-txn_date").first()

    # ── Risk detection ───────────────────────────────────────────

    def _detect_risks(self, firm, link, td) -> list[RiskSignal]:
        signals: list[RiskSignal] = []
        notes: list[str] = []

        if link.value_difference is not None and link.customs_declared_value:
            pct = link.value_difference_pct or Decimal("0")
            if pct > self.cfg.value_tolerance_pct * 100:
                severity = "high" if pct > Decimal("15") else "medium"
                desc = (
                    f"Invoice amount ({link.invoice_currency} {link.invoice_amount}) "
                    f"differs from customs declared value "
                    f"({link.customs_currency} {link.customs_declared_value}) "
                    f"by {link.value_difference} ({pct}%). "
                    f"Tolerance is {self.cfg.value_tolerance_pct * 100}%."
                )
                signals.append(RiskSignal(
                    firm=firm,
                    severity=severity,
                    category=RiskSignal.Category.TRADE_VALUE_MISMATCH,
                    status=RiskSignal.Status.OPEN,
                    title="Invoice vs Customs Value Mismatch",
                    description=desc,
                    confidence=Decimal("0.9000"),
                    entity_type="trade_doc",
                    entity_id=td.id,
                    vendor=link.vendor,
                ))
                notes.append(f"VALUE_MISMATCH: {desc}")

        if link.payment_before_shipment:
            desc = (
                f"Payment due date ({link.payment_due_date}) falls before "
                f"expected shipment realization ({link.expected_shipment_date}). "
                f"BE date: {td.be_date}, transit buffer: {self.cfg.transit_buffer_days} days."
            )
            signals.append(RiskSignal(
                firm=firm,
                severity="high",
                category=RiskSignal.Category.PAYMENT_BEFORE_SHIPMENT,
                status=RiskSignal.Status.OPEN,
                title="Payment Due Before Shipment Realization",
                description=desc,
                confidence=Decimal("0.9500"),
                entity_type="trade_doc",
                entity_id=td.id,
                vendor=link.vendor,
            ))
            notes.append(f"PAYMENT_BEFORE_SHIPMENT: {desc}")

        link.analysis_notes = notes
        return signals
