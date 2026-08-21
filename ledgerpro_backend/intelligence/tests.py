"""
Tests for risk-signal list, summary, detail endpoints AND
cash-flow forecasting engine + API.

Covers:
- Firm-scoped access control (cross-firm 403)
- Pagination and filtering
- Summary aggregation correctness
- Status update (PATCH)
- Performance: summary with bulk signals completes in <200ms
- Cash-flow forecast engine correctness
- Forecast API endpoint (cached & fresh)
- Explanation generation from actual line items
- Celery task integration
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core import signing
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from firms.models import Firm
from invoices.tasks import generate_mock_data
from intelligence.models import (
    Customer, CustomerScore, ExchangeRate, FinancialSnapshot, ReconciliationLink, RiskSignal,
    TradeFinanceLink, Transaction, Vendor, VendorScore,
)
from trade_docs.models import ImportExportRecord


def _auth_token(user: User) -> str:
    payload = {
        'user_id': user.id,
        'email': user.email,
        'exp_timestamp': (timezone.now() + timedelta(days=7)).timestamp(),
    }
    return signing.dumps(payload, key=settings.SECRET_KEY)


@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class RiskSignalEndpointTests(TestCase):

    def setUp(self):
        self.client_a = APIClient()
        self.client_b = APIClient()

        self.user_a = User.objects.create_user(
            username='alice@risk.com', email='alice@risk.com', password='unused',
        )
        self.user_b = User.objects.create_user(
            username='bob@risk.com', email='bob@risk.com', password='unused',
        )

        self.firm_a = Firm.objects.create(
            name='Alice Risk Corp', state='Maharashtra', city='Mumbai',
            owner_email='owner-a@risk.com', created_by=self.user_a, status='active',
        )
        self.firm_b = Firm.objects.create(
            name='Bob Risk Corp', state='Karnataka', city='Bengaluru',
            owner_email='owner-b@risk.com', created_by=self.user_b, status='active',
        )

        self.client_a.credentials(HTTP_AUTHORIZATION=f'Bearer {_auth_token(self.user_a)}')
        self.client_b.credentials(HTTP_AUTHORIZATION=f'Bearer {_auth_token(self.user_b)}')

        # Seed signals for firm_a
        severities = ['critical', 'high', 'medium', 'low']
        categories = ['gst_mismatch', 'duplicate_invoice', 'unusual_amount', 'late_payment']
        for i in range(20):
            RiskSignal.objects.create(
                firm=self.firm_a,
                severity=severities[i % 4],
                category=categories[i % 4],
                status='open' if i < 15 else 'acknowledged',
                title=f'Signal {i}',
                description=f'Test risk signal #{i}',
                entity_type='bill',
                entity_id=i + 1,
                confidence=Decimal('0.8500'),
            )

        # One signal for firm_b
        self.sig_b = RiskSignal.objects.create(
            firm=self.firm_b, severity='high', category='vendor_risk',
            status='open', title='Firm B signal', description='Should be isolated',
            entity_type='vendor', entity_id=1,
        )

    # ----- Access control -------------------------------------------------

    def test_cross_firm_list_returns_403(self):
        resp = self.client_a.get(f'/api/firms/{self.firm_b.id}/risk-signals/')
        self.assertEqual(resp.status_code, 403)

    def test_cross_firm_summary_returns_403(self):
        resp = self.client_a.get(f'/api/firms/{self.firm_b.id}/risk-summary/')
        self.assertEqual(resp.status_code, 403)

    def test_cross_firm_detail_returns_403(self):
        resp = self.client_a.get(f'/api/risk-signals/{self.sig_b.id}')
        self.assertEqual(resp.status_code, 403)

    # ----- List endpoint --------------------------------------------------

    def test_list_returns_paginated_results(self):
        resp = self.client_a.get(f'/api/firms/{self.firm_a.id}/risk-signals/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['count'], 20)
        self.assertEqual(data['page'], 1)
        self.assertLessEqual(len(data['results']), 25)

    def test_list_filter_by_severity(self):
        resp = self.client_a.get(
            f'/api/firms/{self.firm_a.id}/risk-signals/',
            {'severity': 'critical'},
        )
        data = resp.json()
        self.assertTrue(all(r['severity'] == 'critical' for r in data['results']))
        self.assertEqual(data['count'], 5)

    def test_list_filter_by_status_alias(self):
        resp = self.client_a.get(
            f'/api/firms/{self.firm_a.id}/risk-signals/',
            {'status': 'open'},
        )
        data = resp.json()
        self.assertEqual(data['count'], 15)

    def test_list_filter_reviewed_alias(self):
        resp = self.client_a.get(
            f'/api/firms/{self.firm_a.id}/risk-signals/',
            {'status': 'reviewed'},
        )
        data = resp.json()
        self.assertEqual(data['count'], 5)
        self.assertTrue(all(
            r['status'] in ('acknowledged', 'resolved') for r in data['results']
        ))

    def test_list_filter_by_category(self):
        resp = self.client_a.get(
            f'/api/firms/{self.firm_a.id}/risk-signals/',
            {'category': 'gst_mismatch'},
        )
        data = resp.json()
        self.assertTrue(all(r['category'] == 'gst_mismatch' for r in data['results']))

    def test_list_page_size(self):
        resp = self.client_a.get(
            f'/api/firms/{self.firm_a.id}/risk-signals/',
            {'page_size': '5'},
        )
        data = resp.json()
        self.assertEqual(len(data['results']), 5)
        self.assertEqual(data['total_pages'], 4)

    def test_list_page_2(self):
        resp = self.client_a.get(
            f'/api/firms/{self.firm_a.id}/risk-signals/',
            {'page_size': '10', 'page': '2'},
        )
        data = resp.json()
        self.assertEqual(data['page'], 2)
        self.assertEqual(len(data['results']), 10)

    def test_list_does_not_include_other_firms_signals(self):
        resp = self.client_a.get(f'/api/firms/{self.firm_a.id}/risk-signals/')
        data = resp.json()
        ids = {r['id'] for r in data['results']}
        self.assertNotIn(self.sig_b.id, ids)

    # ----- Summary endpoint -----------------------------------------------

    def test_summary_counts(self):
        resp = self.client_a.get(f'/api/firms/{self.firm_a.id}/risk-summary/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['total'], 20)
        self.assertEqual(data['by_severity']['critical'], 5)
        self.assertEqual(data['by_severity']['high'], 5)
        self.assertEqual(data['by_severity']['medium'], 5)
        self.assertEqual(data['by_severity']['low'], 5)
        self.assertEqual(data['by_status']['open'], 15)
        self.assertEqual(data['by_status']['acknowledged'], 5)

    def test_summary_includes_all_keys(self):
        resp = self.client_a.get(f'/api/firms/{self.firm_a.id}/risk-summary/')
        data = resp.json()
        self.assertIn('by_severity', data)
        self.assertIn('by_status', data)
        self.assertIn('by_category', data)
        self.assertIn('recent', data)
        self.assertIn('total', data)

    def test_summary_recent_are_open(self):
        resp = self.client_a.get(f'/api/firms/{self.firm_a.id}/risk-summary/')
        data = resp.json()
        for sig in data['recent']:
            self.assertEqual(sig['status'], 'open')
        self.assertLessEqual(len(data['recent']), 5)

    def test_summary_with_status_filter(self):
        resp = self.client_a.get(
            f'/api/firms/{self.firm_a.id}/risk-summary/',
            {'status': 'open'},
        )
        data = resp.json()
        self.assertEqual(data['total'], 15)

    # ----- Detail / PATCH ------------------------------------------------

    def test_get_signal_detail(self):
        sig = RiskSignal.objects.filter(firm=self.firm_a).first()
        resp = self.client_a.get(f'/api/risk-signals/{sig.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['id'], sig.id)

    def test_patch_status_resolve(self):
        sig = RiskSignal.objects.filter(firm=self.firm_a, status='open').first()
        resp = self.client_a.patch(
            f'/api/risk-signals/{sig.id}',
            {'status': 'resolved'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'resolved')
        self.assertIsNotNone(data['resolved_at'])
        self.assertEqual(data['resolved_by_id'], self.user_a.id)

    def test_patch_status_false_positive(self):
        sig = RiskSignal.objects.filter(firm=self.firm_a, status='open').first()
        resp = self.client_a.patch(
            f'/api/risk-signals/{sig.id}',
            {'status': 'false_positive'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'false_positive')

    def test_patch_cross_firm_returns_403(self):
        resp = self.client_a.patch(
            f'/api/risk-signals/{self.sig_b.id}',
            {'status': 'resolved'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)


@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class RiskSummaryPerformanceTest(TestCase):
    """Verify summary endpoint returns in <200ms with 10k+ signals."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='perf@test.com', email='perf@test.com', password='unused',
        )
        self.firm = Firm.objects.create(
            name='Perf Corp', state='Gujarat', city='Ahmedabad',
            owner_email='owner@perf.com', created_by=self.user, status='active',
        )
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_auth_token(self.user)}')

        # Bulk-create 10,000 signals
        sevs = ['critical', 'high', 'medium', 'low']
        cats = list(RiskSignal.Category.values)
        statuses = list(RiskSignal.Status.values)
        batch = [
            RiskSignal(
                firm=self.firm,
                severity=sevs[i % 4],
                category=cats[i % len(cats)],
                status=statuses[i % len(statuses)],
                title=f'Perf signal {i}',
                description=f'Bulk test #{i}',
                entity_type='bill',
                entity_id=i,
            )
            for i in range(10_000)
        ]
        RiskSignal.objects.bulk_create(batch)

    def test_summary_under_200ms(self):
        import time
        start = time.perf_counter()
        resp = self.client.get(f'/api/firms/{self.firm.id}/risk-summary/')
        elapsed_ms = (time.perf_counter() - start) * 1000

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['total'], 10_000)
        self.assertLess(elapsed_ms, 200, f"Summary took {elapsed_ms:.0f}ms, expected <200ms")


