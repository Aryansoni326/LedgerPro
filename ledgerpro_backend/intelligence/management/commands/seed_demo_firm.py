"""
Idempotent hackathon demo seed.

Loads ~147 synthetic financial documents across 32+ vendors for one demo firm,
with planted anomalies that RiskEngine + CashFlowForecaster detect for real:

  - 3 duplicate invoices
  - 1 unusual-amount spike
  - 1 vendor bank-account change
  - Overdue receivables + large near-term payables → genuine 30/60/90 pressure

Usage (from ledgerpro_backend/):

    python manage.py seed_demo_firm
    python manage.py seed_demo_firm --reset   # wipe + recreate (default)
    python manage.py seed_demo_firm --verify-only

Demo login (full write / approve):
    email:    demo@ledgerpro.demo
    password: DemoPass123!

Owner viewer (read-only):
    email:    owner@ledgerpro.demo
    password: DemoPass123!
"""
from __future__ import annotations

import hashlib
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from agents.models import AgentAction, AgentConversation, ChatSession, PendingApproval
from billing.entitlements import get_or_create_subscription
from billing.tiers import TIER_ENTERPRISE
from firms.models import Firm
from intelligence.forecasting import CashFlowForecaster
from intelligence.models import (
    Customer,
    Document,
    FinancialSnapshot,
    ReconciliationException,
    ReconciliationLink,
    ReconciliationRun,
    RiskSignal,
    TradeFinanceLink,
    Transaction,
    Vendor,
    VendorScore,
    CustomerScore,
)
from intelligence.risk_engine import RiskEngine
from intelligence.scoring import compute_vendor_score, score_all_customers_for_firm
from invoices.models import Bill

DEMO_MARKER = "ledgerpro-hackathon-demo-v1"
DEMO_FIRM_NAME = "Apex Manufacturing Demo Pvt Ltd"
DEMO_ACCOUNTANT_EMAIL = "demo@ledgerpro.demo"
DEMO_OWNER_EMAIL = "owner@ledgerpro.demo"
DEMO_PASSWORD = "DemoPass123!"
TARGET_DOCUMENTS = 147

# 32 vendors — Indian SME-flavoured names
VENDOR_NAMES = [
    "Shree Krishna Steel Traders",
    "Om Logistics Packers",
    "Gujarat Polymer Supplies",
    "Metro Bearings India",
    "Saffron Packaging Co",
    "Vindhya Fasteners Ltd",
    "Coastal Chemicals Pvt Ltd",
    "Narmada Industrial Gases",
    "Precision Dies & Moulds",
    "Ashoka Electricals",
    "Pinnacle Safety Gear",
    "Deccan Rubber Works",
    "Sunrise Conveyors",
    "Tribhuvan Hardware Mart",
    "Eagle Lubricants",
    "Kaveri Print & Labels",
    "Horizon Scaffolding",
    "BluePeak Filters",
    "Annapurna Food Services",
    "Zenith Tooling Solutions",
    "Ravi Transport Fleet",
    "Silverline IT Services",
    "Malabar Spices Export",  # will get bank-account change
    "Northern Alloys",
    "Eastern Seals & Gaskets",
    "Western Paint Distributors",
    "Central Power Components",
    "Lakshmi Foundry Works",
    "Bharat Cutting Tools",
    "Indigo Maintenance Co",
    "Summit Office Supplies",
    "Orbit Calibration Labs",
]

CUSTOMER_NAMES = [
    "Titan Retail Stores",
    "Nova Auto Components",
    "GreenField Agro Ltd",
    "CityGrid Infrastructure",
    "BrightWave Electronics",
]


def _stable_amount(seed: str, lo: int, hi: int) -> Decimal:
    h = int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16)
    return Decimal(lo + (h % (hi - lo + 1)))


