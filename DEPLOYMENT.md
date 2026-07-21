# Deploy LedgerPro: ONE Vercel project + Neon (free-tier friendly)

Frontend (Next.js) and Backend (Django) run on the **same** Vercel URL.  
Database is **Neon**. You only need **1** Vercel project (fits free tier limits).

| Piece | Where |
|-------|--------|
| Website + API | One Vercel project (repo root) |
| Postgres | Neon → `DATABASE_URL` |

Same origin means:
- Pages: `https://YOUR-APP.vercel.app/`
- API: `https://YOUR-APP.vercel.app/api/...`

Import env from: **`.env.vercel`**

---

## Step 1 — Create Neon database

1. Go to [https://console.neon.tech](https://console.neon.tech) → sign up / log in  
2. **Create a project** (name: `ledgerpro`)  
3. Open **Dashboard** → **Connection details**  
4. Copy the **connection string (URI)**. Example:

```
postgresql://neondb_owner:npg_xxxx@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require
```

5. Paste it into `.env.vercel` as `DATABASE_URL=...` (keep `?sslmode=require`)

---

## Step 2 — Fill `.env.vercel`

Open `c:\Users\LENOVO\Desktop\LedgerPro\.env.vercel` and set:

1. `DATABASE_URL` → Neon URI from Step 1  
2. `SECRET_KEY` → any long random string  
3. Leave `FRONTEND_URL` / OAuth redirect as placeholders until you have the Vercel URL  
4. Keep your Google / Gemini / Email / R2 keys  

---

## Step 3 — Deploy ONE project on Vercel

1. Push this repo to GitHub  
2. Open [https://vercel.com/new](https://vercel.com/new)  
3. Import `Aryansoni326/LedgerPro`  
4. **Do NOT set Root Directory** — leave it as the **repository root** (important)  
5. Framework: leave auto / ignore if unclear — root `vercel.json` handles Next.js + Django  
6. **Environment Variables** → Import / paste all keys from **`.env.vercel`**  
7. Click **Deploy**  
8. Copy your URL, e.g. `https://ledgerpro.vercel.app`

### Quick checks

- Frontend: `https://ledgerpro.vercel.app` → landing page  
- API: `https://ledgerpro.vercel.app/api/health` → `{"status":"ok"}`

If you still see **404: NOT_FOUND**, Root Directory is probably still set to `ledgerpro_frontend`. Clear it to **empty / `.`** and redeploy.

---

## Step 4 — Update URLs after first deploy

In Vercel → Project → **Settings** → **Environment Variables**, set:

| Key | Value |
|-----|--------|
| `FRONTEND_URL` | `https://ledgerpro.vercel.app` |
| `CORS_ALLOWED_ORIGINS` | `https://ledgerpro.vercel.app` |
| `CSRF_TRUSTED_ORIGINS` | `https://ledgerpro.vercel.app` |
| `GOOGLE_OAUTH_REDIRECT_URI` | `https://ledgerpro.vercel.app/auth/google/callback` |
| `DATABASE_URL` | (unchanged Neon URI) |

`NEXT_PUBLIC_API_URL` can stay **empty / unset** (same origin).  
Or set it to `https://ledgerpro.vercel.app` if you prefer.

**Redeploy** after changing env vars.

---

## Step 5 — Google OAuth

[Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials) → Authorized redirect URIs → add:

```
https://ledgerpro.vercel.app/auth/google/callback
```

---

## Environment variables (single Vercel project)

Import file: **`.env.vercel`**

```
DEBUG=False
SECRET_KEY=your-long-random-secret
ALLOWED_HOSTS=.vercel.app
DATABASE_URL=postgresql://...@...neon.tech/neondb?sslmode=require
FRONTEND_URL=https://YOUR-APP.vercel.app
CORS_ALLOWED_ORIGINS=https://YOUR-APP.vercel.app
CSRF_TRUSTED_ORIGINS=https://YOUR-APP.vercel.app
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REDIRECT_URI=https://YOUR-APP.vercel.app/auth/google/callback
GEMINI_API_KEY=...
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=LedgerPro <...>
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=...
R2_ENDPOINT_URL=...
CELERY_TASK_ALWAYS_EAGER=True
```

Optional:

```
NEXT_PUBLIC_API_URL=https://YOUR-APP.vercel.app
```

(If omitted in production, the frontend calls `/api/...` on the same domain.)

---

## Checklist

- [ ] Neon created, `DATABASE_URL` pasted  
- [ ] **One** Vercel project, Root Directory = **repo root** (not `ledgerpro_frontend`)  
- [ ] All env vars from `.env.vercel`  
- [ ] `/` loads landing page  
- [ ] `/api/health` returns ok  
- [ ] FRONTEND_URL + OAuth redirect match your Vercel domain  
- [ ] Google redirect URI updated  
- [ ] R2 set if you need file uploads  

## Limits (free tier)

- AI extraction runs inside the API request (60s max)  
- Uploads need **Cloudflare R2** (Vercel disk is temporary)  
- Cold starts can be slow after idle  
