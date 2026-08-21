# LedgerPro Security Model

This document describes how LedgerPro protects accountant workspaces, client financial data, and agent-generated actions in a multi-tenant SaaS model.

## Authentication

LedgerPro uses a **two-step login**:

1. **Google OAuth** (or dev-only mock token when `DEBUG=True`) establishes identity.
2. **Email OTP (4-digit)** completes 2FA before a session token is issued.

Session tokens are **Django-signed payloads** (not JWTs), passed as `Authorization: Bearer <token>`. They expire after 7 days. The server validates the signature, expiry, and that the user account is still active on every API request (`accounts.authentication.SignedTokenAuthentication`).

**Production note:** Mock Google login (`mock_dev_token_*`) is rejected when `DEBUG=False`.

## Authorization & data isolation

Access model: **one accountant owns many firms; each firm is private to its creating accountant.**

- Every `Firm` has `created_by → User`.
- `HasFirmAccess` allows:
  - the creating accountant full access
  - the matched `owner_email` user read-only access
- All firm-scoped endpoints resolve the firm (or the parent firm of a child record) through shared helpers in `firms/access.py`.
- Unsafe operations additionally call `assert_can_write_firm(...)`, so view access never implies write approval.

There is no delegated cross-accountant access model. Guessing another firm's numeric ID or a UUID-backed agent/session/approval ID does not grant access.

### Isolation enforcement points

| Resource | Check |
|----------|--------|
| Firm list | `firms_queryset_for_user(request.user)` |
| Firm-scoped routes (`/api/firms/{id}/…`) | `get_firm_or_403()` |
| Bills, trade docs, e-way bills, vault entries by PK | `get_*_for_user()` helpers in `firms/access.py` |
| Intelligence models by PK | `get_document_for_user`, `get_vendor_for_user`, `get_customer_for_user`, `get_transaction_for_user`, `get_risk_signal_for_user`, `get_reconciliation_*_for_user`, `get_financial_snapshot_for_user`, `get_*_score_for_user`, `get_trade_finance_link_for_user` |
| Agent models by UUID / PK | `get_agent_conversation_for_user`, `get_agent_action_for_user`, `get_pending_approval_for_user`, `get_chat_session_for_user` |

### Model coverage

The automated security suite covers all firm-scoped models introduced in Phases 0–10:

- `Document`
- `Vendor`
- `Customer`
- `Transaction`
- `RiskSignal`
- `ReconciliationLink`
- `ReconciliationException`
- `ReconciliationRun`
- `FinancialSnapshot`
- `VendorScore`
- `CustomerScore`
- `TradeFinanceLink`
- `AgentConversation`
- `AgentAction`
- `PendingApproval` (referred to in some product docs as “Proposed Action”)
- `ChatSession`

`ExchangeRate` is intentionally excluded from cross-firm checks because it is a global reference table with no tenant ownership.

Run the isolation probe:

```bash
cd ledgerpro_backend
python scripts/test_cross_firm_access.py
# or
python manage.py test security.tests.test_security
```

## Agent / AI isolation review

The agent orchestration layer was reviewed specifically for cross-firm context leakage and tenant bleed:

- `POST /api/firms/{firm_id}/agent/query/` and `POST /api/firms/{firm_id}/ask/` both resolve the requesting firm before execution.
- All agent tools receive `firm_id` from server-side orchestration, not from client-controlled request JSON.
- `ChatSession` reuse is bound to `(session_id, firm, user)`, so a session from Firm A cannot be reused against Firm B’s request context.
- Agent approvals are bound to the approval’s `firm`; write executors re-resolve target resources inside that firm before mutating.
- Financial forecast “cache” is stored as firm-scoped `FinancialSnapshot` rows, not in a shared tenant-agnostic cache entry.
- Graph traversal APIs now resolve linked vendors/customers with `firm_id` filters as an additional hardening step.

Security conclusion: **no validated cross-firm leak was found in the new AI/agent endpoints or their context-window/cache path**. Session isolation and server-side firm scoping are covered by automated tests.

## OTP brute-force protection

OTP codes are **4 digits** but guessing is mitigated by layered limits:

| Control | Limit |
|---------|--------|
| Per-session attempts | 5 wrong codes → session locked |
| Per-IP verify attempts | 15 / 15 minutes → HTTP 429 |
| Per-email failed verifications | 10 / 60 minutes → HTTP 429 |
| OTP resend (per email) | 3 / 10 minutes |
| OTP resend (per IP) | 10 / 15 minutes |
| Login / OTP issuance (per IP) | 10 / 15 minutes |
| Code expiry | 5 minutes per session |

OTP hashes use **HMAC-SHA256** with `SECRET_KEY` and a per-session salt (`pending_token`). Comparison uses `hmac.compare_digest` (constant-time).

Firm owner verification (`/api/firms/{id}/verify-otp`) uses the same lockout helper as login OTP.

## File upload validation

All user uploads are validated **server-side** in `common.upload_validation`:

1. **Extension whitelist** — invoices/trade docs: `.pdf`, `.jpg`, `.jpeg`, `.png`; stub uploads also allow `.xlsx`.
2. **Size cap** — 10 MB hard limit (chunked read, not client `Content-Length` alone).
3. **Magic-byte sniffing** — file content must match declared type (e.g. `%PDF` for PDF, `PK\x03\x04` for XLSX).

Client-side checks in the frontend are UX only; the API rejects invalid files independently.

## Audit logging

Immutable `AuditLog` records (`audit` app) capture:

- **Who** — authenticated user
- **What** — resource type (`bill`, `import_export_record`, `eway_bill_record`, `document`, `transaction`, `risk_signal`, `agent_approval`) and ID
- **Action** — `upload`, `edit`, `delete`, `verify`, `export`, `retry_extraction`, `approve_agent_action`, `reject_agent_action`
- **When** — UTC timestamp
- **Context** — optional JSON details, client IP

Coverage includes:

- upload, inline edit, verify, delete, export, and retry for bills and trade documents
- e-way bill stub uploads and vault-driven deletes
- approval/rejection of agent proposals
- the underlying resource mutation for approved agent writes (`transaction` / `risk_signal`) with `via: agent_approval` metadata

`FirmAccessLog` records owner-visible firm access events and remains the source for firm activity feeds.

Audit rows are append-only from application code (no update/delete API).

## Storage & transport

- Files stored in Cloudflare R2 (production) or local `media/` (development).
- **Do not serve `/media/` publicly in production** — use signed URLs or authenticated proxy; `DEBUG=True` enables local media for dev only.
- Configure `CORS_ALLOWED_ORIGINS` explicitly in production (`CORS_ALLOW_ALL_ORIGINS` is dev-only).

## Security testing

```bash
cd ledgerpro_backend
python manage.py test security.tests.test_security agents.tests intelligence.tests
python scripts/test_cross_firm_access.py
```

## Known limitations (v2)

- No per-firm RBAC beyond accountant-vs-owner access mode.
- OTP space is small; rate limits are essential — monitor `OTPRateLimitEvent` in production.
- No virus scanning on uploads.
- Session tokens cannot be revoked server-side without changing `SECRET_KEY` (rotation invalidates all sessions).
