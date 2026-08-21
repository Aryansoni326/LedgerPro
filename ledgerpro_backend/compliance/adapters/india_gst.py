"""
India GST / E-Invoice compliance adapter.

Migrates all GSTIN-validation, CGST/SGST/IGST extraction, and
tax-consistency logic that was previously inline in invoices/ and
analytics/.
"""
from __future__ import annotations

import re
from typing import Any

from .base import (
    ComplianceAdapter,
    TaxBreakdown,
    TaxConsistencyResult,
    TaxIdValidationResult,
)

GSTIN_REGEX = re.compile(
    r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
)

GSTIN_SCAN_REGEX = re.compile(
    r'[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[A-Z0-9]{1}[Z|A-Z0-9]{1}[A-Z0-9]{1}'
)


def _clean_amount(s: str) -> float:
    return float(s.replace(',', ''))


class IndiaGSTAdapter(ComplianceAdapter):
    """Concrete adapter for Indian GST and E-Invoicing."""

    # ── identity ────────────────────────────────────────────────
    @property
    def jurisdiction_code(self) -> str:
        return 'IN'

    @property
    def jurisdiction_label(self) -> str:
        return 'India (GST / E-Invoice)'

    # ── tax-id validation ───────────────────────────────────────
    def validate_tax_id(self, tax_id: str) -> TaxIdValidationResult:
        normalised = tax_id.strip().upper()
        if not normalised:
            return TaxIdValidationResult(valid=False, error_message='Tax ID is empty.')
        if GSTIN_REGEX.match(normalised):
            return TaxIdValidationResult(valid=True, normalised=normalised)
        return TaxIdValidationResult(
            valid=False,
            normalised=normalised,
            error_message=(
                f"Invalid GSTIN format: '{normalised}'. "
                "Must be a valid 15-character Indian GSTIN (e.g., 27AAAAA1111A1Z1)."
            ),
        )

    @property
    def tax_id_field_name(self) -> str:
        return 'gstin'

    @property
    def tax_id_label(self) -> str:
        return 'GSTIN'

    # ── invoice tax extraction ──────────────────────────────────
    def tax_component_keys(self) -> list[str]:
        return ['cgst', 'sgst', 'igst', 'cess']

    def extract_tax_from_text(self, text: str) -> TaxBreakdown:
        components: dict[str, float] = {}
        for label, key in [('CGST', 'cgst'), ('SGST', 'sgst'), ('IGST', 'igst')]:
            m = re.search(
                rf'{label}\s*@\s*\d+\s*%\s*(?:\(Output\))?\s*([\d,]+\.\d{{2}})',
                text, re.IGNORECASE,
            )
            components[key] = _clean_amount(m.group(1)) if m else 0.0
        cess_match = re.search(r'[Cc]ess\s*(?:@\s*\d+\s*%)?\s*([\d,]+\.\d{2})', text)
        components['cess'] = _clean_amount(cess_match.group(1)) if cess_match else 0.0
        return TaxBreakdown(components=components)

    def build_extraction_prompt_fragment(self, firm_name: str, firm_tax_id: str) -> str:
        return (
            f"The current firm's own name is: '{firm_name}' and own GSTIN is: '{firm_tax_id}'.\n"
            "Return JSON with these tax-specific keys:\n"
            '  "gstin_from": "string (15-character GSTIN of the supplier/seller, or null)",\n'
            '  "gstin_to": "string (15-character GSTIN of the buyer/customer, or null)",\n'
            '  "cgst": number (central tax, default 0.0),\n'
            '  "sgst": number (state tax, default 0.0),\n'
            '  "igst": number (integrated tax, default 0.0),\n'
            '  "cess": number (cess, default 0.0),\n'
            "Confidence sub-keys: gstin_from, gstin_to.\n"
        )

    def build_mock_tax_fields(self, *, is_sale: bool, firm_tax_id: str) -> dict[str, Any]:
        if is_sale:
            return {
                'gstin_from': firm_tax_id or '24ABCDE1234F1Z5',
                'gstin_to': '27AAAAA1111A1Z1',
                'cgst': 90.0, 'sgst': 90.0, 'igst': 0.0, 'cess': 0.0,
            }
        return {
            'gstin_from': '27AAAAA1111A1Z1',
            'gstin_to': firm_tax_id or '24ABCDE1234F1Z5',
            'cgst': 90.0, 'sgst': 90.0, 'igst': 0.0, 'cess': 0.0,
        }

    # ── tax consistency checks ──────────────────────────────────
    def check_tax_consistency(self, parsed: dict[str, Any]) -> TaxConsistencyResult:
        warnings: list[str] = []

        for key in ('gstin_from', 'gstin_to'):
            val = parsed.get(key)
            if val and not GSTIN_REGEX.match(str(val).strip().upper()):
                label = 'supplier (From)' if key == 'gstin_from' else 'buyer (To)'
                warnings.append(f"Invalid {label} GSTIN format: '{val}'.")

        cgst = float(parsed.get('cgst', 0.0) or 0.0)
        sgst = float(parsed.get('sgst', 0.0) or 0.0)
        igst = float(parsed.get('igst', 0.0) or 0.0)

        has_intra = cgst > 0 or sgst > 0
        has_inter = igst > 0
        if has_intra and has_inter:
            intra_valid = cgst > 0 and sgst > 0 and igst == 0
            inter_valid = igst > 0 and cgst == 0 and sgst == 0
            if not (intra_valid or inter_valid):
                warnings.append(
                    "Tax classification warning: conflicting GST structure "
                    "(both CGST/SGST and IGST are populated, or CGST/SGST splits are uneven)."
                )
        return TaxConsistencyResult(consistent=len(warnings) == 0, warnings=warnings)

    # ── analytics helpers ───────────────────────────────────────
    def compute_tax_total(self, raw_data: dict[str, Any]) -> float:
        total = 0.0
        for key in self.tax_component_keys():
            try:
                total += float(raw_data.get(key, 0.0) or 0.0)
            except (ValueError, TypeError):
                pass
        return total

    def net_tax_liability_label(self) -> str:
        return 'net_gst_liability'

    # ── invoice-party identification ────────────────────────────
    def extract_party_tax_ids(self, text: str) -> tuple[str | None, str | None]:
        gstins = GSTIN_SCAN_REGEX.findall(text.upper())
        unique: list[str] = []
        for g in gstins:
            if g not in unique:
                unique.append(g)
        return (
            unique[0] if len(unique) > 0 else None,
            unique[1] if len(unique) > 1 else None,
        )

    def seller_tax_id_key(self) -> str:
        return 'gstin_from'

    def buyer_tax_id_key(self) -> str:
        return 'gstin_to'

    # ── export column mapping ───────────────────────────────────
    def export_column_map(self) -> dict[str, str]:
        return {
            'gstin_from': 'Seller GSTIN',
            'gstin_to': 'Buyer GSTIN',
            'cgst': 'CGST',
            'sgst': 'SGST',
            'igst': 'IGST',
            'cess': 'Cess',
        }
