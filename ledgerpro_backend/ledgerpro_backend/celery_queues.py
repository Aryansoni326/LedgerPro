"""
Celery task routing — named queues so slow AI/agent work cannot starve extraction.

Queues
------
extraction  Fast OCR / Gemini document extraction (SLA-sensitive)
risk        Reconciliation, risk scan, forecast, scoring, trade-finance
agents      Ask LedgerPro / LLM agent turns (unbounded latency)
default     Nightly fan-outs, FX, misc maintenance
"""

# Queue names — keep in sync with docker-compose.yml worker -Q flags
QUEUE_EXTRACTION = "extraction"
QUEUE_RISK = "risk"
QUEUE_AGENTS = "agents"
QUEUE_DEFAULT = "default"

ALL_QUEUES = (QUEUE_EXTRACTION, QUEUE_RISK, QUEUE_AGENTS, QUEUE_DEFAULT)

# Explicit task → queue map (also used by isolation tests)
TASK_ROUTES: dict[str, dict[str, str]] = {
    # ── Extraction (SLA-critical) ────────────────────────────────────
    "invoices.tasks.extract_invoice_data": {"queue": QUEUE_EXTRACTION},
    "trade_docs.tasks.extract_trade_doc_data": {"queue": QUEUE_EXTRACTION},
    "eway_bills.tasks.extract_eway_bill_data": {"queue": QUEUE_EXTRACTION},
    "intelligence.tasks.extract_purchase_order_data": {"queue": QUEUE_EXTRACTION},
    "intelligence.tasks.extract_bank_statement_data": {"queue": QUEUE_EXTRACTION},
    "intelligence.tasks.extract_contract_data": {"queue": QUEUE_EXTRACTION},
    "intelligence.tasks.extract_credit_note_data": {"queue": QUEUE_EXTRACTION},
    "intelligence.tasks.extract_debit_note_data": {"queue": QUEUE_EXTRACTION},
    # ── Risk / intelligence (CPU / DB heavy, may call LLM) ───────────
    "intelligence.tasks.run_reconciliation": {"queue": QUEUE_RISK},
    "intelligence.tasks.compute_cashflow_forecast": {"queue": QUEUE_RISK},
    "intelligence.tasks.compute_vendor_score_task": {"queue": QUEUE_RISK},
    "intelligence.tasks.compute_customer_score_task": {"queue": QUEUE_RISK},
    "intelligence.tasks.analyse_trade_finance": {"queue": QUEUE_RISK},
    "intelligence.tasks.scan_firm_risks": {"queue": QUEUE_RISK},
    # ── Agents / LLM turns ───────────────────────────────────────────
    "agents.tasks.run_agent_query": {"queue": QUEUE_AGENTS},
    "agents.tasks.simulate_slow_llm_turn": {"queue": QUEUE_AGENTS},
    # ── Default / maintenance ────────────────────────────────────────
    "intelligence.tasks.nightly_cashflow_forecast_all": {"queue": QUEUE_DEFAULT},
    "intelligence.tasks.nightly_score_all": {"queue": QUEUE_DEFAULT},
    "intelligence.tasks.nightly_trade_finance_all": {"queue": QUEUE_DEFAULT},
    "intelligence.tasks.nightly_exchange_rate_refresh": {"queue": QUEUE_DEFAULT},
    "intelligence.tasks.fetch_historical_exchange_rates": {"queue": QUEUE_DEFAULT},
    "accounts.tasks.test_celery_task": {"queue": QUEUE_DEFAULT},
}