class Command(BaseCommand):
    help = "Seed idempotent hackathon demo firm with real detectable risks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            default=True,
            help="Wipe prior demo firm data before seeding (default: True).",
        )
        parser.add_argument(
            "--no-reset",
            action="store_true",
            help="Skip wipe; refuse if demo firm already exists with data.",
        )
        parser.add_argument(
            "--verify-only",
            action="store_true",
            help="Only print verification of existing demo firm.",
        )
        parser.add_argument(
            "--as-of",
            type=str,
            default="",
            help="Optional YYYY-MM-DD for deterministic dating (default: today).",
        )

    def handle(self, *args, **options):
        as_of = date.fromisoformat(options["as_of"]) if options["as_of"] else date.today()
        if options["verify_only"]:
            firm = Firm.objects.filter(name=DEMO_FIRM_NAME).first()
            if not firm:
                self.stderr.write(self.style.ERROR("Demo firm not found. Run seed_demo_firm first."))
                return
            self._verify(firm, as_of)
            return

        do_reset = not options["no_reset"]
        with transaction.atomic():
            accountant, owner, firm = self._ensure_users_and_firm()
            if do_reset:
                self._wipe_firm_data(firm)
            elif Transaction.objects.filter(firm=firm).exists():
                self.stderr.write(
                    self.style.ERROR("Demo firm already has data. Re-run without --no-reset.")
                )
                return

            vendors, customers = self._seed_parties(firm)
            bills, documents, txns = self._seed_documents_and_ledger(
                firm, accountant, vendors, customers, as_of,
            )
            self._plant_anomalies(firm, vendors, customers, accountant, as_of, txns)

        # Engines run after commit so FKs are visible
        detections = RiskEngine().scan(firm.id, as_of=as_of)
        forecast = CashFlowForecaster().forecast(firm.id, as_of=as_of)
        CashFlowForecaster().save_snapshot(firm.id, forecast)
        if forecast.pressure_day is not None:
            self._ensure_cashflow_risk_signal(firm, forecast)

        for v in Vendor.objects.filter(firm=firm):
            compute_vendor_score(v)
        score_all_customers_for_firm(firm.id)

        self.stdout.write(self.style.SUCCESS(
            f"\nSeeded demo firm id={firm.id} marker={DEMO_MARKER}"
        ))
        self.stdout.write(
            f"  Documents (Bills+Docs): "
            f"{Bill.objects.filter(firm=firm).count() + Document.objects.filter(firm=firm).count()}  "
            f"(target {TARGET_DOCUMENTS})"
        )
        self.stdout.write(f"  Vendors: {Vendor.objects.filter(firm=firm).count()}")
        self.stdout.write(f"  Transactions: {Transaction.objects.filter(firm=firm).count()}")
        self.stdout.write(f"  RiskEngine detections this run: {len(detections)}")
        self.stdout.write(
            f"  Forecast pressure_day={forecast.pressure_day} "
            f"health={forecast.health_score} "
            f"30d={forecast.position_30d}"
        )
        self.stdout.write(self.style.WARNING(
            f"\nLogin: {DEMO_ACCOUNTANT_EMAIL} / {DEMO_PASSWORD}\n"
            f"Owner viewer: {DEMO_OWNER_EMAIL} / {DEMO_PASSWORD}\n"
            f"Firm id: {firm.id}"
        ))
        self._print_demo_script(firm)
        self._verify(firm, as_of)

    # ── Users / firm ─────────────────────────────────────────────────

    def _ensure_users_and_firm(self):
        accountant, _ = User.objects.get_or_create(
            email=DEMO_ACCOUNTANT_EMAIL,
            defaults={
                "username": DEMO_ACCOUNTANT_EMAIL,
                "role": "accountant",
                "is_profile_complete": True,
            },
        )
        accountant.set_password(DEMO_PASSWORD)
        accountant.role = "accountant"
        accountant.is_profile_complete = True
        accountant.save()

        owner, _ = User.objects.get_or_create(
            email=DEMO_OWNER_EMAIL,
            defaults={
                "username": DEMO_OWNER_EMAIL,
                "role": "owner",
                "is_profile_complete": True,
            },
        )
        owner.set_password(DEMO_PASSWORD)
        owner.role = "owner"
        owner.save()

        sub = get_or_create_subscription(accountant)
        sub.tier = TIER_ENTERPRISE
        sub.custom_config = {
            "features": {"demo_marker": DEMO_MARKER, "hackathon": True},
        }
        sub.save()

        firm = Firm.objects.filter(name=DEMO_FIRM_NAME, created_by=accountant).first()
        if not firm:
            firm = Firm.objects.create(
                name=DEMO_FIRM_NAME,
                gstin="29AABCA1234A1Z5",
                jurisdiction="IN",
                base_currency="INR",
                state="Karnataka",
                city="Bengaluru",
                owner_email=DEMO_OWNER_EMAIL,
                created_by=accountant,
                status="active",
            )
        else:
            firm.owner_email = DEMO_OWNER_EMAIL
            firm.status = "active"
            firm.save(update_fields=["owner_email", "status"])
        return accountant, owner, firm

    def _wipe_firm_data(self, firm: Firm):
        """Remove prior demo rows so re-seed is deterministic."""
        PendingApproval.objects.filter(firm=firm).delete()
        AgentAction.objects.filter(conversation__firm=firm).delete()
        AgentConversation.objects.filter(firm=firm).delete()
        ChatSession.objects.filter(firm=firm).delete()
        ReconciliationException.objects.filter(firm=firm).delete()
        ReconciliationLink.objects.filter(firm=firm).delete()
        ReconciliationRun.objects.filter(firm=firm).delete()
        TradeFinanceLink.objects.filter(firm=firm).delete()
        RiskSignal.objects.filter(firm=firm).delete()
        FinancialSnapshot.objects.filter(firm=firm).delete()
        VendorScore.objects.filter(firm=firm).delete()
        CustomerScore.objects.filter(firm=firm).delete()
        Transaction.objects.filter(firm=firm).delete()
        Document.objects.filter(firm=firm).delete()
        Bill.objects.filter(firm=firm).delete()
        Vendor.objects.filter(firm=firm).delete()
        Customer.objects.filter(firm=firm).delete()
        self.stdout.write("Wiped prior demo firm intelligence / invoice rows.")

    # ── Parties ──────────────────────────────────────────────────────

    def _seed_parties(self, firm):
        vendors = []
        for i, name in enumerate(VENDOR_NAMES):
            vendors.append(
                Vendor.objects.create(
                    firm=firm,
                    name=name,
                    gstin=f"29AAAAA{i:04d}A1Z{i % 9}",
                    email=f"ap@{name.split()[0].lower()}.demo",
                    metadata={"demo_marker": DEMO_MARKER, "vendor_index": i},
                )
            )
        customers = []
        for i, name in enumerate(CUSTOMER_NAMES):
            customers.append(
                Customer.objects.create(
                    firm=firm,
                    name=name,
                    gstin=f"27BBBBB{i:04d}B1Z{i % 9}",
                    metadata={"demo_marker": DEMO_MARKER},
                )
            )
        return vendors, customers

    # ── Bulk documents + ledger ──────────────────────────────────────

    def _seed_documents_and_ledger(self, firm, user, vendors, customers, as_of: date):
        """Create TARGET_DOCUMENTS = 147 Bills+Documents and matching ledger rows."""
        bill_count = 0
        doc_count = 0
        txns: list[Transaction] = []

        # Working capital: modest cash in bank
        txns.append(
            Transaction.objects.create(
                firm=firm,
                txn_type=Transaction.TxnType.BANK_TRANSACTION,
                direction=Transaction.Direction.INFLOW,
                status=Transaction.Status.COMPLETED,
                reference_number="DEMO-BANK-OPEN",
                amount=Decimal("350000.00"),
                currency="INR",
                txn_date=as_of - timedelta(days=45),
                description="Opening operating balance",
                metadata={"demo_marker": DEMO_MARKER},
            )
        )

        # ~110 vendor invoice bills (AP) with transactions
        for i in range(110):
            vendor = vendors[i % len(vendors)]
            amt = _stable_amount(f"ap-{i}", 8000, 45000)
            d = as_of - timedelta(days=(i % 80) + 5)
            ref = f"DEMO-AP-{i:04d}"
            bill = Bill.objects.create(
                firm=firm,
                file_name=f"{ref}.pdf",
                file_url=f"/media/demo/{firm.id}/{ref}.pdf",
                file_size=12000 + i,
                status="approved",
                uploaded_by=user,
                raw_data={
                    "invoice_number": ref,
                    "vendor_name": vendor.name,
                    "total_amount": float(amt),
                    "currency": "INR",
                    "demo_marker": DEMO_MARKER,
                },
            )
            bill_count += 1
            status = (
                Transaction.Status.FULLY_MATCHED
                if i % 5 == 0
                else Transaction.Status.PENDING
            )
            txns.append(
                Transaction.objects.create(
                    firm=firm,
                    txn_type=Transaction.TxnType.INVOICE,
                    direction=Transaction.Direction.OUTFLOW,
                    status=status,
                    reference_number=ref,
                    amount=amt,
                    currency="INR",
                    txn_date=d,
                    due_date=d + timedelta(days=30),
                    vendor=vendor,
                    bill=bill,
                    description=f"Purchase from {vendor.name}",
                    metadata={"demo_marker": DEMO_MARKER, "kind": "ap"},
                )
            )

        # ~20 AR invoices (customers) — most overdue for pressure narrative
        for i in range(20):
            customer = customers[i % len(customers)]
            amt = _stable_amount(f"ar-{i}", 40000, 180000)
            # Stagger due dates deep in the past so collections are delayed
            d = as_of - timedelta(days=70 + (i % 20))
            due = as_of - timedelta(days=40 + (i % 15))
            ref = f"DEMO-AR-{i:04d}"
            bill = Bill.objects.create(
                firm=firm,
                file_name=f"{ref}.pdf",
                file_url=f"/media/demo/{firm.id}/{ref}.pdf",
                file_size=15000 + i,
                status="approved",
                uploaded_by=user,
                raw_data={
                    "invoice_number": ref,
                    "customer_name": customer.name,
                    "total_amount": float(amt),
                    "demo_marker": DEMO_MARKER,
                },
            )
            bill_count += 1
            txns.append(
                Transaction.objects.create(
                    firm=firm,
                    txn_type=Transaction.TxnType.INVOICE,
                    direction=Transaction.Direction.INFLOW,
                    status=Transaction.Status.PENDING,
                    reference_number=ref,
                    amount=amt,
                    currency="INR",
                    txn_date=d,
                    due_date=due,
                    customer=customer,
                    bill=bill,
                    description=f"Receivable from {customer.name}",
                    metadata={"demo_marker": DEMO_MARKER, "kind": "ar"},
                )
            )

        # Remaining documents so total Bills+Docs == TARGET after pressure + anomaly bills
        pressure_bills = 3
        anomaly_bills = 4  # planted in _plant_anomalies (1 spike + 3 duplicates)
        remaining = TARGET_DOCUMENTS - bill_count - pressure_bills - anomaly_bills
        if remaining < 0:
            remaining = 0
        doc_types = ["purchase_order", "bank_statement", "contract", "credit_note"]
        for i in range(remaining):
            doc_type = doc_types[i % len(doc_types)]
            vendor = vendors[i % len(vendors)]
            ref = f"DEMO-DOC-{i:04d}"
            Document.objects.create(
                firm=firm,
                doc_type=doc_type,
                file_name=f"{ref}.pdf",
                file_url=f"/media/demo/{firm.id}/{ref}.pdf",
                file_size=9000 + i,
                status="approved",
                uploaded_by=user,
                raw_data={"reference": ref, "demo_marker": DEMO_MARKER},
                classified_type=doc_type,
                classification_confidence=Decimal("0.9500"),
            )
            doc_count += 1
            if doc_type == "purchase_order":
                Transaction.objects.create(
                    firm=firm,
                    txn_type=Transaction.TxnType.PURCHASE_ORDER,
                    direction=Transaction.Direction.OUTFLOW,
                    status=Transaction.Status.PENDING,
                    reference_number=ref,
                    amount=_stable_amount(f"po-{i}", 5000, 25000),
                    currency="INR",
                    txn_date=as_of - timedelta(days=(i % 40) + 2),
                    vendor=vendor,
                    metadata={"demo_marker": DEMO_MARKER, "kind": "po"},
                )

        # Large upcoming payables to force negative 30/60/90 with thin cash
        for i, (vendor, amt, days) in enumerate([
            (vendors[0], Decimal("420000.00"), 12),
            (vendors[1], Decimal("280000.00"), 25),
            (vendors[2], Decimal("190000.00"), 45),
        ]):
            ref = f"DEMO-AP-PRESSURE-{i}"
            bill = Bill.objects.create(
                firm=firm,
                file_name=f"{ref}.pdf",
                file_url=f"/media/demo/{firm.id}/{ref}.pdf",
                file_size=18000,
                status="approved",
                uploaded_by=user,
                raw_data={"invoice_number": ref, "demo_marker": DEMO_MARKER},
            )
            bill_count += 1
            Transaction.objects.create(
                firm=firm,
                txn_type=Transaction.TxnType.INVOICE,
                direction=Transaction.Direction.OUTFLOW,
                status=Transaction.Status.PENDING,
                reference_number=ref,
                amount=amt,
                currency="INR",
                txn_date=as_of,
                due_date=as_of + timedelta(days=days),
                vendor=vendor,
                bill=bill,
                description=f"Large payable to {vendor.name}",
                metadata={"demo_marker": DEMO_MARKER, "kind": "pressure_ap"},
            )

        return bill_count, doc_count, txns

    def _plant_anomalies(self, firm, vendors, customers, user, as_of, _txns):
        """Plant duplicates, unusual amount, bank-account change."""
        # ── Vendor for duplicates + unusual: use a steady vendor with history ──
        steady = vendors[4]  # Saffron Packaging Co
        # Baseline invoices ~12k
        for i in range(4):
            ref = f"DEMO-BASE-{i}"
            Transaction.objects.create(
                firm=firm,
                txn_type=Transaction.TxnType.INVOICE,
                direction=Transaction.Direction.OUTFLOW,
                status=Transaction.Status.COMPLETED,
                reference_number=ref,
                amount=Decimal("12000.00"),
                currency="INR",
                txn_date=as_of - timedelta(days=90 - i * 15),
                vendor=steady,
                metadata={"demo_marker": DEMO_MARKER, "kind": "baseline"},
            )

        # Unusual amount: 5× median
        spike_ref = "DEMO-SPIKE-55000"
        bill = Bill.objects.create(
            firm=firm,
            file_name=f"{spike_ref}.pdf",
            file_url=f"/media/demo/{firm.id}/{spike_ref}.pdf",
            file_size=11111,
            status="needs_review",
            uploaded_by=user,
            raw_data={"invoice_number": spike_ref, "total_amount": 55000, "demo_marker": DEMO_MARKER},
        )
        Transaction.objects.create(
            firm=firm,
            txn_type=Transaction.TxnType.INVOICE,
            direction=Transaction.Direction.OUTFLOW,
            status=Transaction.Status.PENDING,
            reference_number=spike_ref,
            amount=Decimal("55000.00"),
            currency="INR",
            txn_date=as_of - timedelta(days=2),
            vendor=steady,
            bill=bill,
            description="Anomalous packaging invoice",
            metadata={"demo_marker": DEMO_MARKER, "kind": "unusual"},
        )

        # ── 3 duplicate invoices (same ref / fingerprint) ──
        dup_vendor = vendors[0]
        original_ref = "DEMO-DUP-INV-1001"
        for i, day_offset in enumerate([10, 8, 7]):
            ref = original_ref if i < 2 else "DEMO-DUP-INV-1001-COPY"
            # First two share identical reference; third shares vendor+amount in window
            amount = Decimal("88000.00")
            bill = Bill.objects.create(
                firm=firm,
                file_name=f"DEMO-DUP-{i}.pdf",
                file_url=f"/media/demo/{firm.id}/DEMO-DUP-{i}.pdf",
                file_size=10000 + i,
                status="needs_review",
                uploaded_by=user,
                raw_data={"invoice_number": ref, "demo_marker": DEMO_MARKER, "dup_index": i},
            )
            Transaction.objects.create(
                firm=firm,
                txn_type=Transaction.TxnType.INVOICE,
                direction=Transaction.Direction.OUTFLOW,
                status=Transaction.Status.PENDING,
                reference_number=ref if i < 2 else f"DEMO-DUP-FINGERPRINT-{i}",
                amount=amount,
                currency="INR",
                txn_date=as_of - timedelta(days=day_offset),
                vendor=dup_vendor,
                bill=bill,
                description="Duplicate invoice candidate",
                metadata={"demo_marker": DEMO_MARKER, "kind": "duplicate", "dup_index": i},
            )

        # ── Vendor bank-account change (Malabar Spices Export) ──
        bank_vendor = vendors[22]
        bank_vendor.metadata = {
            "demo_marker": DEMO_MARKER,
            "bank_detail_changes": 1,
            "bank_account_history": [
                {
                    "account_mask": "XXXX4412",
                    "ifsc": "HDFC0001234",
                    "changed_on": str(as_of - timedelta(days=120)),
                },
                {
                    "account_mask": "XXXX9981",
                    "ifsc": "ICIC0005678",
                    "changed_on": str(as_of - timedelta(days=3)),
                },
            ],
        }
        bank_vendor.save(update_fields=["metadata", "updated_at"])

    def _ensure_cashflow_risk_signal(self, firm, forecast):
        exists = RiskSignal.objects.filter(
            firm=firm,
            category=RiskSignal.Category.CASH_FLOW_RISK,
            status=RiskSignal.Status.OPEN,
        ).exists()
        if exists:
            return
        RiskSignal.objects.create(
            firm=firm,
            severity=RiskSignal.Severity.HIGH,
            category=RiskSignal.Category.CASH_FLOW_RISK,
            status=RiskSignal.Status.OPEN,
            title="30/60/90 Cash-Flow Pressure",
            description=forecast.risk_explanation,
            confidence=Decimal("0.9200"),
            entity_type="firm",
            entity_id=firm.id,
            ai_reasoning={
                "engine": "CashFlowForecaster",
                "pressure_day": forecast.pressure_day,
                "position_30d": str(forecast.position_30d),
                "position_60d": str(forecast.position_60d),
                "position_90d": str(forecast.position_90d),
                "demo_marker": DEMO_MARKER,
            },
        )

    # ── Verify / demo script ─────────────────────────────────────────

    def _verify(self, firm: Firm, as_of: date):
        docs = Bill.objects.filter(firm=firm).count() + Document.objects.filter(firm=firm).count()
        vendors = Vendor.objects.filter(firm=firm).count()
        dups = RiskSignal.objects.filter(
            firm=firm, category=RiskSignal.Category.DUPLICATE_INVOICE, status="open",
        ).count()
        unusual = RiskSignal.objects.filter(
            firm=firm, category=RiskSignal.Category.UNUSUAL_AMOUNT, status="open",
        ).count()
        bank = RiskSignal.objects.filter(
            firm=firm, category=RiskSignal.Category.VENDOR_RISK, status="open",
        ).count()
        cf = RiskSignal.objects.filter(
            firm=firm, category=RiskSignal.Category.CASH_FLOW_RISK, status="open",
        ).count()
        forecast = CashFlowForecaster().forecast(firm.id, as_of=as_of)

        ok = (
            docs >= 100
            and vendors >= 30
            and dups >= 2
            and unusual >= 1
            and bank >= 1
            and forecast.pressure_day is not None
        )
        style = self.style.SUCCESS if ok else self.style.ERROR
        self.stdout.write(style(
            f"\nVERIFY {'PASS' if ok else 'FAIL'}: docs={docs} vendors={vendors} "
            f"dup_signals={dups} unusual={unusual} bank_change={bank} "
            f"cashflow_signals={cf} pressure_day={forecast.pressure_day}"
        ))
        if not ok:
            self.stderr.write("Demo narrative data path incomplete — re-seed with --reset.")

    def _print_demo_script(self, firm: Firm):
        self.stdout.write("\n-- Live demo narrative (real API paths) --")
        self.stdout.write(f"1. Open firm {firm.id} dashboard — document count from Bills+Documents.")
        self.stdout.write("2. Risk signals: duplicates / unusual / bank change / cash-flow (RiskEngine + forecast).")
        self.stdout.write("3. Ask LedgerPro: \"What is my cash flow forecast and open risk signals?\"")
        self.stdout.write("4. Ask: \"Flag the suspicious duplicate invoice for review\"")
        self.stdout.write("   -> creates PendingApproval via flag_transaction (auto-targets open risk txn).")
        self.stdout.write("5. Approvals panel -> Approve as demo@ledgerpro.demo -> metadata.flagged written.")
        self.stdout.write("6. Optional: \"Send payment reminder for overdue receivables\" -> approve -> reminder_queued.")
