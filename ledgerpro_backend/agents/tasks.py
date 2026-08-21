"""
Async agent / LLM turns — always routed to the ``agents`` Celery queue.

The HTTP API may still call ``execute_agent`` synchronously for low-latency
interactive chat. Long-running or batch agent work MUST use these tasks so
extraction workers are never blocked.
"""
from __future__ import annotations

import logging
import time

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=15,
    soft_time_limit=120,
    time_limit=180,
    queue="agents",
)
def run_agent_query(self, firm_id: int, user_id: int, query: str, agent_type: str | None = None):
    """Execute an Ask LedgerPro / agent turn off the request thread."""
    from accounts.models import User
    from agents.executor import execute_agent

    logger.info(
        "agents queue: firm=%s user=%s attempt=%s query=%r",
        firm_id, user_id, self.request.retries + 1, (query or "")[:80],
    )
    try:
        user = User.objects.get(pk=user_id)
        conv = execute_agent(
            firm_id=firm_id,
            user=user,
            query=query,
            agent_type=agent_type,
        )
        try:
            from common.llm_usage import record_llm_usage
            from firms.models import Firm

            firm = Firm.objects.filter(pk=firm_id).first()
            tier = "unknown"
            if firm and firm.created_by_id:
                from billing.entitlements import get_or_create_subscription
                tier = get_or_create_subscription(firm.created_by).tier
            record_llm_usage(
                firm_id=firm_id,
                tier=str(tier),
                operation="agent",
                model="deterministic-agent",
                input_tokens=max(len(query or "") // 4, 1),
                output_tokens=max(len(str(conv.response or "")) // 4, 1),
            )
        except Exception:
            logger.debug("llm_usage accounting skipped", exc_info=True)
        return {
            "conversation_id": str(conv.id),
            "agent_type": conv.agent_type,
            "latency_ms": conv.latency_ms,
        }
    except Exception as exc:
        logger.exception("Agent task failed firm=%s", firm_id)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise


@shared_task(
    bind=True,
    soft_time_limit=120,
    time_limit=180,
    queue="agents",
)
def simulate_slow_llm_turn(self, duration_sec: float = 2.0, label: str = "llm"):
    """Load-test helper: occupies an agents-queue worker without hitting a real LLM."""
    logger.info("simulate_slow_llm_turn start label=%s duration=%s", label, duration_sec)
    time.sleep(float(duration_sec))
    return {"label": label, "slept": duration_sec}
