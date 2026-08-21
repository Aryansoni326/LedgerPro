# Intelligence Module — ER Diagram & Indexing Strategy

## ER Diagram

```
┌─────────────────────┐
│       Firm           │  (existing — firms.Firm)
│  id, name, gstin,   │
│  state, city, ...   │
└──────────┬──────────┘
           │ 1
           │
     ┌─────┼──────────────────┬──────────────────┬────────────────────┐
     │     │                  │                  │                    │
     ▼ M   ▼ M               ▼ M               ▼ M                  ▼ M
┌─────────┐ ┌──────────┐ ┌───────────────┐ ┌───────────────┐ ┌──────────────────┐
│ Vendor  │ │ Customer │ │  Transaction  │ │  RiskSignal   │ │FinancialSnapshot │
│─────────│ │──────────│ │───────────────│ │───────────────│ │──────────────────│
│ id      │ │ id       │ │ id            │ │ id            │ │ id               │
│ firm_id │ │ firm_id  │ │ firm_id       │ │ firm_id       │ │ firm_id          │
│ name    │ │ name     │ │ txn_type      │ │ severity      │ │ snapshot_type    │
│ gstin   │ │ gstin    │ │ direction     │ │ category      │ │ snapshot_date    │
│ pan     │ │ pan      │ │ status        │ │ status        │ │ total_receivables│
│ email   │ │ email    │ │ amount        │ │ title         │ │ total_payables   │
│ phone   │ │ phone    │ │ currency      │ │ description   │ │ net_cash_flow    │
│ address │ │ address  │ │ txn_date      │ │ confidence    │ │ overdue_*        │
│ metadata│ │ metadata │ │ due_date      │ │ entity_type   │ │ health_score     │
│is_deleted│ │is_deleted│ │ reference_no  │ │ entity_id     │ │ cashflow_forecast│
│deleted_at│ │deleted_at│ │ vendor_id ──FK│ │ vendor_id ──FK│ │ breakdown        │
│created_at│ │created_at│ │ customer_id FK│ │ customer_id FK│ │ is_deleted       │
│updated_at│ │updated_at│ │ bill_id ────FK│ │ resolved_by   │ │ created_at       │
└─────────┘ └──────────┘ │ trade_doc_id FK│ │ resolved_at   │ └──────────────────┘
     ▲           ▲       │ eway_bill_id FK│ │ ai_reasoning  │
     │           │       │ description   │ └───────────────┘
     │           │       │ metadata      │
     │           │       │ is_deleted    │
     │           │       └───────┬───────┘
     │           │               │ 1
     │           │               │
     │           │       ┌───────▼──────────────┐
     │           │       │ ReconciliationLink    │
     │           │       │──────────────────────│
     │           │       │ id                   │
     │           │       │ firm_id              │
     │           │       │ match_group (UUID)   │
     │           │       │ transaction_id ───FK │
     │           │       │ matched_txn_id ──FK  │
     │           │       │ match_confidence     │
     │           │       │ match_method         │
     │           │       │ matched_by (user FK) │
     │           │       │ notes                │
     │           │       │ is_deleted           │
     │           │       └──────────────────────┘
     │           │
     │           │    ┌──────────────────────────────────────────────┐
     │           │    │        Existing Models (unchanged)           │
     │           │    │                                              │
     └───FK──────┼────│  invoices.Bill ◄── Transaction.bill_id      │
                 │    │  trade_docs.ImportExportRecord ◄── .trade_doc│
                 │    │  eway_bills.EwayBillRecord ◄── .eway_bill   │
                 │    │  vault.CloudVaultEntry  (no changes)        │
                 │    │  audit.AuditLog         (no changes)        │
                 │    └──────────────────────────────────────────────┘
```

### Relationship Summary

| Relationship | Type | Notes |
|---|---|---|
| Firm → Vendor | 1:M | Every vendor belongs to one firm |
| Firm → Customer | 1:M | Every customer belongs to one firm |
| Firm → Transaction | 1:M | All transactions are firm-scoped |
| Transaction → Vendor | M:1 | Optional — not all txns have a vendor |
| Transaction → Customer | M:1 | Optional — not all txns have a customer |
| Transaction → Bill | M:1 | Optional link to existing invoice |
| Transaction → ImportExportRecord | M:1 | Optional link to existing trade doc |
| Transaction → EwayBillRecord | M:1 | Optional link to existing e-way bill |
| Transaction ↔ Transaction (via ReconciliationLink) | M:M | Pairs of matched transactions in a reconciliation group |
| Firm → RiskSignal | 1:M | AI-generated risk indicators |
| RiskSignal → Vendor/Customer | M:1 | Optional link to flagged entity |
| Firm → FinancialSnapshot | 1:M | Periodic computed summaries |

---

## Indexing Strategy for RiskSignal

The `RiskSignal` table is the **most query-heavy** table in the intelligence module, powering the real-time risk dashboard. Four indexes are defined:

### 1. `idx_risk_dashboard` — `(firm, status, severity, -created_at)`

**Purpose:** The primary dashboard query: "Show me all open signals for this firm, most severe first, newest first."

```sql
SELECT * FROM intelligence_risksignal
WHERE firm_id = %s AND status = 'open' AND is_deleted = false
ORDER BY severity DESC, created_at DESC
LIMIT 50;
```

This composite index covers the WHERE clause and ORDER BY in a single B-tree scan. The descending `created_at` component avoids a sort step.

### 2. `idx_risk_category` — `(firm, category, status)`

**Purpose:** Category drill-downs: "Show all GST mismatch signals" or "How many unresolved vendor risk signals?"

```sql
SELECT category, COUNT(*) FROM intelligence_risksignal
WHERE firm_id = %s AND status = 'open' AND is_deleted = false
GROUP BY category;
```

### 3. `idx_risk_entity` — `(entity_type, entity_id)`

**Purpose:** Generic foreign-key lookup: "Show all risk signals for Invoice #42" or "All signals for Vendor #7." Enables the detail-page sidebar widget.

### 4. `idx_risk_timeline` — `(firm, created_at)`

**Purpose:** Time-series charts on the dashboard: "Risk signals over the last 90 days." Enables efficient range scans.

### Why not a GIN index on `ai_reasoning`?

The `ai_reasoning` JSONB field stores raw LLM output for auditability. It is **not queried** in dashboard flows — only read when a user drills into a specific signal. A GIN index would add write overhead with no read benefit. If we later add JSONB filtering (e.g., searching by model version), we can add a partial GIN index then.

### Partitioning note

If `RiskSignal` exceeds ~10M rows (unlikely per-firm but possible in aggregate), consider range-partitioning by `created_at` month. Postgres 16 native partitioning makes this a non-disruptive migration.