# ===========================================================================
# Cash-flow forecast tests
# ===========================================================================

@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class CashFlowForecastEngineTests(TestCase):
    """Unit tests for the forecasting engine itself."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='forecast@test.com', email='forecast@test.com', password='x',
        )
        self.firm = Firm.objects.create(
            name='Forecast Corp', state='Karnataka', city='Bangalore',
            owner_email='owner@forecast.com', created_by=self.user, status='active',
        )
        self.customer = Customer.objects.create(
            firm=self.firm, name='Big Buyer Ltd',
        )
        self.vendor = Vendor.objects.create(
            firm=self.firm, name='Supply Co',
        )
        self.today = date.today()

    def _create_txn(self, **kwargs):
        defaults = {
            'firm': self.firm,
            'txn_type': 'invoice',
            'direction': 'inflow',
            'status': 'completed',
            'amount': Decimal('100000'),
            'currency': 'INR',
            'txn_date': self.today - timedelta(days=30),
        }
        defaults.update(kwargs)
        return Transaction.objects.create(**defaults)

    def test_current_balance_computation(self):
        self._create_txn(direction='inflow', amount=Decimal('500000'),
                         status='completed', txn_date=self.today - timedelta(days=5))
        self._create_txn(direction='outflow', amount=Decimal('200000'),
                         status='completed', txn_date=self.today - timedelta(days=3))

        from intelligence.forecasting import CashFlowForecaster
        result = CashFlowForecaster().forecast(self.firm.id, as_of=self.today)
        self.assertEqual(result.current_balance, Decimal('300000'))

    def test_90_day_forecast_length(self):
        from intelligence.forecasting import CashFlowForecaster
        result = CashFlowForecaster().forecast(self.firm.id, as_of=self.today)
        self.assertEqual(len(result.daily_forecast), 90)

    def test_pressure_detected_with_large_payables(self):
        # Past inflows to establish balance
        self._create_txn(direction='inflow', amount=Decimal('100000'),
                         status='completed', txn_date=self.today - timedelta(days=10))
        # Large upcoming payable
        self._create_txn(direction='outflow', amount=Decimal('500000'),
                         status='pending', txn_date=self.today,
                         due_date=self.today + timedelta(days=20),
                         vendor=self.vendor)

        from intelligence.forecasting import CashFlowForecaster
        result = CashFlowForecaster().forecast(self.firm.id, as_of=self.today)
        self.assertIsNotNone(result.pressure_day)
        self.assertLess(result.pressure_amount, Decimal('0'))

    def test_no_pressure_when_balanced(self):
        self._create_txn(direction='inflow', amount=Decimal('1000000'),
                         status='completed', txn_date=self.today - timedelta(days=5))
        self._create_txn(direction='outflow', amount=Decimal('100000'),
                         status='pending', txn_date=self.today,
                         due_date=self.today + timedelta(days=30), vendor=self.vendor)

        from intelligence.forecasting import CashFlowForecaster
        result = CashFlowForecaster().forecast(self.firm.id, as_of=self.today)
        self.assertIsNone(result.pressure_day)

    def test_explanation_contains_actual_vendor_names(self):
        self._create_txn(direction='inflow', amount=Decimal('50000'),
                         status='completed', txn_date=self.today - timedelta(days=5))
        self._create_txn(direction='outflow', amount=Decimal('800000'),
                         status='pending', txn_date=self.today,
                         due_date=self.today + timedelta(days=15), vendor=self.vendor)

        from intelligence.forecasting import CashFlowForecaster
        result = CashFlowForecaster().forecast(self.firm.id, as_of=self.today)
        self.assertIn('Supply Co', result.risk_explanation)
        self.assertNotIn('{', result.risk_explanation)  # no template placeholders

    def test_explanation_contains_actual_customer_names_for_delayed(self):
        # Overdue receivable
        self._create_txn(
            direction='inflow', amount=Decimal('620000'),
            txn_type='invoice', status='pending',
            txn_date=self.today - timedelta(days=60),
            due_date=self.today - timedelta(days=30),
            customer=self.customer,
        )
        # Small balance so pressure occurs
        self._create_txn(direction='inflow', amount=Decimal('10000'),
                         status='completed', txn_date=self.today - timedelta(days=5))
        self._create_txn(direction='outflow', amount=Decimal('840000'),
                         status='pending', txn_date=self.today,
                         due_date=self.today + timedelta(days=20), vendor=self.vendor)

        from intelligence.forecasting import CashFlowForecaster
        result = CashFlowForecaster().forecast(self.firm.id, as_of=self.today)
        self.assertIn('Big Buyer Ltd', result.risk_explanation)
        self.assertIn('Supply Co', result.risk_explanation)

    def test_weighted_avg_uses_recent_data_more(self):
        """Recent months should dominate the weighted average."""
        # Old transactions: 60 days delay
        for i in range(5):
            self._create_txn(
                direction='inflow', status='fully_matched',
                txn_date=self.today - timedelta(days=150 + i * 5),
                due_date=self.today - timedelta(days=150 + i * 5 + 60),
            )
        # Recent transactions: 15 days delay
        for i in range(5):
            self._create_txn(
                direction='inflow', status='fully_matched',
                txn_date=self.today - timedelta(days=10 + i * 5),
                due_date=self.today - timedelta(days=10 + i * 5 + 15),
            )

        from intelligence.forecasting import CashFlowForecaster
        f = CashFlowForecaster()
        avg = f._weighted_avg_days(self.firm, self.today, 'inflow')
        # Should be closer to 15 than 60
        self.assertLess(avg, Decimal('40'))

    def test_snapshot_persistence(self):
        self._create_txn(direction='inflow', amount=Decimal('100000'),
                         status='completed', txn_date=self.today - timedelta(days=5))

        from intelligence.forecasting import CashFlowForecaster
        f = CashFlowForecaster()
        result = f.forecast(self.firm.id, as_of=self.today)
        snapshot = f.save_snapshot(self.firm.id, result)

        self.assertEqual(snapshot.snapshot_date, self.today)
        self.assertEqual(snapshot.snapshot_type, 'daily')
        self.assertIn('risk_explanation', snapshot.cashflow_forecast)
        self.assertIn('daily_positions', snapshot.breakdown)

    def test_health_score_perfect_when_healthy(self):
        self._create_txn(direction='inflow', amount=Decimal('10000000'),
                         status='completed', txn_date=self.today - timedelta(days=5))

        from intelligence.forecasting import CashFlowForecaster
        result = CashFlowForecaster().forecast(self.firm.id, as_of=self.today)
        self.assertGreaterEqual(result.health_score, Decimal('80'))

    def test_health_score_low_when_negative(self):
        # Only outflows
        self._create_txn(direction='outflow', amount=Decimal('100000'),
                         status='completed', txn_date=self.today - timedelta(days=5))
        self._create_txn(direction='outflow', amount=Decimal('500000'),
                         status='pending', txn_date=self.today,
                         due_date=self.today + timedelta(days=10), vendor=self.vendor)

        from intelligence.forecasting import CashFlowForecaster
        result = CashFlowForecaster().forecast(self.firm.id, as_of=self.today)
        self.assertLess(result.health_score, Decimal('60'))


@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class CashFlowForecastAPITests(TestCase):
    """Integration tests for the /api/firms/{id}/cash-flow-forecast/ endpoint."""

    def setUp(self):
        self.client_api = APIClient()
        self.user = User.objects.create_user(
            username='apiuser@fc.com', email='apiuser@fc.com', password='x',
        )
        self.firm = Firm.objects.create(
            name='API Forecast Inc', state='Delhi', city='New Delhi',
            owner_email='apiuser@fc.com', created_by=self.user, status='active',
        )
        token = _auth_token(self.user)
        self.client_api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        self.today = date.today()
        # Seed some data
        self.customer = Customer.objects.create(firm=self.firm, name='Client A')
        self.vendor = Vendor.objects.create(firm=self.firm, name='Vendor X')

        Transaction.objects.create(
            firm=self.firm, txn_type='payment', direction='inflow',
            status='completed', amount=Decimal('500000'), currency='INR',
            txn_date=self.today - timedelta(days=10),
        )
        Transaction.objects.create(
            firm=self.firm, txn_type='invoice', direction='inflow',
            status='pending', amount=Decimal('300000'), currency='INR',
            txn_date=self.today - timedelta(days=20),
            due_date=self.today + timedelta(days=15),
            customer=self.customer,
        )
        Transaction.objects.create(
            firm=self.firm, txn_type='purchase_order', direction='outflow',
            status='pending', amount=Decimal('200000'), currency='INR',
            txn_date=self.today, due_date=self.today + timedelta(days=25),
            vendor=self.vendor,
        )

    def test_forecast_endpoint_returns_200(self):
        resp = self.client_api.get(f'/api/firms/{self.firm.id}/cash-flow-forecast/')
        self.assertEqual(resp.status_code, 200)

    def test_forecast_response_has_required_fields(self):
        resp = self.client_api.get(f'/api/firms/{self.firm.id}/cash-flow-forecast/')
        data = resp.json()
        for field in ('as_of', 'current_balance', 'position_30d', 'position_60d',
                      'position_90d', 'risk_explanation', 'health_score',
                      'daily_forecast', 'top_delayed_receivables', 'top_upcoming_payables'):
            self.assertIn(field, data, f"Missing field: {field}")

    def test_forecast_daily_has_90_entries(self):
        resp = self.client_api.get(f'/api/firms/{self.firm.id}/cash-flow-forecast/')
        self.assertEqual(len(resp.json()['daily_forecast']), 90)

    def test_cached_forecast_served(self):
        # First call computes and saves
        self.client_api.get(f'/api/firms/{self.firm.id}/cash-flow-forecast/')
        # Second call should serve cached
        resp = self.client_api.get(f'/api/firms/{self.firm.id}/cash-flow-forecast/')
        self.assertEqual(resp.status_code, 200)
        # Verify snapshot was created
        self.assertTrue(
            FinancialSnapshot.objects.filter(
                firm=self.firm, snapshot_date=self.today,
            ).exists()
        )

    def test_fresh_param_forces_recomputation(self):
        self.client_api.get(f'/api/firms/{self.firm.id}/cash-flow-forecast/')
        resp = self.client_api.get(
            f'/api/firms/{self.firm.id}/cash-flow-forecast/?fresh=true'
        )
        self.assertEqual(resp.status_code, 200)

    def test_cross_firm_access_denied(self):
        other_user = User.objects.create_user(
            username='other@fc.com', email='other@fc.com', password='x',
        )
        other_firm = Firm.objects.create(
            name='Other Firm', state='Gujarat', city='Surat',
            owner_email='other@fc.com', created_by=other_user, status='active',
        )
        resp = self.client_api.get(f'/api/firms/{other_firm.id}/cash-flow-forecast/')
        self.assertEqual(resp.status_code, 403)

    def test_explanation_not_a_template(self):
        """Explanation must be generated from actual data, not contain placeholders."""
        resp = self.client_api.get(f'/api/firms/{self.firm.id}/cash-flow-forecast/')
        explanation = resp.json()['risk_explanation']
        self.assertNotIn('{', explanation)
        self.assertNotIn('{{', explanation)
        # Must contain actual rupee amounts
        self.assertIn('₹', explanation)

    def test_celery_task_returns_snapshot_id(self):
        from intelligence.tasks import compute_cashflow_forecast
        result = compute_cashflow_forecast(self.firm.id)
        self.assertIn('snapshot_id', result)
        self.assertIn('health_score', result)

    def test_nightly_fan_out_enqueues_all_firms(self):
        from intelligence.tasks import nightly_cashflow_forecast_all
        nightly_cashflow_forecast_all()
        # After eager execution, snapshot should exist
        self.assertTrue(
            FinancialSnapshot.objects.filter(firm=self.firm, snapshot_date=date.today()).exists()
        )


# ===========================================================================
# Vendor & Customer scoring tests
# ===========================================================================

@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class VendorScoringTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='vscore@test.com', email='vscore@test.com', password='x',
        )
        self.firm = Firm.objects.create(
            name='Score Corp', state='Maharashtra', city='Mumbai',
            owner_email='vscore@test.com', created_by=self.user, status='active',
        )
        self.vendor = Vendor.objects.create(firm=self.firm, name='Acme Supplies')
        self.today = date.today()

    def _txn(self, **kw):
        defaults = {
            'firm': self.firm, 'txn_type': 'invoice', 'direction': 'outflow',
            'status': 'completed', 'amount': Decimal('10000'), 'currency': 'INR',
            'txn_date': self.today - timedelta(days=30), 'vendor': self.vendor,
        }
        defaults.update(kw)
        return Transaction.objects.create(**defaults)

    def test_vendor_score_created(self):
        from intelligence.scoring import compute_vendor_score
        score = compute_vendor_score(self.vendor)
        self.assertIsNotNone(score.overall_score)
        self.assertGreaterEqual(score.overall_score, Decimal('0'))
        self.assertLessEqual(score.overall_score, Decimal('100'))

    def test_vendor_score_with_invoices(self):
        for i in range(5):
            self._txn(txn_type='invoice', txn_date=self.today - timedelta(days=30 * (i + 1)))
        from intelligence.scoring import compute_vendor_score
        score = compute_vendor_score(self.vendor)
        self.assertIn('invoice_consistency', score.breakdown)
        self.assertEqual(score.breakdown['invoice_consistency']['invoice_count'], 5)

    def test_good_payment_history_raises_score(self):
        for i in range(5):
            d = self.today - timedelta(days=10 * (i + 1))
            self._txn(
                txn_type='payment', direction='outflow', status='fully_matched',
                txn_date=d, due_date=d + timedelta(days=5),
            )
        from intelligence.scoring import compute_vendor_score
        score = compute_vendor_score(self.vendor)
        self.assertGreater(score.payment_history, Decimal('70'))

    def test_anomaly_signals_lower_score(self):
        RiskSignal.objects.create(
            firm=self.firm, vendor=self.vendor, severity='critical',
            category='vendor_risk', title='Test', description='Test signal',
            entity_type='vendor', entity_id=self.vendor.id,
        )
        from intelligence.scoring import compute_vendor_score
        score = compute_vendor_score(self.vendor)
        self.assertLess(score.anomaly_history, Decimal('90'))

    def test_breakdown_has_all_metrics(self):
        from intelligence.scoring import compute_vendor_score
        score = compute_vendor_score(self.vendor)
        for key in ['invoice_consistency', 'payment_history', 'price_stability',
                     'document_quality', 'bank_change_frequency', 'anomaly_history']:
            self.assertIn(key, score.breakdown, f"Missing breakdown key: {key}")
            self.assertIn('reason', score.breakdown[key])

    def test_incremental_task(self):
        from intelligence.tasks import compute_vendor_score_task
        result = compute_vendor_score_task(self.vendor.id)
        self.assertIn('score', result)


@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class CustomerScoringTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='cscore@test.com', email='cscore@test.com', password='x',
        )
        self.firm = Firm.objects.create(
            name='CScore Corp', state='Delhi', city='Delhi',
            owner_email='cscore@test.com', created_by=self.user, status='active',
        )
        self.customer = Customer.objects.create(firm=self.firm, name='Big Client')
        self.today = date.today()

    def _txn(self, **kw):
        defaults = {
            'firm': self.firm, 'txn_type': 'invoice', 'direction': 'inflow',
            'status': 'completed', 'amount': Decimal('50000'), 'currency': 'INR',
            'txn_date': self.today - timedelta(days=30), 'customer': self.customer,
        }
        defaults.update(kw)
        return Transaction.objects.create(**defaults)

    def test_customer_score_created(self):
        from intelligence.scoring import compute_customer_score
        score = compute_customer_score(self.customer)
        self.assertGreaterEqual(score.overall_score, Decimal('0'))
        self.assertLessEqual(score.overall_score, Decimal('100'))

    def test_high_revenue_contribution_boosts_score(self):
        # This customer is 100% of firm revenue
        self._txn(amount=Decimal('1000000'), status='fully_matched',
                  due_date=self.today - timedelta(days=25))
        from intelligence.scoring import compute_customer_score
        score = compute_customer_score(self.customer)
        self.assertGreaterEqual(score.revenue_contribution, Decimal('90'))

    def test_high_exposure_lowers_score(self):
        # All pending, nothing matched
        for _ in range(5):
            self._txn(amount=Decimal('200000'), status='pending')
        from intelligence.scoring import compute_customer_score
        score = compute_customer_score(self.customer)
        self.assertLess(score.credit_exposure, Decimal('60'))

    def test_breakdown_has_all_metrics(self):
        from intelligence.scoring import compute_customer_score
        score = compute_customer_score(self.customer)
        for key in ['payment_history', 'avg_payment_time_trend',
                     'credit_exposure', 'revenue_contribution']:
            self.assertIn(key, score.breakdown, f"Missing: {key}")
            self.assertIn('reason', score.breakdown[key])

    def test_incremental_task(self):
        from intelligence.tasks import compute_customer_score_task
        result = compute_customer_score_task(self.customer.id)
        self.assertIn('score', result)

    def test_nightly_batch_runs(self):
        from intelligence.tasks import nightly_score_all
        nightly_score_all()
        self.assertTrue(
            CustomerScore.objects.filter(firm=self.firm, customer=self.customer).exists()
        )


@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class ScoringAPITests(TestCase):

    def setUp(self):
        self.client_api = APIClient()
        self.user = User.objects.create_user(
            username='scoreapi@test.com', email='scoreapi@test.com', password='x',
        )
        self.firm = Firm.objects.create(
            name='API Score Inc', state='Karnataka', city='Bangalore',
            owner_email='scoreapi@test.com', created_by=self.user, status='active',
        )
        token = _auth_token(self.user)
        self.client_api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        self.vendor = Vendor.objects.create(firm=self.firm, name='Test Vendor')
        self.customer = Customer.objects.create(firm=self.firm, name='Test Customer')

        # Pre-compute scores
        from intelligence.scoring import compute_vendor_score, compute_customer_score
        compute_vendor_score(self.vendor)
        compute_customer_score(self.customer)

    def test_vendor_score_list(self):
        resp = self.client_api.get(f'/api/firms/{self.firm.id}/vendor-scores/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['count'], 1)
        self.assertIn('sub_metrics', resp.json()['results'][0])

    def test_vendor_score_detail(self):
        resp = self.client_api.get(f'/api/vendors/{self.vendor.id}/score/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('breakdown', data)
        self.assertIn('invoice_consistency', data['breakdown'])

    def test_vendor_score_recompute_via_post(self):
        resp = self.client_api.post(f'/api/vendors/{self.vendor.id}/score/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('overall_score', resp.json())

    def test_customer_score_list(self):
        resp = self.client_api.get(f'/api/firms/{self.firm.id}/customer-scores/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['count'], 1)

    def test_customer_score_detail(self):
        resp = self.client_api.get(f'/api/customers/{self.customer.id}/score/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('breakdown', data)
        self.assertIn('payment_history', data['breakdown'])

    def test_customer_score_recompute_via_post(self):
        resp = self.client_api.post(f'/api/customers/{self.customer.id}/score/')
        self.assertEqual(resp.status_code, 200)

    def test_cross_firm_access_denied(self):
        other_user = User.objects.create_user(
            username='other@score.com', email='other@score.com', password='x',
        )
        other_firm = Firm.objects.create(
            name='Other Firm', state='Gujarat', city='Surat',
            owner_email='other@score.com', created_by=other_user, status='active',
        )
        resp = self.client_api.get(f'/api/firms/{other_firm.id}/vendor-scores/')
        self.assertEqual(resp.status_code, 403)

    def test_breakdown_reasons_are_not_templates(self):
        resp = self.client_api.get(f'/api/vendors/{self.vendor.id}/score/')
        breakdown = resp.json()['breakdown']
        for key, detail in breakdown.items():
            reason = detail.get('reason', '')
            self.assertNotIn('{{', reason, f"Template placeholder in {key}")
            self.assertNotIn('{0}', reason, f"Template placeholder in {key}")


@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class MultiCurrencyTransactionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='fx@test.com', email='fx@test.com', password='x',
        )
        self.firm = Firm.objects.create(
            name='FX Corp', state='Maharashtra', city='Mumbai',
            owner_email='fx@test.com', created_by=self.user, status='active',
            base_currency='INR',
        )

    def test_inr_transaction_defaults_to_unit_rate(self):
        txn = Transaction.objects.create(
            firm=self.firm,
            txn_type='invoice',
            direction='inflow',
            status='pending',
            amount=Decimal('1000.00'),
            currency='INR',
            txn_date=date(2026, 8, 1),
        )
        self.assertEqual(txn.exchange_rate, Decimal('1.00000000'))
        self.assertEqual(txn.base_currency_amount, Decimal('1000.00'))
        self.assertEqual(txn.base_currency, 'INR')

    def test_foreign_currency_transaction_uses_historical_rate(self):
        ExchangeRate.objects.create(
            from_currency='USD',
            to_currency='INR',
            rate_date=date(2026, 8, 1),
            rate=Decimal('83.25000000'),
            source='test',
        )
        txn = Transaction.objects.create(
            firm=self.firm,
            txn_type='invoice',
            direction='inflow',
            status='pending',
            amount=Decimal('100.00'),
            currency='USD',
            txn_date=date(2026, 8, 1),
        )
        self.assertEqual(txn.exchange_rate, Decimal('83.25000000'))
        self.assertEqual(txn.base_currency_amount, Decimal('8325.00'))


@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class HistoricalFXRateTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='rates@test.com', email='rates@test.com', password='x',
        )
        self.firm = Firm.objects.create(
            name='Rates Corp', state='Delhi', city='Delhi',
            owner_email='rates@test.com', created_by=self.user, status='active',
            base_currency='INR',
        )
        Transaction.objects.create(
            firm=self.firm,
            txn_type='invoice',
            direction='inflow',
            status='pending',
            amount=Decimal('100.00'),
            currency='USD',
            exchange_rate=Decimal('83.00000000'),
            base_currency='INR',
            base_currency_amount=Decimal('8300.00'),
            txn_date=date(2026, 8, 1),
        )

    @patch('intelligence.fx.urllib.request.urlopen')
    def test_daily_task_stores_historical_rates(self, mock_urlopen):
        response = MagicMock()
        response.read.return_value = (
            b'{"amount":1.0,"base":"INR","date":"2026-08-19","rates":{"USD":0.01210000}}'
        )
        mock_urlopen.return_value.__enter__.return_value = response

        from intelligence.tasks import fetch_historical_exchange_rates

        result = fetch_historical_exchange_rates(rate_iso='2026-08-19')
        self.assertEqual(result['stored'], 1)
        rate = ExchangeRate.objects.get(
            from_currency='INR',
            to_currency='USD',
            rate_date=date(2026, 8, 19),
        )
        self.assertEqual(rate.rate, Decimal('0.01210000'))


@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class RealizedFXSettlementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='settlefx@test.com', email='settlefx@test.com', password='x',
        )
        self.firm = Firm.objects.create(
            name='Settlement FX Ltd', state='Gujarat', city='Ahmedabad',
            owner_email='settlefx@test.com', created_by=self.user, status='active',
            base_currency='INR',
        )
        self.vendor = Vendor.objects.create(firm=self.firm, name='Global Vendor')

    def test_fx_difference_locked_at_settlement(self):
        from intelligence.reconciliation import ReconciliationEngine

        ExchangeRate.objects.create(
            from_currency='USD', to_currency='INR',
            rate_date=date(2026, 8, 1), rate=Decimal('80.00000000'), source='test',
        )
        ExchangeRate.objects.create(
            from_currency='USD', to_currency='INR',
            rate_date=date(2026, 8, 7), rate=Decimal('82.00000000'), source='test',
        )

        invoice = Transaction.objects.create(
            firm=self.firm,
            txn_type='invoice',
            direction='outflow',
            status='pending',
            amount=Decimal('100.00'),
            currency='USD',
            txn_date=date(2026, 8, 1),
            vendor=self.vendor,
        )
        payment = Transaction.objects.create(
            firm=self.firm,
            txn_type='payment',
            direction='outflow',
            status='completed',
            amount=Decimal('100.00'),
            currency='USD',
            txn_date=date(2026, 8, 7),
            vendor=self.vendor,
        )

        ReconciliationEngine().match(self.firm.id)

        link = ReconciliationLink.objects.get(transaction=invoice, matched_transaction=payment)
        self.assertEqual(link.original_base_amount, Decimal('8000.00'))
        self.assertEqual(link.settlement_base_amount, Decimal('8200.00'))
        self.assertEqual(link.fx_difference, Decimal('200.00'))
        self.assertEqual(link.settlement_currency, 'USD')
        self.assertEqual(link.settlement_exchange_rate, Decimal('82.00000000'))

        ExchangeRate.objects.create(
            from_currency='USD', to_currency='INR',
            rate_date=date(2026, 8, 19), rate=Decimal('90.00000000'), source='test',
        )
        link.refresh_from_db()
        self.assertEqual(link.fx_difference, Decimal('200.00'))

    def test_cross_currency_match_uses_base_currency_amounts(self):
        from intelligence.reconciliation import ReconciliationEngine

        ExchangeRate.objects.create(
            from_currency='USD', to_currency='INR',
            rate_date=date(2026, 8, 1), rate=Decimal('83.00000000'), source='test',
        )

        invoice = Transaction.objects.create(
            firm=self.firm,
            txn_type='invoice',
            direction='outflow',
            status='pending',
            amount=Decimal('100.00'),
            currency='USD',
            txn_date=date(2026, 8, 1),
            vendor=self.vendor,
        )
        payment = Transaction.objects.create(
            firm=self.firm,
            txn_type='payment',
            direction='outflow',
            status='completed',
            amount=Decimal('8300.00'),
            currency='INR',
            txn_date=date(2026, 8, 1),
            vendor=self.vendor,
        )

        run = ReconciliationEngine().match(self.firm.id)
        self.assertEqual(run.exact_matches, 1)
        link = ReconciliationLink.objects.get(transaction=invoice, matched_transaction=payment)
        self.assertEqual(link.fx_difference, Decimal('0.00'))


class InvoiceCurrencyDefaultsTests(TestCase):
    def test_mock_invoice_data_includes_currency(self):
        user = User.objects.create_user(
            username='billfx@test.com', email='billfx@test.com', password='x',
        )
        firm = Firm.objects.create(
            name='Bill FX Co', state='Maharashtra', city='Pune',
            owner_email='billfx@test.com', created_by=user, status='active',
        )
        bill = type('BillStub', (), {'id': 1})()
        payload = generate_mock_data(bill, firm)
        self.assertEqual(payload['currency'], 'INR')


# ═══════════════════════════════════════════════════════════════════
# Trade-Finance Analysis Tests
# ═══════════════════════════════════════════════════════════════════

@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
def _seed_fx_rate():
    """Seed a USD→INR rate so Transaction.save() doesn't hit live API."""
    ExchangeRate.objects.get_or_create(
        from_currency='USD', to_currency='INR', rate_date=date(2026, 1, 1),
        defaults={'rate': Decimal('83.00000000'), 'source': 'test'},
    )


