"""
Server-side entitlements + concurrent-safe usage metering.

All feature gates and quota checks for document volume, organizations,
AI agent access, and API access go through this module — never trust the UI.
"""
from __future__ import annotations

import logging
import time

from django.db import OperationalError, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.response import Response

from billing.exceptions import BillingError, FeatureNotAvailable, QuotaExceeded
from billing.models import Subscription, UsagePeriod, current_period_end, current_period_start
from billing.tiers import TIER_FREE, TIER_LIMITS
from firms.models import Firm

logger = logging.getLogger(__name__)


def get_or_create_subscription(user) -> Subscription:
    sub, _ = Subscription.objects.get_or_create(
        user=user,
        defaults={
            "tier": TIER_FREE,
            "status": Subscription.Status.ACTIVE,
            "current_period_start": current_period_start(),
            "current_period_end": current_period_end(),
        },
    )
    return sub


def billing_user_for_firm(firm) -> object:
    """Quotas attach to the accountant/billing account that owns the firm."""
    return firm.created_by


def _ensure_period(subscription: Subscription) -> None:
    """Roll calendar-month window if we crossed into a new month."""
    today = timezone.now().date()
    if subscription.current_period_end <= today:
        subscription.current_period_start = current_period_start(today)
        subscription.current_period_end = current_period_end(today)
        subscription.save(update_fields=["current_period_start", "current_period_end", "updated_at"])


def get_or_create_usage_period(subscription: Subscription) -> UsagePeriod:
    _ensure_period(subscription)
    period, _ = UsagePeriod.objects.get_or_create(
        subscription=subscription,
        period_start=subscription.current_period_start,
        defaults={"period_end": subscription.current_period_end},
    )
    return period


def organization_count(user) -> int:
    return Firm.objects.filter(created_by=user).count()


def assert_can_create_organization(user) -> Subscription:
    sub = get_or_create_subscription(user)
    limits = sub.effective_limits()
    if limits.max_organizations is None:
        return sub
    used = organization_count(user)
    if used >= limits.max_organizations:
        raise QuotaExceeded(
            f"Organization limit reached for {limits.display_name} "
            f"({used}/{limits.max_organizations}). Upgrade to add more firms.",
            code="organization_quota_exceeded",
            details={
                "used": used,
                "limit": limits.max_organizations,
                "tier": sub.tier,
            },
        )
    return sub


def assert_feature(user, feature: str) -> Subscription:
    """feature: 'ai_agent_access' | 'api_access'"""
    sub = get_or_create_subscription(user)
    limits = sub.effective_limits()
    allowed = getattr(limits, feature, False)
    if not allowed:
        raise FeatureNotAvailable(
            f"{feature} is not included in the {limits.display_name} plan.",
            code=f"{feature}_required",
            details={"tier": sub.tier, "feature": feature},
        )
    return sub


def _reserve_counter(
    *,
    subscription: Subscription,
    field: str,
    amount: int,
    limit: int | None,
    quota_code: str,
    label: str,
) -> UsagePeriod:
    """
    Atomically increment a usage counter.

    Conditional ``UPDATE … WHERE count <= limit - n`` prevents overshoot under
    concurrency. Retries on SQLite ``database is locked``.
    """
    if amount < 1:
        raise ValueError("amount must be >= 1")

    last_exc: Exception | None = None
    for attempt in range(16):
        try:
            with transaction.atomic():
                _ensure_period(subscription)
                period, _ = UsagePeriod.objects.select_for_update().get_or_create(
                    subscription=subscription,
                    period_start=subscription.current_period_start,
                    defaults={"period_end": subscription.current_period_end},
                )

                qs = UsagePeriod.objects.filter(pk=period.pk)
                if limit is not None:
                    qs = qs.filter(**{f"{field}__lte": limit - amount})

                updated = qs.update(**{field: F(field) + amount})
                if updated != 1:
                    period.refresh_from_db(fields=[field])
                    current = getattr(period, field)
                    raise QuotaExceeded(
                        f"{label} quota exceeded for this billing period "
                        f"({current}/{limit}).",
                        code=quota_code,
                        details={
                            "used": current,
                            "limit": limit,
                            "requested": amount,
                            "tier": subscription.tier,
                            "period_start": str(period.period_start),
                        },
                    )

                period.refresh_from_db(fields=[field, "updated_at"])
                return period
        except OperationalError as exc:
            last_exc = exc
            if "locked" not in str(exc).lower():
                raise
            time.sleep(0.02 * (attempt + 1))
            continue

    assert last_exc is not None
    raise last_exc


def reserve_documents(user, amount: int = 1) -> UsagePeriod:
    sub = get_or_create_subscription(user)
    limit = sub.effective_limits().max_documents_per_month
    return _reserve_counter(
        subscription=sub,
        field="documents_count",
        amount=amount,
        limit=limit,
        quota_code="document_quota_exceeded",
        label="Document",
    )


def reserve_ai_queries(user, amount: int = 1) -> UsagePeriod:
    sub = assert_feature(user, "ai_agent_access")
    limit = sub.effective_limits().max_ai_queries_per_month
    return _reserve_counter(
        subscription=sub,
        field="ai_queries_count",
        amount=amount,
        limit=limit,
        quota_code="ai_query_quota_exceeded",
        label="AI query",
    )


def reserve_documents_for_firm(firm, amount: int = 1) -> UsagePeriod:
    return reserve_documents(billing_user_for_firm(firm), amount)


def reserve_ai_queries_for_firm(firm, amount: int = 1) -> UsagePeriod:
    return reserve_ai_queries(billing_user_for_firm(firm), amount)


def billing_error_response(exc: BillingError) -> Response:
    return Response(exc.as_response_data(), status=exc.http_status)


def usage_snapshot(user) -> dict:
    sub = get_or_create_subscription(user)
    period = get_or_create_usage_period(sub)
    limits = sub.effective_limits()
    return {
        "subscription": sub.features_dict(),
        "period": {
            "start": str(period.period_start),
            "end": str(period.period_end),
        },
        "usage": {
            "documents_count": period.documents_count,
            "ai_queries_count": period.ai_queries_count,
            "organizations_count": organization_count(user),
        },
        "limits": limits.to_dict(),
        "tier_catalog": {k: v.to_dict() for k, v in TIER_LIMITS.items()},
    }
