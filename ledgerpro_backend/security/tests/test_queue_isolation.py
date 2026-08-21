"""
Celery queue routing + extraction/agent isolation acceptance tests.
"""
from __future__ import annotations

from django.conf import settings
from django.test import SimpleTestCase

from common.queue_isolation import NUM_EXTRACTION_JOBS, run_isolation_simulation
from ledgerpro_backend.celery_queues import (
    QUEUE_AGENTS,
    QUEUE_DEFAULT,
    QUEUE_EXTRACTION,
    QUEUE_RISK,
    TASK_ROUTES,
)


class CeleryQueueRoutingTests(SimpleTestCase):
    def test_settings_expose_named_routes(self):
        self.assertEqual(settings.CELERY_TASK_DEFAULT_QUEUE, QUEUE_DEFAULT)
        self.assertIn("invoices.tasks.extract_invoice_data", settings.CELERY_TASK_ROUTES)
        self.assertEqual(
            settings.CELERY_TASK_ROUTES["invoices.tasks.extract_invoice_data"]["queue"],
            QUEUE_EXTRACTION,
        )

    def test_extraction_tasks_never_share_agents_queue(self):
        for name, route in TASK_ROUTES.items():
            if "extract_" in name:
                self.assertEqual(
                    route["queue"],
                    QUEUE_EXTRACTION,
                    f"{name} must stay on extraction",
                )
                self.assertNotEqual(route["queue"], QUEUE_AGENTS)

    def test_agent_tasks_routed_to_agents_queue(self):
        self.assertEqual(TASK_ROUTES["agents.tasks.run_agent_query"]["queue"], QUEUE_AGENTS)
        self.assertEqual(
            TASK_ROUTES["agents.tasks.simulate_slow_llm_turn"]["queue"], QUEUE_AGENTS,
        )

    def test_risk_tasks_routed_to_risk_queue(self):
        for name in (
            "intelligence.tasks.run_reconciliation",
            "intelligence.tasks.scan_firm_risks",
            "intelligence.tasks.compute_cashflow_forecast",
            "intelligence.tasks.analyse_trade_finance",
        ):
            self.assertEqual(TASK_ROUTES[name]["queue"], QUEUE_RISK)


class QueueIsolationLoadTests(SimpleTestCase):
    """Acceptance: extraction SLA unaffected by saturated agents queue."""

    def test_extraction_sla_under_concurrent_agent_load(self):
        isolated = run_isolation_simulation(shared_pool=False)
        self.assertTrue(
            isolated["sla_met"],
            f"extraction p95 {isolated['extraction_wait_p95']:.3f}s "
            f"> SLA {isolated['sla_sec']}s under agent load",
        )
        self.assertEqual(isolated["extraction_count"], NUM_EXTRACTION_JOBS)

    def test_shared_pool_is_worse_than_isolated(self):
        isolated = run_isolation_simulation(shared_pool=False)
        coupled = run_isolation_simulation(shared_pool=True)
        self.assertLess(
            isolated["extraction_wait_p95"],
            coupled["extraction_wait_p95"],
            "shared worker pool must inflate extraction wait vs isolated queues",
        )