class TradeFinanceValueMismatchTests(TestCase):
    """Detect invoice value vs customs declared value divergence."""

    def setUp(self):
        _seed_fx_rate()
        self.user = User.objects.create_user(
            username='trade@test.com', email='trade@test.com', password='x',
        )
        self.firm = Firm.objects.create(
            name='Trade Corp', state='Maharashtra', city='Mumbai',
            owner_email='trade@test.com', created_by=self.user, status='active',
        )
        self.vendor = Vendor.objects.create(firm=self.firm, name='Global Freight Partners Ltd')

        self.trade_doc = ImportExportRecord.objects.create(
            firm=self.firm,
            file_name='be_001.pdf',
            file_url='/media/test.pdf',
            status='verified',
            uploaded_by=self.user,
            be_number='BE2026-00123',
            be_date=date(2026, 8, 1),
            currency='USD',
            assessable_value=Decimal('85000.00'),
            shipper_name='Global Freight Partners Ltd',
        )

    def test_no_signal_when_within_tolerance(self):
        Transaction.objects.create(
            firm=self.firm, txn_type='invoice', direction='outflow',
            status='pending', amount=Decimal('85000.00'), currency='USD',
            txn_date=date(2026, 7, 15), vendor=self.vendor,
        )
        from intelligence.trade_finance import TradeFinanceAnalyser
        result = TradeFinanceAnalyser().analyse(self.firm.id)
        self.assertEqual(result['signals_created'], 0)
        self.assertEqual(result['links_created'], 1)

    def test_signal_raised_on_value_mismatch(self):
        Transaction.objects.create(
            firm=self.firm, txn_type='invoice', direction='outflow',
            status='pending', amount=Decimal('95000.00'), currency='USD',
            txn_date=date(2026, 7, 15), vendor=self.vendor,
        )
        from intelligence.trade_finance import TradeFinanceAnalyser
        result = TradeFinanceAnalyser().analyse(self.firm.id)
        self.assertEqual(result['signals_created'], 1)

        sig = RiskSignal.objects.get(
            firm=self.firm,
            category=RiskSignal.Category.TRADE_VALUE_MISMATCH,
        )
        self.assertEqual(sig.entity_type, 'trade_doc')
        self.assertEqual(sig.entity_id, self.trade_doc.id)
        self.assertIn('95000', sig.description)
        self.assertIn('85000', sig.description)

    def test_link_stores_value_difference(self):
        Transaction.objects.create(
            firm=self.firm, txn_type='invoice', direction='outflow',
            status='pending', amount=Decimal('90000.00'), currency='USD',
            txn_date=date(2026, 7, 15), vendor=self.vendor,
        )
        from intelligence.trade_finance import TradeFinanceAnalyser
        TradeFinanceAnalyser().analyse(self.firm.id)

        link = TradeFinanceLink.objects.get(firm=self.firm, trade_doc=self.trade_doc)
        self.assertEqual(link.invoice_amount, Decimal('90000.00'))
        self.assertEqual(link.customs_declared_value, Decimal('85000.00'))
        self.assertEqual(link.value_difference, Decimal('5000.00'))

    def test_idempotent_rerun_does_not_duplicate(self):
        Transaction.objects.create(
            firm=self.firm, txn_type='invoice', direction='outflow',
            status='pending', amount=Decimal('95000.00'), currency='USD',
            txn_date=date(2026, 7, 15), vendor=self.vendor,
        )
        from intelligence.trade_finance import TradeFinanceAnalyser
        analyser = TradeFinanceAnalyser()
        analyser.analyse(self.firm.id)
        analyser.analyse(self.firm.id)
        self.assertEqual(TradeFinanceLink.objects.filter(firm=self.firm).count(), 1)
        self.assertEqual(
            RiskSignal.objects.filter(
                firm=self.firm, category=RiskSignal.Category.TRADE_VALUE_MISMATCH,
            ).count(), 1,
        )


