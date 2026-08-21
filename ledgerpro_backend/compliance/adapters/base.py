"""
Abstract base for jurisdiction-specific compliance adapters.

Every adapter implements a uniform interface so core financial logic
(invoice extraction, analytics, scoring) never contains jurisdiction-
specific branching.  Adding a new jurisdiction means dropping a new
file in compliance/adapters/ and registering it — zero changes to
invoices/, analytics/, or intelligence/.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaxIdValidationResult:
    """Outcome of validating a single tax-identification number."""
    valid: bool
    normalised: str = ''
    error_message: str = ''


@dataclass
class TaxBreakdown:
    """Jurisdiction-neutral container for tax line items."""
    components: dict[str, float] = field(default_factory=dict)

    @property
    def total(self) -> float:
        return sum(self.components.values())


@dataclass
class TaxConsistencyResult:
    """Outcome of checking whether tax components are internally consistent."""
    consistent: bool = True
    warnings: list[str] = field(default_factory=list)


class ComplianceAdapter(ABC):
    """Interface that every jurisdiction adapter must implement."""

    # ── identity ────────────────────────────────────────────────
    @property
    @abstractmethod
    def jurisdiction_code(self) -> str:
        """ISO-style short code, e.g. 'IN', 'US', 'EU'."""

    @property
    @abstractmethod
    def jurisdiction_label(self) -> str:
        """Human-readable label, e.g. 'India (GST)'."""

    # ── tax-id validation ───────────────────────────────────────
    @abstractmethod
    def validate_tax_id(self, tax_id: str) -> TaxIdValidationResult:
        """Validate and normalise a tax-identification number (GSTIN / EIN / VAT)."""

    @property
    @abstractmethod
    def tax_id_field_name(self) -> str:
        """Model-level field name for the firm's tax ID, e.g. 'gstin'."""

    @property
    @abstractmethod
    def tax_id_label(self) -> str:
        """User-facing label for the tax ID, e.g. 'GSTIN', 'EIN', 'VAT Number'."""

    # ── invoice tax extraction ──────────────────────────────────
    @abstractmethod
    def tax_component_keys(self) -> list[str]:
        """Ordered list of tax-component keys this jurisdiction uses
        (e.g. ['cgst', 'sgst', 'igst', 'cess'] for India)."""

    @abstractmethod
    def extract_tax_from_text(self, text: str) -> TaxBreakdown:
        """Regex-based extraction of tax line items from raw OCR text."""

    @abstractmethod
    def build_extraction_prompt_fragment(self, firm_name: str, firm_tax_id: str) -> str:
        """Return the jurisdiction-specific portion of the LLM extraction prompt."""

    @abstractmethod
    def build_mock_tax_fields(self, *, is_sale: bool, firm_tax_id: str) -> dict[str, Any]:
        """Return mock tax data for development/testing."""

    # ── tax consistency checks ──────────────────────────────────
    @abstractmethod
    def check_tax_consistency(self, parsed: dict[str, Any]) -> TaxConsistencyResult:
        """Validate that parsed tax components are internally consistent
        (e.g. CGST/SGST vs IGST mutual exclusion)."""

    # ── analytics helpers ───────────────────────────────────────
    @abstractmethod
    def compute_tax_total(self, raw_data: dict[str, Any]) -> float:
        """Sum all tax components from a bill's raw_data dict."""

    @abstractmethod
    def net_tax_liability_label(self) -> str:
        """Label for the net liability metric, e.g. 'net_gst_liability'."""

    # ── invoice-party identification ────────────────────────────
    @abstractmethod
    def extract_party_tax_ids(self, text: str) -> tuple[str | None, str | None]:
        """Extract (seller_tax_id, buyer_tax_id) from raw text."""

    @abstractmethod
    def seller_tax_id_key(self) -> str:
        """JSON key for seller's tax ID in parsed data, e.g. 'gstin_from'."""

    @abstractmethod
    def buyer_tax_id_key(self) -> str:
        """JSON key for buyer's tax ID in parsed data, e.g. 'gstin_to'."""

    # ── export column mapping ───────────────────────────────────
    @abstractmethod
    def export_column_map(self) -> dict[str, str]:
        """Map from internal raw_data keys to user-facing export column headers.
        Example: {'gstin_from': 'Seller GSTIN', 'cgst': 'CGST', ...}"""
