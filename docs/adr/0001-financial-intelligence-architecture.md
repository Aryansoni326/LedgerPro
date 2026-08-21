# ADR-0001: Financial Intelligence Platform Architecture

**Status:** Accepted  
**Date:** 2026-08-19  
**Authors:** Architecture Team  
**Deciders:** Engineering Lead, Product Lead

---

## Context

LedgerPro is a multi-tenant document management platform (Django 5 / DRF, Next.js 14, PostgreSQL 16, Celery + Redis 7) serving Indian accountants and firm owners. The current domain model centers on Firms, Bills (Invoices), ImportExportRecords (TradeDocuments), EwayBillRecords, CloudVault, and AuditLog.

We need to evolve this into a **Financial Intelligence Platform** with three new AI layers and an Agentic layer:

| Layer | Components |
|-------|-----------|
| **Document AI** | OCR extraction (existing), enhanced field extraction, document classification |
| **Financial AI** | Cash-flow prediction, financial health scoring, trend analysis |
| **Compliance AI** | GST compliance checks, regulatory risk detection, e-way bill validation |
| **Agentic Layer** | CFO Agent, Compliance Agent, Finance Agent, Audit Agent |
| **Action Engine** | Orchestrates agent recommendations into actionable workflows |

---

## Decision 1: Financial Relationship Graph — Postgres with Recursive CTEs (not Neo4j)

### Decision

Store the Financial Relationship Graph in **PostgreSQL 16 using adjacency-list tables and recursive CTEs**, not a dedicated graph store (Neo4j) or the AGE extension.

### Justification

| Factor | PostgreSQL | Neo4j / AGE |
|--------|-----------|-------------|
| **Ops overhead** | Zero — already running PG 16 | New service in Docker Compose, backups, monitoring, HA |
| **Team skill** | Team knows SQL + Django ORM | Requires Cypher training, new ORM/driver |
| **Transactional consistency** | Single DB — firm-scoped FK constraints, ACID with existing models | Two-phase commit or eventual consistency across stores |
| **Graph query depth** | Firm-scoped graphs are small (hundreds–low thousands of nodes per firm); recursive CTEs handle 5–8 hop traversals in <50ms | Needed only for billions of edges or 20+ hop traversals |
| **Migration risk** | Django migrations, existing tooling | Separate migration system, data sync pipeline |
| **Future escape hatch** | If graph complexity explodes, AGE extension is a Postgres plugin — no data migration needed | N/A |

**Recommendation:** Start with Postgres. The relationship graph is firm-scoped (bounded subgraphs), so we never hit global-scale graph problems. If we later need advanced graph algorithms (community detection, PageRank across firms), AGE can be added as a Postgres extension without moving data.

### Schema sketch

```
┌──────────┐       ┌───────────────────┐       ┌──────────┐
│  Vendor   │──M:N──│ Transaction        │──M:N──│ Customer  │
└──────────┘       │  (amount, date,    │       └──────────┘
                   │   type, status)    │
                   └────────┬──────────┘
                            │ FK
                   ┌────────▼──────────┐
                   │ ReconciliationLink │
                   │  invoice_id        │
                   │  payment_id        │
                   │  purchase_order_id │
                   │  bank_txn_id       │
                   │  match_confidence  │
                   └───────────────────┘
```

---

## Decision 2: Separation of AI Extraction (Module 1) vs. AI Reasoning (Modules 2–4)

### Decision

AI extraction and AI reasoning run in **separate Celery queues** within the same Django process, not as separate microservices.

### Architecture

