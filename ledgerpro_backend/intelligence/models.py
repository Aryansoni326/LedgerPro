from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from firms.models import Firm


# ---------------------------------------------------------------------------
# Shared base: soft-delete + firm-scoped multi-tenancy
# ---------------------------------------------------------------------------

class FirmScopedManager(models.Manager):
    """Default manager that excludes soft-deleted rows."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class FirmScopedModel(models.Model):
    """Abstract base for all intelligence models.

    Provides:
    - firm FK for multi-tenancy (matching existing pattern in invoices, vault, etc.)
    - soft-delete via is_deleted + deleted_at
    - timestamps
    """

    firm = models.ForeignKey(
        Firm,
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)ss",
        db_index=True,
    )
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = FirmScopedManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self):
        from django.utils import timezone
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])


# ---------------------------------------------------------------------------
# Document — unified intake for new document types
# ---------------------------------------------------------------------------

class Document(FirmScopedModel):
    """Unified document record for types not covered by the legacy apps
    (invoices.Bill, trade_docs.ImportExportRecord, eway_bills.EwayBillRecord).

    Follows the exact same status lifecycle as existing models so the
    processing → needs_review → verified → approved / extraction_failed
    pipeline is preserved.
    """

    class DocType(models.TextChoices):
        PURCHASE_ORDER = 'purchase_order', 'Purchase Order'
        BANK_STATEMENT = 'bank_statement', 'Bank Statement'
        CONTRACT = 'contract', 'Contract'
        CREDIT_NOTE = 'credit_note', 'Credit Note'
        DEBIT_NOTE = 'debit_note', 'Debit Note'

    STATUS_CHOICES = [
        ('processing', 'Processing'),
        ('needs_review', 'Needs Review'),
        ('verified', 'Verified'),
        ('approved', 'Approved'),
        ('extraction_failed', 'Extraction Failed'),
    ]

    doc_type = models.CharField(max_length=30, choices=DocType.choices)
    file_name = models.CharField(max_length=255)
    file_url = models.CharField(max_length=1000)
    file_size = models.IntegerField(default=0)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='processing')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploaded_documents',
    )
    uploaded_at = models.DateTimeField(default=timezone.now)
    raw_data = models.JSONField(blank=True, null=True)
    extraction_raw_json = models.TextField(blank=True, null=True)
    validation_warnings = models.JSONField(default=list, blank=True)
    extraction_failed = models.BooleanField(default=False)

    # Classification metadata
    classified_type = models.CharField(max_length=30, blank=True, default='')
    classification_confidence = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal('0.0000'),
    )

    class Meta:
        indexes = [
            models.Index(fields=['firm', 'doc_type', 'status']),
            models.Index(fields=['firm', 'uploaded_at']),
        ]

    def __str__(self):
        return f"{self.get_doc_type_display()} — {self.file_name} ({self.status})"


# ---------------------------------------------------------------------------
# Vendor & Customer
# ---------------------------------------------------------------------------

class Vendor(FirmScopedModel):
    name = models.CharField(max_length=255)
    gstin = models.CharField(max_length=15, blank=True, default="")
    pan = models.CharField(max_length=10, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="")
    address = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["firm", "gstin"],
                condition=models.Q(is_deleted=False, gstin__gt=""),
                name="uq_vendor_firm_gstin",
            ),
        ]
        indexes = [
            models.Index(fields=["firm", "name"]),
        ]

    def __str__(self):
        return f"{self.name} (Vendor, {self.firm.name})"


class Customer(FirmScopedModel):
    name = models.CharField(max_length=255)
    gstin = models.CharField(max_length=15, blank=True, default="")
    pan = models.CharField(max_length=10, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="")
    address = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["firm", "gstin"],
                condition=models.Q(is_deleted=False, gstin__gt=""),
                name="uq_customer_firm_gstin",
            ),
        ]
        indexes = [
            models.Index(fields=["firm", "name"]),
        ]

    def __str__(self):
        return f"{self.name} (Customer, {self.firm.name})"


# ---------------------------------------------------------------------------
# ExchangeRate — historical FX rates (one row per date + currency pair)
# ---------------------------------------------------------------------------

class ExchangeRate(models.Model):
    """Historical FX rate for converting one currency into another.

    ``rate`` means: 1 unit of ``from_currency`` equals ``rate`` units of
    ``to_currency`` on ``rate_date``.
    """

    from_currency = models.CharField(max_length=10)
    to_currency = models.CharField(max_length=10)
    rate_date = models.DateField()
    rate = models.DecimalField(max_digits=18, decimal_places=8)
    source = models.CharField(max_length=100, default="open_er_api")
    fetched_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["from_currency", "to_currency", "rate_date"],
                name="uq_fx_pair_date",
            ),
        ]
        indexes = [
            models.Index(fields=["from_currency", "to_currency", "-rate_date"], name="idx_fx_pair_date"),
        ]

    def __str__(self):
        return (
            f"{self.from_currency}/{self.to_currency} {self.rate} "
            f"on {self.rate_date}"
        )


# ---------------------------------------------------------------------------
# Transaction — unified ledger of financial movements
# ---------------------------------------------------------------------------

class Transaction(FirmScopedModel):
    class TxnType(models.TextChoices):
        INVOICE = "invoice", "Invoice"
        PAYMENT = "payment", "Payment"
        PURCHASE_ORDER = "purchase_order", "Purchase Order"
        BANK_TRANSACTION = "bank_transaction", "Bank Transaction"
        CREDIT_NOTE = "credit_note", "Credit Note"
        DEBIT_NOTE = "debit_note", "Debit Note"

    class Direction(models.TextChoices):
        INFLOW = "inflow", "Inflow"
        OUTFLOW = "outflow", "Outflow"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        PARTIALLY_MATCHED = "partially_matched", "Partially Matched"
        FULLY_MATCHED = "fully_matched", "Fully Matched"
        CANCELLED = "cancelled", "Cancelled"

    txn_type = models.CharField(max_length=30, choices=TxnType.choices)
    direction = models.CharField(max_length=10, choices=Direction.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reference_number = models.CharField(max_length=255, blank=True, default="")
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=10, default="INR")
    exchange_rate = models.DecimalField(
        max_digits=18,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Transaction-date FX rate from currency into the firm's base currency.",
    )
    base_currency = models.CharField(max_length=10, default="INR")
    base_currency_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Functional/base-currency amount locked at transaction time.",
    )
    txn_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True, default="")

    vendor = models.ForeignKey(
        Vendor, on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions",
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions",
    )

    # Link back to existing document models (nullable — not every txn comes from a document)
    bill = models.ForeignKey(
        "invoices.Bill", on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions",
    )
    trade_doc = models.ForeignKey(
        "trade_docs.ImportExportRecord", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="transactions",
    )
    eway_bill = models.ForeignKey(
        "eway_bills.EwayBillRecord", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="transactions",
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["firm", "txn_date"]),
            models.Index(fields=["firm", "txn_type", "status"]),
            models.Index(fields=["firm", "vendor"]),
            models.Index(fields=["firm", "customer"]),
            models.Index(fields=["reference_number"]),
            models.Index(fields=["firm", "currency", "txn_date"]),
        ]

    def save(self, *args, **kwargs):
        if self.firm_id:
            firm_base_currency = (getattr(self.firm, "base_currency", "") or "INR").upper()
            self.currency = (self.currency or firm_base_currency).upper()
            self.base_currency = (self.base_currency or firm_base_currency).upper()
            if self.base_currency != firm_base_currency:
                self.base_currency = firm_base_currency

            if self.exchange_rate is None or self.base_currency_amount is None:
                from .fx import annotate_transaction_fx
                annotate_transaction_fx(self)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.txn_type} {self.reference_number} {self.amount} {self.currency}"


# ---------------------------------------------------------------------------
# ReconciliationLink — Smart Reconciliation (Module 5) join table
# ---------------------------------------------------------------------------

class ReconciliationLink(FirmScopedModel):
    """Links related transactions together (invoice ↔ payment ↔ PO ↔ bank txn).

    Each row represents a matched pair/group. Multiple rows can share a
    ``match_group`` UUID to represent an N-way reconciliation.
    """

    class MatchMethod(models.TextChoices):
        MANUAL = "manual", "Manual"
        RULE_BASED = "rule_based", "Rule-Based"
        AI_SUGGESTED = "ai_suggested", "AI-Suggested"

    match_group = models.UUIDField(db_index=True, help_text="Groups related links into one reconciliation set.")
    transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name="reconciliation_links",
    )
    matched_transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name="reverse_reconciliation_links",
    )
    match_confidence = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0.0000"),
        help_text="0.0000–1.0000 confidence score.",
    )
    match_method = models.CharField(max_length=20, choices=MatchMethod.choices, default=MatchMethod.MANUAL)
    settlement_currency = models.CharField(
        max_length=10,
        blank=True,
        default="",
        help_text="Currency in which the settlement leg occurred.",
    )
    settlement_exchange_rate = models.DecimalField(
        max_digits=18,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Settlement-date FX rate from settlement currency into the firm's base currency.",
    )
    original_base_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Original transaction amount converted at the original transaction-time rate.",
    )
    settlement_base_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Settlement leg amount converted at the settlement-time rate.",
    )
    fx_difference = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Realised FX gain/loss locked when the settlement is recorded.",
    )
    settled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the settlement snapshot was captured.",
    )
    matched_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
    )
    notes = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["transaction", "matched_transaction"],
                condition=models.Q(is_deleted=False),
                name="uq_reconciliation_pair",
            ),
        ]
        indexes = [
            models.Index(fields=["firm", "match_group"]),
        ]

    def __str__(self):
        return f"Recon {self.match_group}: txn {self.transaction_id} ↔ {self.matched_transaction_id}"


# ---------------------------------------------------------------------------
# RiskSignal — AI-generated risk indicators
# ---------------------------------------------------------------------------

class RiskSignal(FirmScopedModel):
    """A single risk indicator produced by the Compliance AI or Financial AI layer."""

    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Category(models.TextChoices):
        GST_MISMATCH = "gst_mismatch", "GST Mismatch"
        DUPLICATE_INVOICE = "duplicate_invoice", "Duplicate Invoice"
        UNUSUAL_AMOUNT = "unusual_amount", "Unusual Amount"
        LATE_PAYMENT = "late_payment", "Late Payment"
        VENDOR_RISK = "vendor_risk", "Vendor Risk"
        COMPLIANCE_GAP = "compliance_gap", "Compliance Gap"
        CASH_FLOW_RISK = "cash_flow_risk", "Cash-Flow Risk"
        TRADE_VALUE_MISMATCH = "trade_value_mismatch", "Trade Value Mismatch"
        PAYMENT_BEFORE_SHIPMENT = "payment_before_shipment", "Payment Before Shipment Realization"
        CUSTOM = "custom", "Custom"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        RESOLVED = "resolved", "Resolved"
        FALSE_POSITIVE = "false_positive", "False Positive"

    severity = models.CharField(max_length=10, choices=Severity.choices)
    category = models.CharField(max_length=30, choices=Category.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    title = models.CharField(max_length=255)
    description = models.TextField()
    confidence = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0.0000"),
    )

    # Polymorphic link to the entity that triggered the signal
    entity_type = models.CharField(max_length=40)
    entity_id = models.PositiveIntegerField()

    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True, related_name="risk_signals")
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="risk_signals")

    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    ai_reasoning = models.JSONField(default=dict, blank=True, help_text="Raw AI model output / chain-of-thought.")

    class Meta:
        indexes = [
            # Primary dashboard query: open signals for a firm, ordered by severity
            models.Index(fields=["firm", "status", "severity", "-created_at"], name="idx_risk_dashboard"),
            # Filter by category for drill-downs
            models.Index(fields=["firm", "category", "status"], name="idx_risk_category"),
            # Entity lookup (generic FK pattern)
            models.Index(fields=["entity_type", "entity_id"], name="idx_risk_entity"),
            # Time-series for trend charts
            models.Index(fields=["firm", "created_at"], name="idx_risk_timeline"),
        ]

    def __str__(self):
        return f"[{self.severity}] {self.title} ({self.firm.name})"


# ---------------------------------------------------------------------------
# ReconciliationException — unresolved mismatches queued for human review
# ---------------------------------------------------------------------------

class ReconciliationException(FirmScopedModel):
    """Records a mismatch discovered during automated reconciliation.

    Each row links to the transactions involved and describes the likely
    cause of the discrepancy so a human reviewer can resolve it quickly.
    """

    class MismatchCause(models.TextChoices):
        BANK_CHARGES = "bank_charges", "Bank Charges / Fees"
        DISCOUNT = "discount", "Discount Applied"
        PARTIAL_PAYMENT = "partial_payment", "Partial Payment"
        TAX_DEDUCTION = "tax_deduction", "TDS / Tax Deduction"
        INCORRECT_PAYMENT = "incorrect_payment", "Incorrect Payment Amount"
        DUPLICATE = "duplicate", "Possible Duplicate"
        MISSING_COUNTERPART = "missing_counterpart", "Missing Counterpart"
        DATE_MISMATCH = "date_mismatch", "Date Outside Tolerance"
        VENDOR_MISMATCH = "vendor_mismatch", "Vendor / Party Mismatch"
        CURRENCY_MISMATCH = "currency_mismatch", "Currency Mismatch"
        OTHER = "other", "Other / Unknown"

    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "Pending Review"
        APPROVED = "approved", "Approved (Match Accepted)"
        REJECTED = "rejected", "Rejected (Not a Match)"
        ADJUSTED = "adjusted", "Adjusted Manually"

    # The primary transaction being reconciled
    transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name="recon_exceptions",
    )
    # The candidate it was compared against (nullable for missing-counterpart)
    candidate_transaction = models.ForeignKey(
        Transaction, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="candidate_recon_exceptions",
    )
    match_group = models.UUIDField(
        db_index=True,
        help_text="Links to the ReconciliationLink.match_group this exception belongs to.",
    )

    mismatch_cause = models.CharField(max_length=30, choices=MismatchCause.choices)
    confidence = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0.0000"),
        help_text="Confidence in the diagnosed cause (0–1).",
    )
    reason = models.TextField(help_text="Human-readable explanation of the mismatch.")
    expected_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    actual_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    difference = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    review_status = models.CharField(
        max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.PENDING,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["firm", "review_status", "-created_at"],
                         name="idx_recon_exc_review"),
            models.Index(fields=["firm", "mismatch_cause"],
                         name="idx_recon_exc_cause"),
            models.Index(fields=["match_group"], name="idx_recon_exc_group"),
        ]

    def __str__(self):
        return (
            f"ReconException [{self.mismatch_cause}] "
            f"txn {self.transaction_id} — {self.reason[:60]}"
        )


# ---------------------------------------------------------------------------
# ReconciliationRun — audit trail for each engine invocation
# ---------------------------------------------------------------------------

class ReconciliationRun(FirmScopedModel):
    """Records metadata for each invocation of the reconciliation engine."""

    class RunStatus(models.TextChoices):
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    status = models.CharField(max_length=20, choices=RunStatus.choices, default=RunStatus.RUNNING)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    total_transactions = models.PositiveIntegerField(default=0)
    exact_matches = models.PositiveIntegerField(default=0)
    fuzzy_matches = models.PositiveIntegerField(default=0)
    exceptions_created = models.PositiveIntegerField(default=0)
    unmatched = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True, default="")
    config = models.JSONField(default=dict, blank=True,
                              help_text="Tolerance settings used for this run.")

    class Meta:
        indexes = [
            models.Index(fields=["firm", "-started_at"]),
        ]

    def __str__(self):
        return f"ReconRun {self.id} ({self.firm.name}) — {self.status}"


# ---------------------------------------------------------------------------
# FinancialSnapshot — periodic firm-level financial summary
# ---------------------------------------------------------------------------

class FinancialSnapshot(FirmScopedModel):
    """Point-in-time financial health summary for a firm, computed periodically."""

    class SnapshotType(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

    snapshot_type = models.CharField(max_length=10, choices=SnapshotType.choices)
    snapshot_date = models.DateField()

    total_receivables = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    total_payables = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    net_cash_flow = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    overdue_receivables = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    overdue_payables = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    open_risk_signals = models.PositiveIntegerField(default=0)
    health_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"),
        help_text="0–100 composite score.",
    )

    cashflow_forecast = models.JSONField(default=dict, blank=True, help_text="AI-generated forecast payload.")
    breakdown = models.JSONField(default=dict, blank=True, help_text="Detailed category breakdowns.")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["firm", "snapshot_type", "snapshot_date"],
                condition=models.Q(is_deleted=False),
                name="uq_snapshot_firm_type_date",
            ),
        ]
        indexes = [
            models.Index(fields=["firm", "snapshot_type", "-snapshot_date"]),
        ]

    def __str__(self):
        return f"{self.snapshot_type} snapshot {self.snapshot_date} ({self.firm.name})"


# ---------------------------------------------------------------------------
# VendorScore — composite trust/risk score for a vendor
# ---------------------------------------------------------------------------

class VendorScore(FirmScopedModel):
    """0–100 composite score for a vendor within a firm.

    Sub-metric weights (must sum to 100):
        invoice_consistency  : 20  — regularity and accuracy of invoices
        payment_history      : 25  — how reliably the firm pays this vendor on time
        price_stability      : 15  — variance in unit prices across invoices
        document_quality     : 15  — extraction success rate, validation warnings
        bank_change_frequency: 10  — how often vendor bank details change
        anomaly_history      : 15  — count/severity of risk signals tied to vendor
    """

    vendor = models.OneToOneField(
        Vendor, on_delete=models.CASCADE, related_name="score",
    )

    overall_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"),
        help_text="Composite 0–100 score.",
    )

    # Sub-metric scores (each 0–100, weighted to produce overall_score)
    invoice_consistency = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    payment_history = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    price_stability = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    document_quality = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    bank_change_frequency = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    anomaly_history = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))

    # Detailed breakdown for the audit/explain endpoint
    breakdown = models.JSONField(default=dict, blank=True,
                                 help_text="Per-metric evidence and reasoning.")
    previous_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Score before the last recomputation (for delta display).",
    )
    last_computed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["firm", "-overall_score"], name="idx_vendor_score_rank"),
        ]

    def __str__(self):
        return f"VendorScore {self.vendor.name}: {self.overall_score}"


# ---------------------------------------------------------------------------
# CustomerScore — composite credit/value score for a customer
# ---------------------------------------------------------------------------

class CustomerScore(FirmScopedModel):
    """0–100 composite score for a customer within a firm.

    Sub-metric weights (must sum to 100):
        payment_history        : 30  — on-time vs late payment ratio
        avg_payment_time_trend : 20  — is the customer paying faster or slower?
        credit_exposure        : 25  — outstanding receivables vs credit limit
        revenue_contribution   : 25  — share of firm revenue from this customer
    """

    customer = models.OneToOneField(
        Customer, on_delete=models.CASCADE, related_name="score",
    )

    overall_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"),
        help_text="Composite 0–100 score.",
    )

    # Sub-metric scores (each 0–100)
    payment_history = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    avg_payment_time_trend = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    credit_exposure = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    revenue_contribution = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))

    breakdown = models.JSONField(default=dict, blank=True,
                                 help_text="Per-metric evidence and reasoning.")
    previous_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
    )
    last_computed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["firm", "-overall_score"], name="idx_customer_score_rank"),
        ]

    def __str__(self):
        return f"CustomerScore {self.customer.name}: {self.overall_score}"


# ---------------------------------------------------------------------------
# TradeFinanceLink — connects PO → Invoice → Shipment → Customs → Payment
# ---------------------------------------------------------------------------

class TradeFinanceLink(FirmScopedModel):
    """Links the full lifecycle of a trade-finance deal.

    PurchaseOrder → Invoice → ImportExportRecord (customs/shipment) → Payment.
    All FK fields are nullable so partial chains (e.g. customs doc with no
    matched PO yet) are valid.
    """

    class LinkStatus(models.TextChoices):
        PARTIAL = "partial", "Partial (some legs missing)"
        COMPLETE = "complete", "Complete"
        FLAGGED = "flagged", "Flagged for Review"

    status = models.CharField(
        max_length=20,
        choices=LinkStatus.choices,
        default=LinkStatus.PARTIAL,
    )

    purchase_order_txn = models.ForeignKey(
        Transaction, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="trade_finance_po_links",
        help_text="The Purchase Order transaction.",
    )
    invoice_txn = models.ForeignKey(
        Transaction, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="trade_finance_inv_links",
        help_text="The commercial invoice transaction.",
    )
    trade_doc = models.ForeignKey(
        "trade_docs.ImportExportRecord", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="trade_finance_links",
        help_text="Bill of Entry / Shipping Bill.",
    )
    payment_txn = models.ForeignKey(
        Transaction, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="trade_finance_pay_links",
        help_text="The payment transaction settling this deal.",
    )

    vendor = models.ForeignKey(
        Vendor, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="trade_finance_links",
    )

    invoice_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    invoice_currency = models.CharField(max_length=10, blank=True, default="")
    customs_declared_value = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    customs_currency = models.CharField(max_length=10, blank=True, default="")
    value_difference = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True,
        help_text="invoice_amount − customs_declared_value (same currency).",
    )
    value_difference_pct = models.DecimalField(
        max_digits=7, decimal_places=4, null=True, blank=True,
        help_text="Percentage deviation: abs(diff) / customs_declared_value.",
    )

    expected_shipment_date = models.DateField(null=True, blank=True)
    payment_due_date = models.DateField(null=True, blank=True)
    payment_before_shipment = models.BooleanField(
        default=False,
        help_text="True when payment_due_date < expected_shipment_date.",
    )

    analysis_notes = models.JSONField(default=list, blank=True)
    last_analysed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["firm", "status", "-created_at"], name="idx_tfl_status"),
            models.Index(fields=["firm", "vendor"], name="idx_tfl_vendor"),
        ]

    def __str__(self):
        return f"TradeFinanceLink {self.id} ({self.status}) — {self.firm.name}"
