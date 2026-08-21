"""
Billing / subscription feature-gating and concurrent usage metering tests.
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest import skipUnless

from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import User
from billing.entitlements import (
    assert_can_create_organization,
    assert_feature,
    get_or_create_subscription,
    reserve_ai_queries,
    reserve_documents,
)
from billing.exceptions import FeatureNotAvailable, QuotaExceeded
from billing.models import UsagePeriod
from billing.tiers import TIER_ENTERPRISE, TIER_FREE, TIER_GROWTH, TIER_PROFESSIONAL, TIER_STARTER
from firms.models import Firm


@override_settings(USE_SQLITE=True)
class SubscriptionTierTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="bill@test.com", email="bill@test.com", password="x",
        )
        self.sub = get_or_create_subscription(self.user)

    def test_new_user_gets_free_tier(self):
        self.assertEqual(self.sub.tier, TIER_FREE)
        self.assertFalse(self.sub.effective_limits().ai_agent_access)
        self.assertFalse(self.sub.effective_limits().api_access)

    def test_growth_enables_agent_not_api(self):
        self.sub.tier = TIER_GROWTH
        self.sub.save()
        limits = self.sub.effective_limits()
        self.assertTrue(limits.ai_agent_access)
        self.assertFalse(limits.api_access)

    def test_professional_enables_api(self):
        self.sub.tier = TIER_PROFESSIONAL
        self.sub.save()
        limits = self.sub.effective_limits()
        self.assertTrue(limits.api_access)
        self.assertIsNone(limits.max_documents_per_month)

    def test_enterprise_custom_config_without_migration(self):
        self.sub.tier = TIER_ENTERPRISE
        self.sub.custom_config = {
            "max_organizations": 42,
            "max_documents_per_month": 1000,
            "features": {"sso": True, "dedicated_slack_channel": "#ledgerpro-acme"},
        }
        self.sub.save()
        limits = self.sub.effective_limits()
        self.assertEqual(limits.max_organizations, 42)
        self.assertEqual(limits.max_documents_per_month, 1000)
        feats = self.sub.features_dict()["custom_features"]
        self.assertTrue(feats["sso"])
        self.assertEqual(feats["dedicated_slack_channel"], "#ledgerpro-acme")

    def test_organization_quota_enforced(self):
        self.sub.tier = TIER_STARTER
        self.sub.save()
        for i in range(3):
            Firm.objects.create(
                name=f"Firm {i}",
                state="KA",
                city="BLR",
                owner_email=f"o{i}@t.com",
                created_by=self.user,
                status="active",
            )
        with self.assertRaises(QuotaExceeded):
            assert_can_create_organization(self.user)

    def test_ai_feature_gate(self):
        with self.assertRaises(FeatureNotAvailable):
            assert_feature(self.user, "ai_agent_access")
        self.sub.tier = TIER_GROWTH
        self.sub.save()
        assert_feature(self.user, "ai_agent_access")


@override_settings(USE_SQLITE=True)
class BillingAPIGateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="api@test.com", email="api@test.com", password="x",
        )
        self.client.force_authenticate(user=self.user)
        self.sub = get_or_create_subscription(self.user)

    def test_external_api_blocked_on_free(self):
        resp = self.client.get("/api/external/v1/me/")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], "api_access_required")

    def test_external_api_allowed_on_professional(self):
        self.sub.tier = TIER_PROFESSIONAL
        self.sub.save()
        resp = self.client.get("/api/external/v1/me/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["api_access"])

    def test_subscription_endpoint(self):
        resp = self.client.get("/api/billing/subscription/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["subscription"]["tier"], TIER_FREE)
        self.assertIn("documents_count", body["usage"])


@override_settings(USE_SQLITE=True)
class ConcurrentMeteringTests(TransactionTestCase):
    """Usage counters stay accurate under concurrent reserve() calls."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="race@test.com", email="race@test.com", password="x",
        )
        self.sub = get_or_create_subscription(self.user)
        self.sub.tier = TIER_STARTER
        self.sub.save()
        # Starter docs limit = 500; use a tight custom path via free tier for race
        self.sub.tier = TIER_FREE
        self.sub.save()  # 25 docs

    def test_document_quota_hard_stop(self):
        for _ in range(25):
            reserve_documents(self.user, amount=1)
        with self.assertRaises(QuotaExceeded):
            reserve_documents(self.user, amount=1)
        period = UsagePeriod.objects.get(
            subscription=self.sub,
            period_start=self.sub.current_period_start,
        )
        self.assertEqual(period.documents_count, 25)

    @skipUnless(connection.vendor == "postgresql", "Concurrent writers need Postgres; SQLite serializes/locks")
    def test_document_reserves_never_exceed_limit(self):
        limit = 25
        successes: list[int] = []
        errors: list[int] = []
        lock = threading.Lock()

        def worker(_i):
            connection.close()
            try:
                reserve_documents(self.user, amount=1)
                with lock:
                    successes.append(1)
            except QuotaExceeded:
                with lock:
                    errors.append(1)
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(worker, i) for i in range(40)]
            for f in as_completed(futures):
                f.result()

        period = UsagePeriod.objects.get(
            subscription=self.sub,
            period_start=self.sub.current_period_start,
        )
        self.assertEqual(period.documents_count, limit)
        self.assertEqual(sum(successes), limit)
        self.assertEqual(sum(errors), 40 - limit)

    def test_ai_query_meter_with_feature(self):
        self.sub.tier = TIER_GROWTH
        self.sub.save()
        # Growth max_ai = 500 — reserve a few
        for _ in range(5):
            reserve_ai_queries(self.user, amount=1)
        period = UsagePeriod.objects.get(
            subscription=self.sub,
            period_start=self.sub.current_period_start,
        )
        self.assertEqual(period.ai_queries_count, 5)
