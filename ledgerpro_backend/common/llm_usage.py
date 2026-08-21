"""
Per-firm LLM / Gemini usage accounting for cost monitoring by pricing tier.

Wire ``record_llm_usage`` from extraction and agent call sites. Aggregates are
logged and stored in-process for local dashboards; production should ship the
same payload to your metrics backend (Prometheus / Datadog / BigQuery).

Pricing tiers (landing page, INR / month):
  Starter       ₹2,499  — up to 3 firms, 500 invoices
  Professional  ₹7,499  — up to 15 firms, unlimited invoices
  Enterprise    ₹18,999 — unlimited firms, SLA

See docs/SCALING.md for recommended monthly token budgets and alert thresholds.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

logger = logging.getLogger(__name__)

Tier = Literal["starter", "professional", "enterprise", "unknown"]

# Soft monthly USD spend ceilings used for alerts (tune with real Gemini pricing).
# These are *cost floors for paging*, not hard product limits.
TIER_MONTHLY_LLM_BUDGET_USD: dict[str, Decimal] = {
    "starter": Decimal("15.00"),       # ~500 invoice extractions
    "professional": Decimal("75.00"),  # multi-firm + agent chat
    "enterprise": Decimal("400.00"),   # high volume + SLA headroom
    "unknown": Decimal("25.00"),
}


@dataclass
class LLMUsageEvent:
    firm_id: int
    tier: str
    operation: str          # extraction | agent | risk_reasoning
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: Decimal = Decimal("0")
    day: str = field(default_factory=lambda: date.today().isoformat())


_lock = threading.Lock()
# (firm_id, YYYY-MM) -> spend USD
_monthly_spend: dict[tuple[int, str], Decimal] = {}


def estimate_gemini_flash_cost(input_tokens: int, output_tokens: int) -> Decimal:
    """Rough Gemini Flash-class estimate — update when provider pricing changes."""
    # Placeholder rates (USD / 1M tokens). Prefer live price cards in ops runbooks.
    in_rate = Decimal("0.10") / Decimal("1000000")
    out_rate = Decimal("0.40") / Decimal("1000000")
    return (Decimal(input_tokens) * in_rate + Decimal(output_tokens) * out_rate).quantize(
        Decimal("0.000001")
    )


def record_llm_usage(
    *,
    firm_id: int,
    tier: str = "unknown",
    operation: str,
    model: str = "gemini",
    input_tokens: int = 0,
    output_tokens: int = 0,
    estimated_cost_usd: Decimal | None = None,
) -> LLMUsageEvent:
    """Record one LLM call. Emits a structured log line for log-based billing."""
    cost = estimated_cost_usd
    if cost is None:
        cost = estimate_gemini_flash_cost(input_tokens, output_tokens)

    event = LLMUsageEvent(
        firm_id=firm_id,
        tier=(tier or "unknown").lower(),
        operation=operation,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=cost,
    )

    month_key = date.today().strftime("%Y-%m")
    with _lock:
        bucket = (firm_id, month_key)
        _monthly_spend[bucket] = _monthly_spend.get(bucket, Decimal("0")) + cost
        month_total = _monthly_spend[bucket]

    budget = TIER_MONTHLY_LLM_BUDGET_USD.get(event.tier, TIER_MONTHLY_LLM_BUDGET_USD["unknown"])
    logger.info(
        "llm_usage firm_id=%s tier=%s op=%s model=%s in=%s out=%s cost_usd=%s month_usd=%s budget_usd=%s",
        event.firm_id,
        event.tier,
        event.operation,
        event.model,
        event.input_tokens,
        event.output_tokens,
        event.estimated_cost_usd,
        month_total,
        budget,
        extra={"llm_usage": asdict(event), "month_spend_usd": str(month_total)},
    )
    if month_total >= budget:
        logger.warning(
            "llm_budget_exceeded firm_id=%s tier=%s month_usd=%s budget_usd=%s",
            firm_id, event.tier, month_total, budget,
        )
    return event


def get_firm_month_spend(firm_id: int, month: str | None = None) -> Decimal:
    month_key = month or date.today().strftime("%Y-%m")
    with _lock:
        return _monthly_spend.get((firm_id, month_key), Decimal("0"))


def reset_usage_for_tests() -> None:
    with _lock:
        _monthly_spend.clear()