```
                        ┌─────────────────────────────────────────────┐
                        │              Django Backend                  │
                        │                                             │
  Upload ──► Celery     │  Queue: "extraction"        Queue: "ai"    │
             Worker     │  ┌──────────────┐      ┌─────────────────┐ │
             Pool       │  │ extract_*    │      │ score_risk      │ │
                        │  │ (Gemini OCR) │      │ predict_cashflow│ │
                        │  │ ~2-10s       │──X──►│ check_compliance│ │
                        │  └──────────────┘      │ ~15-60s (LLM)  │ │
                        │                        └─────────────────┘ │
                        └─────────────────────────────────────────────┘
                                   │                      │
                              extraction              ai-reasoning
                              worker(s)               worker(s)

  ──X──► means: extraction tasks NEVER call reasoning tasks synchronously.
         Reasoning is triggered by a post-extraction signal or separate API call.
```

### Key rules

1. **Four Celery queues:** `extraction` (OCR, SLA-bound), `risk` (recon / RiskEngine / forecast), `agents` (Ask LedgerPro / LLM, unbounded), `default` (nightly / FX). See `docs/SCALING.md` and `docker-compose.yml`.
2. **Separate worker pools:** one Compose service (or K8s Deployment) per queue — never `-Q extraction,agents` on a single process.
3. **No synchronous chaining:** Extraction tasks never `.get()` or `chain()` into reasoning/agent tasks.
4. **Circuit breaker:** Agent tasks use `soft_time_limit=120, time_limit=180` so a hung LLM call cannot block the agents worker forever.
5. **Same Django codebase:** All queues share one image; scale by adding worker replicas, not new services.

### Why not a separate microservice?

- Team size does not justify the operational cost of a second deployable, separate CI/CD, inter-service auth, and API gateway.
- Django's Celery integration already provides queue isolation, retry policies, and monitoring.
- If LLM call volume grows 10×, we can split the `ai_reasoning` worker into its own Docker service with zero code changes (just a new Compose service pointing at the same codebase).

---

## Decision 3: Versioned Internal API Contract (Django App, not Microservice)

### Decision

Create a new Django app `intelligence` that exposes a **versioned internal Python API** (service layer) consumed by views and Celery tasks. No REST boundary between Django and "AI orchestration" — it's a module boundary within the monolith.

### Contract

```python
# intelligence/services.py  — v1 internal API

class IntelligenceService:
    """Versioned internal API for AI operations. All methods are firm-scoped."""

    VERSION = "1.0"

    @staticmethod
    def extract_document(firm_id: int, document_type: str, document_id: int) -> dict:
        """Enqueue extraction. Returns {'task_id': str, 'status': 'queued'}."""

    @staticmethod
    def score_risk(firm_id: int, entity_type: str, entity_id: int) -> dict:
        """Enqueue risk scoring. Returns {'task_id': str, 'status': 'queued'}."""

    @staticmethod
    def predict_cashflow(firm_id: int, horizon_days: int = 90) -> dict:
        """Enqueue cash-flow prediction. Returns {'task_id': str, 'status': 'queued'}."""

    @staticmethod
    def check_compliance(firm_id: int, document_ids: list[int]) -> dict:
        """Enqueue compliance check. Returns {'task_id': str, 'status': 'queued'}."""

    @staticmethod
    def get_task_result(task_id: str) -> dict:
        """Poll task status. Returns {'status': str, 'result': dict | None}."""

    @staticmethod
    def get_financial_snapshot(firm_id: int) -> dict:
        """Synchronous read from cached FinancialSnapshot. No LLM call."""
```

### Why a Python module boundary, not REST?

- Same process = no serialization overhead, no network latency, no auth between services.
- The `IntelligenceService` class is the **seam**. If we later extract a microservice, the REST API mirrors this interface 1:1.
- Versioning is explicit (`VERSION = "1.0"`); breaking changes bump the version and old callers use the old class until migrated.

### When to extract to a real service

Extract when ANY of these are true:
- AI reasoning needs a different runtime (e.g., GPU worker, Python 3.13 while Django is on 3.12)
- The team grows to 3+ engineers working independently on the AI layer
- AI reasoning needs independent scaling (>10× current load)

---

## Decision 4: Celery Task Structure Changes

### Current state

