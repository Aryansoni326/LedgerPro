# Hackathon demo — re-run minutes before presenting

From `ledgerpro_backend/`:

```bash
# Windows PowerShell
$env:USE_SQLITE='True'
python manage.py migrate
python manage.py seed_demo_firm
python manage.py seed_demo_firm --verify-only
```

**Login:** `demo@ledgerpro.demo` / `DemoPass123!` (accountant — can approve agent actions)  
**Viewer:** `owner@ledgerpro.demo` / `DemoPass123!` (read-only)

### Live narrative (real data paths)

1. **147 documents** — `Bill` + `Document` rows for the demo firm (not a fake counter).
2. **Fraud detected** — `RiskEngine.scan` finds duplicate invoices, unusual amount, vendor bank-account change.
3. **Cash-flow risk** — `CashFlowForecaster` produces a real `pressure_day` from overdue A/R + large payables; `cash_flow_risk` signal stored.
4. **Agent recommends** — Ask: *“Flag the suspicious duplicate invoice for review”* → `flag_transaction` PendingApproval (auto-targets open risk txn).
5. **Approve → executed** — Approve in UI as `demo@…` → `process_approval` writes `transaction.metadata.flagged`.

Re-run `seed_demo_firm` anytime; it wipes prior demo rows and reseeds idempotently.
