# Scaling LedgerPro (Compose → queues → PgBouncer → Kubernetes)

This is the operational playbook for growing from the current Docker Compose
stack to multi-tenant production load **without** migrating to Kubernetes early.

## Current topology (Compose)

| Service | Role |
|---------|------|
| `db` | Postgres 16 (primary) |
| `redis` | Celery broker / results |
| `backend` | Django API |
| `celery_extraction` | Queue **`extraction`** — OCR / document Gemini (SLA) |
| `celery_risk` | Queue **`risk`** — recon, RiskEngine, forecast, scoring |
| `celery_agents` | Queue **`agents`** — Ask LedgerPro / LLM (`prefetch=1`, 120s/180s limits) |
| `celery_default` | Queue **`default`** — nightly fan-outs, FX |
| `celery_beat` | Periodic schedule |
| `frontend` | Next.js |

Task → queue map lives in `ledgerpro_backend/ledgerpro_backend/celery_queues.py`
and is loaded via `CELERY_TASK_ROUTES`.

**Rule:** never run a single worker with `-Q extraction,agents`. Shared processes
let long LLM calls starve extraction regardless of queue names.

---

## Why named queues

Document extraction is interactive UX (upload → `needs_review` in seconds).
Agent/LLM turns are latency-unbounded (15–180s). Putting both on one Celery
worker makes extraction p95 track agent backlog.

Isolation acceptance is covered by:

```bash
cd ledgerpro_backend
python scripts/test_queue_isolation.py
# or
pytest security/tests/test_queue_isolation.py -v
```

Extraction work must stay under the SLA even while the agents queue is saturated.

---

## Phase 1 — Stay on Compose (default)

Keep Compose while **all** of these hold:

- Active firms ≲ **150**
- Concurrent Celery workers fit on one VM (≤ ~8 containers)
- Postgres CPU \< **70%** sustained, connections \< **80**
- Extraction p95 \< **15s** under normal load
- Redis memory stable (no eviction of Celery messages)

Scale knobs without leaving Compose:

```bash
CELERY_EXTRACTION_CONCURRENCY=6
CELERY_AGENTS_CONCURRENCY=4
docker compose up -d --scale celery_extraction=2   # if you later parameterize replicas
```

Prefer vertical scale (bigger box + higher `-c`) before orchestration.

---

## Phase 2 — PgBouncer / read replicas (still Compose)

**Trigger:** Postgres `max_connections` pressure, or API+workers open
\> **60–80** concurrent DB sessions, or connection errors under upload spikes.

Enable the Compose profile (does not require Kubernetes):

```bash
docker compose --profile scale up -d
# Point Django at PgBouncer:
# DB_HOST=pgbouncer   (or DATABASE_URL=...@pgbouncer:5432/...)
# Use transaction pooling; disable server-side cursors / advisory locks that need session mode
```

**Read replicas** (managed Postgres: RDS / Cloud SQL / Neon):

| Trigger | Action |
|---------|--------|
| Dashboard/report read QPS dominates | Add replica; route `FinancialSnapshot` / list APIs via `DatabaseRouter` |
| Primary CPU \> 70% on reads | Same |
| Write path (extraction status updates) fine | Keep writes on primary only |

Do **not** put Celery result backends or advisory locks on a replica.

---

## Phase 3 — Kubernetes only when Compose is the bottleneck

**Do not migrate because it is fashionable.** Move when **two or more** apply:

1. You need **\> 1 host** of Celery capacity (agents + extraction) and Compose
   `scale` / manual VM cloning is error-prone.
2. Rolling deploys of workers block extraction for \> **5 minutes** regularly.
3. You need cluster autoscaling keyed on **queue depth**
   (`extraction` depth vs `agents` depth independently).
4. Multi-region or strict HA (pod anti-affinity, PDB) is a contractual SLA.
5. Ops time spent babysitting Compose \> time to maintain a small Helm chart.

**Non-triggers** (stay on Compose + managed DB/Redis):

- “We added AI features”
- Firm count under ~150 with healthy p95
- Desire for service mesh / Istio
- Single-region Render/Fly/VM is meeting SLOs

When you do migrate: one Deployment per queue (`extraction`, `risk`, `agents`,
`default`), same image as today, HPA on Redis queue length — **no** rewrite of
Django into microservices required (see ADR 0001).

---

## LLM API spend per firm / pricing tier

Landing tiers (INR/month): **Starter ₹2,499**, **Professional ₹7,499**,
**Enterprise ₹18,999**.

LLM cost is mostly Gemini extraction (+ future agent synthesis). Soft monthly
USD budgets used for alerting (see `common/llm_usage.py`):

| Tier | Soft LLM budget (USD/mo) | Intent |
|------|--------------------------|--------|
| Starter | ~$15 | ~500 invoice extractions |
| Professional | ~$75 | Multi-firm + agent chat |
| Enterprise | ~$400 | High volume + SLA headroom |

**Instrumentation:** call `record_llm_usage(firm_id=..., tier=..., operation=...)`
from extraction / agent call sites. Logs emit `llm_usage` / `llm_budget_exceeded`
for log drains or metrics.

**Ops checklist**

- Tag every Gemini request with `firm_id` + `tier` (custom header or log field).
- Weekly review: top 10 firms by `month_spend_usd` vs subscription margin.
- Enterprise: negotiated overage; Starter/Pro: rate-limit agent queue per firm
  when budget \> 80% (product decision — do not throttle **extraction**).
- Never charge extraction retries caused by 429/5xx against the customer’s
  fair-use budget without marking `operation=extraction_retry`.

---

## Extraction SLA under agent load

Target: **extraction p95 ≤ 15s** (mock/local) / ≤ provider RTT + 5s (prod) while
agents queue depth ≫ extraction depth.

Guarantees in this repo:

1. Separate Compose services per queue.
2. `CELERY_TASK_ROUTES` so `.delay()` cannot accidentally land on the wrong queue.
3. Agents workers: `--prefetch-multiplier=1 --soft-time-limit=120 --time-limit=180`.
4. Simulated isolation test: `scripts/test_queue_isolation.py`.

If extraction p95 regresses while agents are busy, check first that someone did
not start `celery ... -Q extraction,agents` on one process.