- Single default queue, all tasks (extraction) run on it.
- Tasks: `extract_invoice_data`, `extract_trade_doc_data`, `extract_eway_bill_data` (all with `max_retries=6`).

### New structure

```python
# settings.py additions
CELERY_TASK_QUEUES = {
    'extraction': {'exchange': 'extraction', 'routing_key': 'extraction'},
    'ai_reasoning': {'exchange': 'ai_reasoning', 'routing_key': 'ai_reasoning'},
    'ai_periodic': {'exchange': 'ai_periodic', 'routing_key': 'ai_periodic'},
}

CELERY_TASK_ROUTES = {
    'invoices.tasks.extract_*': {'queue': 'extraction'},
    'trade_docs.tasks.extract_*': {'queue': 'extraction'},
    'eway_bills.tasks.extract_*': {'queue': 'extraction'},
    'intelligence.tasks.score_*': {'queue': 'ai_reasoning'},
    'intelligence.tasks.predict_*': {'queue': 'ai_reasoning'},
    'intelligence.tasks.check_*': {'queue': 'ai_reasoning'},
    'intelligence.tasks.refresh_*': {'queue': 'ai_periodic'},
}

CELERY_BEAT_SCHEDULE = {
    'nightly-risk-rescore': {
        'task': 'intelligence.tasks.refresh_risk_scores',
        'schedule': crontab(hour=2, minute=0),
    },
    'hourly-snapshot-refresh': {
        'task': 'intelligence.tasks.refresh_financial_snapshots',
        'schedule': crontab(minute=0),
    },
}
```

### New tasks (in `intelligence/tasks.py`)

| Task | Queue | Time Limit | Retries | Notes |
|------|-------|-----------|---------|-------|
| `score_risk_for_entity` | `ai_reasoning` | soft=120s, hard=180s | 3 | Per-vendor/customer risk score |
| `predict_cashflow` | `ai_reasoning` | soft=120s, hard=180s | 2 | 90-day forecast per firm |
| `check_compliance_batch` | `ai_reasoning` | soft=300s, hard=360s | 2 | Batch of documents |
| `refresh_risk_scores` | `ai_periodic` | soft=600s, hard=720s | 1 | Nightly full rescore |
| `refresh_financial_snapshots` | `ai_periodic` | soft=300s, hard=360s | 1 | Hourly snapshot cache |
| `reconcile_transactions` | `ai_reasoning` | soft=120s, hard=180s | 2 | Smart matching |

### Docker Compose changes

```yaml
# Add to docker-compose.yml
celery_ai_worker:
  build: ./ledgerpro_backend
  container_name: ledgerpro_celery_ai
  command: celery -A ledgerpro_backend worker -Q ai_reasoning,ai_periodic -c 2 --prefetch-multiplier=1 -l info
  volumes: [./ledgerpro_backend:/app]
  env_file: [.env]
  environment: [DB_HOST=db, REDIS_URL=redis://redis:6379/0]
  depends_on: {db: {condition: service_healthy}, redis: {condition: service_healthy}}

celery_beat:
  build: ./ledgerpro_backend
  container_name: ledgerpro_celery_beat
  command: celery -A ledgerpro_backend beat -l info
  volumes: [./ledgerpro_backend:/app]
  env_file: [.env]
  environment: [DB_HOST=db, REDIS_URL=redis://redis:6379/0]
  depends_on: {db: {condition: service_healthy}, redis: {condition: service_healthy}}
```

