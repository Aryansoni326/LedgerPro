"""
US Sales Tax / 1099 stub adapter.

Demonstrates that a second jurisdiction can be added with zero changes
to core financial logic.  Replace NotImplementedError bodies with real
logic when US support ships.
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

EIN_REGEX = re.compile(r'^\d{2}-?\d{7}$')


class USSalesTaxAdapter(ComplianceAdapter):
    """Stub adapter for US Sales Tax and 1099 reporting."""

    @property
    def jurisdiction_code(self) -> str:
        return 'US'

    @property
    def jurisdiction_label(self) -> str:
        return 'United States (Sales Tax / 1099)'

    def validate_tax_id(self, tax_id: str) -> TaxIdValidationResult:
        normalised = tax_id.strip().replace('-', '')
        if EIN_REGEX.match(tax_id.strip()):
            return TaxIdValidationResult(valid=True, normalised=normalised)
        return TaxIdValidationResult(
            valid=False, normalised=normalised,
            error_message=f"Invalid EIN format: '{tax_id}'. Expected XX-XXXXXXX.",
        )

    @property
    def tax_id_field_name(self) -> str:
        return 'ein'

    @property
    def tax_id_label(self) -> str:
        return 'EIN'

    def tax_component_keys(self) -> list[str]:
        return ['sales_tax', 'use_tax']

    def extract_tax_from_text(self, text: str) -> TaxBreakdown:
        return TaxBreakdown(components={'sales_tax': 0.0, 'use_tax': 0.0})

    def build_extraction_prompt_fragment(self, firm_name: str, firm_tax_id: str) -> str:
        return (
            f"The firm is '{firm_name}' with EIN '{firm_tax_id}'.\n"
            "Return JSON with:\n"
            '  "ein_from": "string (seller EIN, or null)",\n'
            '  "ein_to": "string (buyer EIN, or null)",\n'
            '  "sales_tax": number (default 0.0),\n'
        )

    def build_mock_tax_fields(self, *, is_sale: bool, firm_tax_id: str) -> dict[str, Any]:
        return {'ein_from': '12-3456789', 'ein_to': '98-7654321', 'sales_tax': 50.0, 'use_tax': 0.0}

    def check_tax_consistency(self, parsed: dict[str, Any]) -> TaxConsistencyResult:
        return TaxConsistencyResult(consistent=True)

    def compute_tax_total(self, raw_data: dict[str, Any]) -> float:
        return sum(float(raw_data.get(k, 0) or 0) for k in self.tax_component_keys())

    def net_tax_liability_label(self) -> str:
        return 'net_sales_tax_liability'

    def extract_party_tax_ids(self, text: str) -> tuple[str | None, str | None]:
        eins = re.findall(r'\d{2}-\d{7}', text)
        unique = list(dict.fromkeys(eins))
        return (unique[0] if unique else None, unique[1] if len(unique) > 1 else None)

    def seller_tax_id_key(self) -> str:
        return 'ein_from'

    def buyer_tax_id_key(self) -> str:
        return 'ein_to'

    def export_column_map(self) -> dict[str, str]:
        return {'ein_from': 'Seller EIN', 'ein_to': 'Buyer EIN', 'sales_tax': 'Sales Tax', 'use_tax': 'Use Tax'}