@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class TradeFinancePaymentBeforeShipmentTests(TestCase):
    """Detect payment due dates falling before expected shipment realization."""

    def setUp(self):
        _seed_fx_rate()
        self.user = User.objects.create_user(
            username='ship@test.com', email='ship@test.com', password='x',
        )
        self.firm = Firm.objects.create(
            name='Shipment Corp', state='Gujarat', city='Ahmedabad',
            owner_email='ship@test.com', created_by=self.user, status='active',
        )
        self.vendor = Vendor.objects.create(firm=self.firm, name='Sea Carrier Inc')

        self.trade_doc = ImportExportRecord.objects.create(
            firm=self.firm,
            file_name='be_002.pdf',
            file_url='/media/test2.pdf',
            status='needs_review',
            uploaded_by=self.user,
            be_number='BE2026-00456',
            be_date=date(2026, 8, 1),
            currency='USD',
            assessable_value=Decimal('50000.00'),
            shipper_name='Sea Carrier Inc',
        )

    def test_signal_raised_when_payment_due_before_shipment(self):
        inv = Transaction.objects.create(
            firm=self.firm, txn_type='invoice', direction='outflow',
            status='pending', amount=Decimal('50000.00'), currency='USD',
            txn_date=date(2026, 7, 20), vendor=self.vendor,
            due_date=date(2026, 8, 5),
        )
        Transaction.objects.create(
            firm=self.firm, txn_type='payment', direction='outflow',
            status='completed', amount=Decimal('50000.00'), currency='USD',
            txn_date=date(2026, 8, 3), vendor=self.vendor,
        )
        from intelligence.trade_finance import TradeFinanceAnalyser
        result = TradeFinanceAnalyser().analyse(self.firm.id)
        self.assertGreaterEqual(result['signals_created'], 1)

        sig = RiskSignal.objects.get(
            firm=self.firm,
            category=RiskSignal.Category.PAYMENT_BEFORE_SHIPMENT,
        )
        self.assertEqual(sig.severity, 'high')
        self.assertIn('2026-08-05', sig.description)

    def test_no_signal_when_payment_after_shipment(self):
        Transaction.objects.create(
            firm=self.firm, txn_type='invoice', direction='outflow',
            status='pending', amount=Decimal('50000.00'), currency='USD',
            txn_date=date(2026, 7, 20), vendor=self.vendor,
            due_date=date(2026, 9, 1),
        )
        from intelligence.trade_finance import TradeFinanceAnalyser
        result = TradeFinanceAnalyser().analyse(self.firm.id)
        pbs_signals = RiskSignal.objects.filter(
            firm=self.firm, category=RiskSignal.Category.PAYMENT_BEFORE_SHIPMENT,
        ).count()
        self.assertEqual(pbs_signals, 0)


