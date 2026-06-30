# LedgerPro Security Model

This document describes how LedgerPro protects accountant workspaces and client financial data.

## Authentication

LedgerPro uses a **two-step login**:

1. **Google OAuth** (or dev-only mock token when `DEBUG=True`) establishes identity.
2. **Email OTP (4-digit)** completes 2FA before a session token is issued.

Session tokens are **Django-signed payloads** (not JWTs), passed as `Authorization: Bearer <token>`. They expire after 7 days. The server validates the signature, expiry, and that the user account is still active on every API request (`accounts.authentication.SignedTokenAuthentication`).

**Production note:** Mock Google login (`mock_dev_token_*`) is rejected when `DEBUG=False`.

## Authorization & data isolation

Access model: **one accountant owns many firms; each firm is private to its creator.**

- Every `Firm` has `created_by → User`.
- `HasFirmAccess` permission checks `obj.created_by == request.user`.
- All firm-scoped endpoints resolve the firm (or parent firm of a bill/trade doc/vault entry) and return **HTTP 403** if the authenticated user is not the creator.

There is no shared-firm or delegated-access model in v2. Guessing another firm's numeric ID does not grant access.

### Isolation enforcement points

| Resource | Check |
|----------|--------|
| Firm list | `Firm.objects.filter(created_by=request.user)` |
| Firm-scoped routes (`/api/firms/{id}/…`) | `get_firm_or_403()` |
| Bills, trade docs, vault entries by PK | Load object → verify `object.firm.created_by` |

Run the isolation probe:

```bash
cd ledgerpro_backend
python scripts/test_cross_firm_access.py
# or
python manage.py test security.tests.test_security.CrossFirmIsolationTests
```

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

- **Who** — accountant user
- **What** — resource type (`bill`, `import_export_record`, `eway_bill_record`) and ID
- **Action** — `upload`, `edit`, `delete`, `verify`, `export`, `retry_extraction`
- **When** — UTC timestamp
- **Context** — optional JSON details, client IP

Logged on upload, inline edit, verify, delete, export, and retry for bills and trade documents; e-way bill stub uploads and vault-driven deletes are also logged.

Audit rows are append-only from application code (no update/delete API).

## Storage & transport

- Files stored in Cloudflare R2 (production) or local `media/` (development).
- **Do not serve `/media/` publicly in production** — use signed URLs or authenticated proxy; `DEBUG=True` enables local media for dev only.
- Configure `CORS_ALLOWED_ORIGINS` explicitly in production (`CORS_ALLOW_ALL_ORIGINS` is dev-only).

## Security testing

```bash
cd ledgerpro_backend
python manage.py test security.tests.test_security
python scripts/test_cross_firm_access.py
```

## Known limitations (v2)

- No per-firm RBAC (single owner per firm).
- OTP space is small; rate limits are essential — monitor `OTPRateLimitEvent` in production.
- No virus scanning on uploads.
- Session tokens cannot be revoked server-side without changing `SECRET_KEY` (rotation invalidates all sessions).
