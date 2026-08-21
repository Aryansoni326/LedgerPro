"""
Billing & external API endpoints.

Feature flags (ai_agent, api_access, quotas) are enforced here and at
mutation endpoints — never only in the frontend.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from billing.entitlements import (
    assert_feature,
    billing_error_response,
    get_or_create_subscription,
    usage_snapshot,
)
from billing.exceptions import BillingError
from billing.tiers import CUSTOM_CONFIG_KEYS, TIER_CHOICES, TIER_ENTERPRISE, TIER_LIMITS


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_subscription(request):
    """GET /api/billing/subscription/ — current plan + usage + limits."""
    return Response(usage_snapshot(request.user), status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def tier_catalog(request):
    """GET /api/billing/tiers/ — catalog of plan feature flags."""
    return Response(
        {
            "tiers": [
                {"id": key, "label": label, **TIER_LIMITS[key].to_dict()}
                for key, label in TIER_CHOICES
            ],
        },
        status=status.HTTP_200_OK,
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_update_subscription(request, user_id: int):
    """
    Staff-only: set tier / Enterprise custom_config without a schema migration.

    Body example::

        {
          "tier": "enterprise",
          "custom_config": {
            "max_organizations": 250,
            "features": {"sso": true, "dedicated_slack": true}
          }
        }
    """
    from accounts.models import User

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    sub = get_or_create_subscription(user)
    tier = request.data.get("tier")
    if tier:
        if tier not in dict(TIER_CHOICES):
            return Response(
                {"error": f"Invalid tier. Choose from {list(dict(TIER_CHOICES))}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        sub.tier = tier

    if "status" in request.data:
        sub.status = request.data["status"]

    if "custom_config" in request.data:
        target_tier = tier or sub.tier
        if target_tier != TIER_ENTERPRISE:
            return Response(
                {"error": "custom_config is only supported on Enterprise."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        raw = request.data.get("custom_config") or {}
        if not isinstance(raw, dict):
            return Response(
                {"error": "custom_config must be an object."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cleaned = {k: v for k, v in raw.items() if k in CUSTOM_CONFIG_KEYS}
        sub.custom_config = cleaned
        sub.tier = TIER_ENTERPRISE

    sub.save()
    return Response(usage_snapshot(user), status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def external_api_bootstrap(request):
    """
    GET /api/external/v1/me/

    Programmatic API entrypoint — gated by ``api_access`` feature flag.
    """
    try:
        assert_feature(request.user, "api_access")
    except BillingError as exc:
        return billing_error_response(exc)

    sub = get_or_create_subscription(request.user)
    return Response(
        {
            "api_access": True,
            "tier": sub.tier,
            "features": sub.features_dict(),
            "message": "External API access granted for this billing account.",
        },
        status=status.HTTP_200_OK,
    )