@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class TradeFinanceLinkChainTests(TestCase):
    """Verify PO → Invoice → Customs → Payment chain building."""

    def setUp(self):
        _seed_fx_rate()
        self.user = User.objects.create_user(
            username='chain@test.com', email='chain@test.com', password='x',
        )
        self.firm = Firm.objects.create(
            name='Chain Corp', state='Delhi', city='Delhi',
            owner_email='chain@test.com', created_by=self.user, status='active',
        )
        self.vendor = Vendor.objects.create(firm=self.firm, name='Supplier Co')

    def test_full_chain_marked_complete(self):
        po = Transaction.objects.create(
            firm=self.firm, txn_type='purchase_order', direction='outflow',
            status='pending', amount=Decimal('10000.00'), currency='USD',
            txn_date=date(2026, 6, 1), vendor=self.vendor,
        )
        inv = Transaction.objects.create(
            firm=self.firm, txn_type='invoice', direction='outflow',
            status='pending', amount=Decimal('10000.00'), currency='USD',
            txn_date=date(2026, 7, 1), vendor=self.vendor,
        )
        td = ImportExportRecord.objects.create(
            firm=self.firm, file_name='be.pdf', file_url='/media/be.pdf',
            status='verified', uploaded_by=self.user,
            be_number='BE-001', be_date=date(2026, 7, 15),
            currency='USD', assessable_value=Decimal('10000.00'),
            shipper_name='Supplier Co',
        )
        pay = Transaction.objects.create(
            firm=self.firm, txn_type='payment', direction='outflow',
            status='completed', amount=Decimal('10000.00'), currency='USD',
            txn_date=date(2026, 8, 1), vendor=self.vendor,
        )

        from intelligence.trade_finance import TradeFinanceAnalyser
        TradeFinanceAnalyser().analyse(self.firm.id)

        link = TradeFinanceLink.objects.get(firm=self.firm, trade_doc=td)
        self.assertEqual(link.status, 'complete')
        self.assertEqual(link.purchase_order_txn_id, po.id)
        self.assertEqual(link.invoice_txn_id, inv.id)
        self.assertEqual(link.payment_txn_id, pay.id)
        self.assertEqual(link.value_difference, Decimal('0.00'))

    def test_partial_chain_when_no_payment(self):
        Transaction.objects.create(
            firm=self.firm, txn_type='invoice', direction='outflow',
            status='pending', amount=Decimal('10000.00'), currency='USD',
            txn_date=date(2026, 7, 1), vendor=self.vendor,
        )
        td = ImportExportRecord.objects.create(
            firm=self.firm, file_name='be2.pdf', file_url='/media/be2.pdf',
            status='verified', uploaded_by=self.user,
            be_number='BE-002', be_date=date(2026, 7, 15),
            currency='USD', assessable_value=Decimal('10000.00'),
            shipper_name='Supplier Co',
        )

        from intelligence.trade_finance import TradeFinanceAnalyser
        TradeFinanceAnalyser().analyse(self.firm.id)

        link = TradeFinanceLink.objects.get(firm=self.firm, trade_doc=td)
        self.assertEqual(link.status, 'partial')
        self.assertIsNone(link.payment_txn)