---

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Next.js 14 Frontend                         │
│  Dashboard │ Risk View │ Cash-flow │ Reconciliation │ Agent Chat    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ REST API (DRF)
┌──────────────────────────────▼──────────────────────────────────────┐
│                      Django 5 Backend (Monolith)                    │
│                                                                     │
│  ┌─────────┐ ┌─────────┐ ┌───────────┐ ┌─────────┐ ┌───────────┐ │
│  │ firms   │ │invoices │ │trade_docs │ │eway_bills│ │  vault    │ │
│  └─────────┘ └─────────┘ └───────────┘ └─────────┘ └───────────┘ │
│  ┌─────────┐ ┌─────────┐ ┌─────────────────────────────────────┐  │
│  │ audit   │ │accounts │ │         intelligence (NEW)           │  │
│  └─────────┘ └─────────┘ │  services.py  ── Internal API v1    │  │
│                           │  tasks.py     ── AI Celery tasks    │  │
│                           │  models.py    ── Vendor, Customer,  │  │
│                           │                  Transaction,       │  │
│                           │                  RiskSignal,         │  │
│                           │                  FinancialSnapshot,  │  │
│                           │                  ReconciliationLink  │  │
│                           └─────────────────────────────────────┘  │
│                                                                     │
│  Celery Queues:                                                     │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ extraction │  │ ai_reasoning │  │  ai_periodic  │               │
│  │ (OCR, fast)│  │ (LLM, slow)  │  │ (cron jobs)  │               │
│  └────────────┘  └──────────────┘  └──────────────┘               │
└───────────┬──────────────┬──────────────┬───────────────────────────┘
            │              │              │
     ┌──────▼──────┐ ┌────▼────┐  ┌──────▼──────┐
     │ PostgreSQL  │ │  Redis  │  │ Gemini /    │
     │ 16          │ │  7      │  │ LLM API     │
     │ (all data + │ │ (broker │  │ (external)  │
     │  graph)     │ │+ cache) │  │             │
     └─────────────┘ └─────────┘  └─────────────┘
```

---

## Out of Scope for MVP

The following are explicitly **NOT** in scope for the MVP release:

1. **Neo4j or AGE extension** — Postgres-only for the relationship graph. Re-evaluate at 10K+ firms.
2. **Agentic Layer (CFO Agent, Compliance Agent, Finance Agent, Audit Agent)** — Build the data models and AI tasks first; agents come in Phase 2.
3. **Action Engine** — Depends on the Agentic Layer; Phase 3.
4. **Real-time streaming** — AI results are polled or pushed via periodic refresh, not WebSocket-streamed.
5. **Multi-LLM orchestration** — MVP uses a single LLM provider (Gemini). Multi-model routing is a future optimization.
6. **Cross-firm analytics** — All AI operates within a single firm's data boundary. Aggregate insights across firms require explicit consent and a separate data pipeline.
7. **Custom ML model training** — MVP uses prompt-based LLM reasoning, not fine-tuned models.
8. **Separate AI microservice** — Stays as a Django app. Extract only when the criteria in Decision 3 are met.
9. **Advanced graph algorithms** (PageRank, community detection) — Not needed until vendor network analysis across firms.
10. **Bank API integrations** — Bank transactions are manually imported (CSV/Excel) in MVP; open-banking APIs are Phase 2.
11. **Celery Beat in production** — For MVP, periodic tasks can be triggered by cron or manual API calls; Beat deployment is optional.
12. **Frontend for Agent Chat** — Backend-only for AI features in MVP; the dashboard surfaces scores and predictions, not conversational UI.

---

## Consequences

- **Positive:** No new infrastructure; all new code lives in a single new Django app. Team can ship incrementally.
- **Positive:** Queue isolation means a 60-second LLM call never delays a 3-second OCR extraction.
- **Positive:** Clear internal API seam (`IntelligenceService`) makes future microservice extraction trivial.
- **Negative:** Postgres recursive CTEs are less expressive than Cypher for deep graph traversals — acceptable given firm-scoped data.
- **Negative:** Single-process monolith means a bad AI task deployment can affect extraction. Mitigated by queue isolation and separate worker processes.

---

## References

- Existing codebase: `firms/access.py` (multi-tenancy pattern), `invoices/tasks.py` (Celery extraction pattern)
- PostgreSQL recursive CTE documentation: https://www.postgresql.org/docs/16/queries-with.html
- Celery task routing: https://docs.celeryq.dev/en/stable/userguide/routing.html
