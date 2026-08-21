"""
Usage-based SaaS billing: Subscription + metered UsagePeriod.

Subscription belongs to the billing account (User). Firm/organization quotas
and document/AI meters are enforced against the firm creator's subscription.
"""
from __future__ import annotations

from datetime import date

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db import models
from django.utils import timezone

from billing.tiers import (
    CUSTOM_CONFIG_KEYS,
    TIER_CHOICES,
    TIER_ENTERPRISE,
    TIER_FREE,
    TIER_LIMITS,
    TierLimits,
)


def current_period_start(as_of: date | None = None) -> date:
    """Billing periods are calendar months (UTC date)."""
    d = as_of or timezone.now().date()
    return d.replace(day=1)


def current_period_end(as_of: date | None = None) -> date:
    start = current_period_start(as_of)
    return start + relativedelta(months=1)


class Subscription(models.Model):
    class Status(models.TextChoices):
        TRIALING = "trialing", "Trialing"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past Due"
        CANCELED = "canceled", "Canceled"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    tier = models.CharField(max_length=32, choices=TIER_CHOICES, default=TIER_FREE, db_index=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True,
    )
    # Enterprise (and rare overrides): merge onto tier defaults without migrations.
    # Example: {"max_organizations": 200, "features": {"sso": true, "dedicated_vpc": true}}
    custom_config = models.JSONField(default=dict, blank=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    current_period_start = models.DateField(default=current_period_start)
    current_period_end = models.DateField(default=current_period_end)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["tier", "status"]),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.tier}({self.status})"

    def effective_limits(self) -> TierLimits:
        base = TIER_LIMITS.get(self.tier, TIER_LIMITS[TIER_FREE])
        if self.tier != TIER_ENTERPRISE or not self.custom_config:
            return base

        cfg = {k: v for k, v in self.custom_config.items() if k in CUSTOM_CONFIG_KEYS}
        return TierLimits(
            max_organizations=cfg.get("max_organizations", base.max_organizations),
            max_documents_per_month=cfg.get(
                "max_documents_per_month", base.max_documents_per_month,
            ),
            max_ai_queries_per_month=cfg.get(
                "max_ai_queries_per_month", base.max_ai_queries_per_month,
            ),
            ai_agent_access=bool(cfg.get("ai_agent_access", base.ai_agent_access)),
            api_access=bool(cfg.get("api_access", base.api_access)),
            display_name=base.display_name,
            list_price_inr=base.list_price_inr,
        )

    def features_dict(self) -> dict:
        limits = self.effective_limits()
        extra = {}
        if self.tier == TIER_ENTERPRISE:
            extra = dict(self.custom_config.get("features") or {})
        return {
            "tier": self.tier,
            "status": self.status,
            "max_organizations": limits.max_organizations,
            "max_documents_per_month": limits.max_documents_per_month,
            "max_ai_queries_per_month": limits.max_ai_queries_per_month,
            "ai_agent_access": limits.ai_agent_access,
            "api_access": limits.api_access,
            "custom_features": extra,
        }


class UsagePeriod(models.Model):
    """
    Metered usage for one subscription billing period.

    Counters are updated with ``F()`` + ``select_for_update`` so concurrent
    uploads/queries cannot under-count or bypass quotas.
    """

    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="usage_periods",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    documents_count = models.PositiveIntegerField(default=0)
    ai_queries_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["subscription", "period_start"],
                name="uq_usage_subscription_period",
            ),
        ]
        indexes = [
            models.Index(fields=["subscription", "period_start"]),
        ]

    def __str__(self):
        return (
            f"sub={self.subscription_id} {self.period_start} "
            f"docs={self.documents_count} ai={self.ai_queries_count}"
        )