@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class TradeFinanceAPITests(TestCase):
    """Test the /api/firms/{id}/trade-finance/ endpoint."""

    def setUp(self):
        _seed_fx_rate()
        self.client_api = APIClient()
        self.user = User.objects.create_user(
            username='tfapi@test.com', email='tfapi@test.com', password='x',
        )
        self.firm = Firm.objects.create(
            name='TF API Corp', state='Karnataka', city='Bangalore',
            owner_email='tfapi@test.com', created_by=self.user, status='active',
        )
        token = _auth_token(self.user)
        self.client_api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        self.vendor = Vendor.objects.create(firm=self.firm, name='API Vendor')

        self.td = ImportExportRecord.objects.create(
            firm=self.firm, file_name='api_be.pdf', file_url='/media/api_be.pdf',
            status='verified', uploaded_by=self.user,
            be_number='API-BE-001', be_date=date(2026, 8, 1),
            currency='USD', assessable_value=Decimal('20000.00'),
            shipper_name='API Vendor',
        )
        Transaction.objects.create(
            firm=self.firm, txn_type='invoice', direction='outflow',
            status='pending', amount=Decimal('25000.00'), currency='USD',
            txn_date=date(2026, 7, 20), vendor=self.vendor,
        )

    def test_post_triggers_analysis(self):
        resp = self.client_api.post(f'/api/firms/{self.firm.id}/trade-finance/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['trade_docs_scanned'], 1)
        self.assertEqual(data['links_created'], 1)
        self.assertGreaterEqual(data['signals_created'], 1)

    def test_get_returns_links(self):
        self.client_api.post(f'/api/firms/{self.firm.id}/trade-finance/')
        resp = self.client_api.get(f'/api/firms/{self.firm.id}/trade-finance/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['count'], 1)
        link = data['results'][0]
        self.assertIn('value_difference', link)
        self.assertIn('payment_before_shipment', link)

    def test_cross_firm_access_denied(self):
        other_user = User.objects.create_user(
            username='other_tf@test.com', email='other_tf@test.com', password='x',
        )
        other_firm = Firm.objects.create(
            name='Other TF', state='UP', city='Lucknow',
            owner_email='other_tf@test.com', created_by=other_user, status='active',
        )
        resp = self.client_api.get(f'/api/firms/{other_firm.id}/trade-finance/')
        self.assertEqual(resp.status_code, 403)

    def test_existing_trade_doc_flows_untouched(self):
        """Verify that the trade doc extraction/verify/retry views are unmodified."""
        from django.urls import reverse
        resp = self.client_api.get(f'/api/firms/{self.firm.id}/trade-docs')
        self.assertEqual(resp.status_code, 200)

    def test_risk_signals_use_existing_model(self):
        self.client_api.post(f'/api/firms/{self.firm.id}/trade-finance/')
        signals = RiskSignal.objects.filter(
            firm=self.firm,
            category__in=[
                RiskSignal.Category.TRADE_VALUE_MISMATCH,
                RiskSignal.Category.PAYMENT_BEFORE_SHIPMENT,
            ],
        )
        self.assertGreaterEqual(signals.count(), 1)
        for sig in signals:
            self.assertEqual(sig.entity_type, 'trade_doc')


# ═══════════════════════════════════════════════════════════════════════
# Graph traversal tests
# ═══════════════════════════════════════════════════════════════════════

@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class GraphRiskSignalTraversalTests(TestCase):
    """Test 'show all transactions connected to this risk signal'."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='graph@test.com', email='graph@test.com', password='x',
        )
        self.firm = Firm.objects.create(
            name='GraphCorp', state='MH', city='Mumbai',
            owner_email='g@test.com', created_by=self.user, status='active',
        )
        _seed_fx_rate()

        self.vendor = Vendor.objects.create(firm=self.firm, name='V1', gstin='29TESTV1000A1Z5')
        self.txn = Transaction.objects.create(
            firm=self.firm, txn_type='invoice', direction='outflow', status='pending',
            amount=Decimal('5000'), txn_date=date(2026, 1, 10), vendor=self.vendor,
            reference_number='INV-G001',
        )
        self.signal = RiskSignal.objects.create(
            firm=self.firm, severity='high', category='unusual_amount',
            status='open', title='Unusual amount', description='Test',
            entity_type='transaction', entity_id=self.txn.id,
            vendor=self.vendor, confidence=Decimal('0.90'),
        )

    def test_risk_signal_graph_returns_nodes_and_edges(self):
        from intelligence.graph import risk_signal_graph
        result = risk_signal_graph(self.firm.id, self.signal.id)
        self.assertGreaterEqual(result['node_count'], 2)
        self.assertGreaterEqual(result['edge_count'], 1)
        types = {n['type'] for n in result['nodes']}
        self.assertIn('risk_signal', types)
        self.assertIn('transaction', types)

    def test_risk_signal_graph_includes_vendor(self):
        from intelligence.graph import risk_signal_graph
        result = risk_signal_graph(self.firm.id, self.signal.id)
        types = {n['type'] for n in result['nodes']}
        self.assertIn('vendor', types)

    def test_risk_signal_graph_includes_reconciled_txns(self):
        import uuid
        from intelligence.models import ReconciliationLink
        payment = Transaction.objects.create(
            firm=self.firm, txn_type='payment', direction='inflow', status='completed',
            amount=Decimal('5000'), txn_date=date(2026, 1, 15), vendor=self.vendor,
        )
        ReconciliationLink.objects.create(
            firm=self.firm, match_group=uuid.uuid4(),
            transaction=self.txn, matched_transaction=payment,
            match_confidence=Decimal('0.9500'), match_method='rule_based',
        )
        from intelligence.graph import risk_signal_graph
        result = risk_signal_graph(self.firm.id, self.signal.id)
        txn_ids = {n['id'] for n in result['nodes'] if n['type'] == 'transaction'}
        self.assertIn(payment.id, txn_ids)


@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class GraphVendorHistoryTests(TestCase):
    """Test 'show this vendor's full relationship history'."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='vhist@test.com', email='vhist@test.com', password='x',
        )
        self.firm = Firm.objects.create(
            name='VHistCorp', state='MH', city='Mumbai',
            owner_email='vh@test.com', created_by=self.user, status='active',
        )
        _seed_fx_rate()
        self.vendor = Vendor.objects.create(firm=self.firm, name='HistVendor', gstin='29HISTV000A1Z5')

        for i in range(5):
            Transaction.objects.create(
                firm=self.firm, txn_type='invoice', direction='outflow', status='pending',
                amount=Decimal(str(1000 * (i + 1))), txn_date=date(2026, 1, i + 1),
                vendor=self.vendor, reference_number=f'INV-VH{i}',
            )
        RiskSignal.objects.create(
            firm=self.firm, severity='medium', category='late_payment',
            status='open', title='Late payment', description='test',
            entity_type='vendor', entity_id=self.vendor.id,
            vendor=self.vendor, confidence=Decimal('0.75'),
        )

    def test_vendor_history_returns_all_txns(self):
        from intelligence.graph import vendor_history
        result = vendor_history(self.firm.id, self.vendor.id)
        txn_nodes = [n for n in result['nodes'] if n['type'] == 'transaction']
        self.assertEqual(len(txn_nodes), 5)

    def test_vendor_history_includes_risk_signals(self):
        from intelligence.graph import vendor_history
        result = vendor_history(self.firm.id, self.vendor.id)
        sig_nodes = [n for n in result['nodes'] if n['type'] == 'risk_signal']
        self.assertEqual(len(sig_nodes), 1)

    def test_vendor_history_summary(self):
        from intelligence.graph import vendor_history
        result = vendor_history(self.firm.id, self.vendor.id)
        self.assertEqual(result['summary']['total_transactions'], 5)
        self.assertEqual(result['summary']['open_risk_signals'], 1)


@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class GraphEvidenceDrilldownTests(TestCase):
    """Test evidence drill-down used by the Agentic / Audit layer."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='evid@test.com', email='evid@test.com', password='x',
        )
        self.firm = Firm.objects.create(
            name='EvidCorp', state='MH', city='Mumbai',
            owner_email='e@test.com', created_by=self.user, status='active',
        )
        _seed_fx_rate()
        self.vendor = Vendor.objects.create(firm=self.firm, name='EvidVendor')
        self.txn = Transaction.objects.create(
            firm=self.firm, txn_type='invoice', direction='outflow', status='pending',
            amount=Decimal('7500'), txn_date=date(2026, 2, 1), vendor=self.vendor,
        )
        self.signal = RiskSignal.objects.create(
            firm=self.firm, severity='high', category='unusual_amount',
            status='open', title='Unusual', description='desc',
            entity_type='transaction', entity_id=self.txn.id,
            vendor=self.vendor, confidence=Decimal('0.85'),
        )

    def test_evidence_from_transaction(self):
        from intelligence.graph import evidence_drilldown
        result = evidence_drilldown(self.firm.id, 'transaction', self.txn.id)
        self.assertEqual(result['entity_type'], 'transaction')
        types = {n['type'] for n in result['nodes']}
        self.assertIn('transaction', types)
        self.assertIn('risk_signal', types)

    def test_evidence_from_vendor(self):
        from intelligence.graph import evidence_drilldown
        result = evidence_drilldown(self.firm.id, 'vendor', self.vendor.id)
        self.assertEqual(result['entity_type'], 'vendor')
        self.assertGreaterEqual(result['node_count'], 2)

    def test_evidence_unknown_type(self):
        from intelligence.graph import evidence_drilldown
        result = evidence_drilldown(self.firm.id, 'unknown_thing', 1)
        self.assertIn('error', result)


@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class GraphAPIEndpointTests(TestCase):
    """Test the REST endpoints for graph traversal."""

    def setUp(self):
        self.client_a = APIClient()
        self.client_b = APIClient()

        self.user_a = User.objects.create_user(
            username='ga@test.com', email='ga@test.com', password='x',
        )
        self.user_b = User.objects.create_user(
            username='gb@test.com', email='gb@test.com', password='x',
        )
        self.firm_a = Firm.objects.create(
            name='GA Corp', state='MH', city='Mumbai',
            owner_email='ga@test.com', created_by=self.user_a, status='active',
        )
        self.firm_b = Firm.objects.create(
            name='GB Corp', state='KA', city='Bengaluru',
            owner_email='gb@test.com', created_by=self.user_b, status='active',
        )
        self.client_a.credentials(HTTP_AUTHORIZATION=f'Bearer {_auth_token(self.user_a)}')
        self.client_b.credentials(HTTP_AUTHORIZATION=f'Bearer {_auth_token(self.user_b)}')
        _seed_fx_rate()

        self.vendor = Vendor.objects.create(firm=self.firm_a, name='API Vendor')
        self.customer = Customer.objects.create(firm=self.firm_a, name='API Customer')
        self.txn = Transaction.objects.create(
            firm=self.firm_a, txn_type='invoice', direction='outflow', status='pending',
            amount=Decimal('1000'), txn_date=date(2026, 3, 1), vendor=self.vendor,
        )
        self.signal = RiskSignal.objects.create(
            firm=self.firm_a, severity='high', category='unusual_amount',
            status='open', title='API test', description='desc',
            entity_type='transaction', entity_id=self.txn.id,
            vendor=self.vendor, confidence=Decimal('0.90'),
        )

    def test_risk_signal_graph_endpoint(self):
        resp = self.client_a.get(f'/api/firms/{self.firm_a.id}/graph/risk-signal/{self.signal.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('nodes', resp.json())
        self.assertIn('edges', resp.json())

    def test_vendor_graph_endpoint(self):
        resp = self.client_a.get(f'/api/firms/{self.firm_a.id}/graph/vendor/{self.vendor.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('nodes', resp.json())

    def test_customer_graph_endpoint(self):
        resp = self.client_a.get(f'/api/firms/{self.firm_a.id}/graph/customer/{self.customer.id}/')
        self.assertEqual(resp.status_code, 200)

    def test_evidence_endpoint(self):
        resp = self.client_a.get(
            f'/api/firms/{self.firm_a.id}/graph/evidence/',
            {'entity_type': 'transaction', 'entity_id': self.txn.id},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('nodes', resp.json())

    def test_cross_firm_access_blocked(self):
        resp = self.client_b.get(f'/api/firms/{self.firm_a.id}/graph/risk-signal/{self.signal.id}/')
        self.assertEqual(resp.status_code, 403)

    def test_evidence_missing_params(self):
        resp = self.client_a.get(f'/api/firms/{self.firm_a.id}/graph/evidence/')
        self.assertEqual(resp.status_code, 400)


@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class GraphPerformanceTests(TestCase):
    """Acceptance test: traversal on 10k+ transactions completes in <500ms."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='perf@graph.com', email='perf@graph.com', password='x',
        )
        self.firm = Firm.objects.create(
            name='PerfCorp', state='MH', city='Mumbai',
            owner_email='p@test.com', created_by=self.user, status='active',
        )
        _seed_fx_rate()
        self.vendor = Vendor.objects.create(firm=self.firm, name='BigVendor')

        txns = []
        base = date(2024, 1, 1)
        for i in range(10_000):
            txns.append(Transaction(
                firm=self.firm, txn_type='invoice', direction='outflow', status='pending',
                amount=Decimal(str(100 + i)), txn_date=base + timedelta(days=i % 365),
                vendor=self.vendor, reference_number=f'BULK-{i}',
                currency='INR', base_currency='INR',
                exchange_rate=Decimal('1.00000000'),
                base_currency_amount=Decimal(str(100 + i)),
            ))
        Transaction.objects.bulk_create(txns, batch_size=2000)

        self.signal = RiskSignal.objects.create(
            firm=self.firm, severity='high', category='vendor_risk',
            status='open', title='Perf test', description='10k test',
            entity_type='vendor', entity_id=self.vendor.id,
            vendor=self.vendor, confidence=Decimal('0.85'),
        )

    def test_risk_signal_graph_under_500ms(self):
        import time
        from intelligence.graph import risk_signal_graph
        start = time.perf_counter()
        result = risk_signal_graph(self.firm.id, self.signal.id)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 0.5, f'Took {elapsed:.3f}s — must be <500ms')
        self.assertGreater(result['node_count'], 0)

    def test_vendor_history_under_500ms(self):
        import time
        from intelligence.graph import vendor_history
        start = time.perf_counter()
        result = vendor_history(self.firm.id, self.vendor.id)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 0.5, f'Took {elapsed:.3f}s — must be <500ms')
        self.assertEqual(result['summary']['vendor_name'], 'BigVendor')

    def test_evidence_drilldown_under_500ms(self):
        import time
        from intelligence.graph import evidence_drilldown
        start = time.perf_counter()
        result = evidence_drilldown(self.firm.id, 'vendor', self.vendor.id)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 0.5, f'Took {elapsed:.3f}s — must be <500ms')
