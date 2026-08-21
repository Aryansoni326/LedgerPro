"""
Canonical subscription tier catalog.

Limits here are the product defaults. Enterprise customers override via
``Subscription.custom_config`` (JSON) — no per-customer schema migrations.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# Sentinel: None means unlimited
UNLIMITED = None


@dataclass(frozen=True)
class TierLimits:
    max_organizations: int | None
    max_documents_per_month: int | None
    max_ai_queries_per_month: int | None
    ai_agent_access: bool
    api_access: bool
    display_name: str
    # List price INR / month (marketing; billing provider may differ)
    list_price_inr: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


TIER_FREE = "free"
TIER_STARTER = "starter"
TIER_GROWTH = "growth"
TIER_PROFESSIONAL = "professional"
TIER_ENTERPRISE = "enterprise"

TIER_CHOICES = (
    (TIER_FREE, "Free"),
    (TIER_STARTER, "Starter"),
    (TIER_GROWTH, "Growth"),
    (TIER_PROFESSIONAL, "Professional"),
    (TIER_ENTERPRISE, "Enterprise"),
)

TIER_LIMITS: dict[str, TierLimits] = {
    TIER_FREE: TierLimits(
        max_organizations=1,
        max_documents_per_month=25,
        max_ai_queries_per_month=10,
        ai_agent_access=False,
        api_access=False,
        display_name="Free",
        list_price_inr=0,
    ),
    TIER_STARTER: TierLimits(
        max_organizations=3,
        max_documents_per_month=500,
        max_ai_queries_per_month=50,
        ai_agent_access=False,
        api_access=False,
        display_name="Starter",
        list_price_inr=2499,
    ),
    TIER_GROWTH: TierLimits(
        max_organizations=8,
        max_documents_per_month=2000,
        max_ai_queries_per_month=500,
        ai_agent_access=True,
        api_access=False,
        display_name="Growth",
        list_price_inr=4999,
    ),
    TIER_PROFESSIONAL: TierLimits(
        max_organizations=15,
        max_documents_per_month=UNLIMITED,
        max_ai_queries_per_month=5000,
        ai_agent_access=True,
        api_access=True,
        display_name="Professional",
        list_price_inr=7499,
    ),
    TIER_ENTERPRISE: TierLimits(
        max_organizations=UNLIMITED,
        max_documents_per_month=UNLIMITED,
        max_ai_queries_per_month=UNLIMITED,
        ai_agent_access=True,
        api_access=True,
        display_name="Enterprise",
        list_price_inr=18999,
    ),
}

# Keys allowed in Subscription.custom_config (Enterprise). Unknown keys are ignored.
CUSTOM_CONFIG_KEYS = frozenset({
    "max_organizations",
    "max_documents_per_month",
    "max_ai_queries_per_month",
    "ai_agent_access",
    "api_access",
    "features",  # free-form feature flags dict — no schema migration
})
