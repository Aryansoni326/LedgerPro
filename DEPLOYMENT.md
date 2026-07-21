# Deploy LedgerPro on Vercel + Neon (Hobby-friendly)

You can use **one** project (both) or **two** projects (more reliable on Hobby).

## Recommended on Hobby: 2 projects (most reliable)

### A) Frontend — `ledger-pro` (or `ledger-pro-web`)

1. Vercel → project → **Settings → General → Root Directory** = `ledgerpro_frontend`
2. Env:
   ```
   NEXT_PUBLIC_API_URL=https://ledger-pro-api.vercel.app
   ```
   (use your real API URL)
3. Redeploy

### B) Backend — `ledger-pro-api`

1. **Root Directory** = `ledgerpro_backend`
2. Import env from `.env.vercel` (DATABASE_URL, SECRET_KEY, OAuth, email, etc.)
3. Set:
   ```
   FRONTEND_URL=https://ledger-pro-topaz.vercel.app
   CORS_ALLOWED_ORIGINS=https://ledger-pro-topaz.vercel.app
   CSRF_TRUSTED_ORIGINS=https://ledger-pro-topaz.vercel.app
   GOOGLE_OAUTH_REDIRECT_URI=https://ledger-pro-topaz.vercel.app/auth/google/callback
   ```
4. Redeploy
5. Test: `https://YOUR-API.vercel.app/api/health`

**Why builds failed before:** Vercel installs from `pyproject.toml`. Django was missing there → `No module named 'django'`. That is fixed now.

## Neon

`DATABASE_URL` must be the Neon URI with `sslmode=require` (already in `.env.vercel`).

## Google OAuth

Add redirect:
```
https://ledger-pro-topaz.vercel.app/auth/google/callback
```

## One-project mode (optional)

Root Directory empty + root `vercel.json` services. Prefer the 2-project setup on Hobby if one-project builds keep failing.
