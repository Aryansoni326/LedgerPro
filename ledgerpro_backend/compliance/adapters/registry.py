"""
Adapter registry — maps jurisdiction codes to adapter instances.

Core financial logic calls ``get_adapter_for_firm(firm)`` and receives
the correct ComplianceAdapter without knowing the jurisdiction.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .base import ComplianceAdapter
from .india_gst import IndiaGSTAdapter
from .us_salestax import USSalesTaxAdapter

if TYPE_CHECKING:
    from firms.models import Firm

_ADAPTERS: dict[str, ComplianceAdapter] = {
    'IN': IndiaGSTAdapter(),
    'US': USSalesTaxAdapter(),
}

DEFAULT_JURISDICTION = 'IN'


def get_adapter(jurisdiction_code: str) -> ComplianceAdapter:
    """Return the adapter for a given jurisdiction code, falling back to default."""
    code = (jurisdiction_code or DEFAULT_JURISDICTION).upper()
    adapter = _ADAPTERS.get(code)
    if adapter is None:
        raise ValueError(
            f"No compliance adapter registered for jurisdiction '{code}'. "
            f"Available: {', '.join(sorted(_ADAPTERS))}."
        )
    return adapter


def get_adapter_for_firm(firm: Firm) -> ComplianceAdapter:
    """Return the adapter matching the firm's jurisdiction setting."""
    code = getattr(firm, 'jurisdiction', None) or DEFAULT_JURISDICTION
    return get_adapter(code)


def registered_jurisdictions() -> list[tuple[str, str]]:
    """Return list of (code, label) for all registered adapters — used for model choices."""
    return [(a.jurisdiction_code, a.jurisdiction_label) for a in _ADAPTERS.values()]
