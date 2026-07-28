# Deploy LedgerPro on Render

This monorepo deploys as **3 services** + Postgres + Redis.

| Service | Folder | Role |
|---------|--------|------|
| `ledgerpro-api` | `ledgerpro_backend/` | Django REST API (gunicorn) |
| `ledgerpro-celery` | `ledgerpro_backend/` | Background AI / invoice jobs |
| `ledgerpro-web` | `ledgerpro_frontend/` | Next.js frontend |
| `ledgerpro-db` | — | PostgreSQL |
| `ledgerpro-redis` | — | Redis (Celery broker) |

Env import file (local, gitignored): **`.env.render`**

---

## Option A — Blueprint (recommended)

1. Push this repo to GitHub
2. [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint**
3. Select `Aryansoni326/LedgerPro` (or your repo)
4. Confirm `render.yaml` → Create
5. When prompted for `sync: false` values, paste from **`.env.render`**
6. Wait until all services are live

## Option B — Manual services

### 1. PostgreSQL
**New → PostgreSQL** → copy **Internal Database URL** → use as `DATABASE_URL`

### 2. Redis (Key Value)
**New → Key Value** → copy connection string → use as `REDIS_URL`

### 3. Backend API (`ledgerpro-api`)
- **Root Directory:** `ledgerpro_backend`
- **Runtime:** Python 3.11
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `bash start.sh`
- Import env from **`.env.render`** (all keys except `NEXT_PUBLIC_API_URL`)
- Add `DATABASE_URL` and `REDIS_URL` from steps 1–2 if not using Blueprint

### 4. Celery worker (`ledgerpro-celery`)
- **Root Directory:** `ledgerpro_backend`
- **Build:** `pip install -r requirements.txt`
- **Start:** `bash start_celery.sh`
- Same env as API (`DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `GEMINI_API_KEY`, `R2_*`)

### 5. Frontend (`ledgerpro-web`)
- **Root Directory:** `ledgerpro_frontend`
- **Runtime:** Node 20
- **Build:** `npm ci && npm run build`
- **Start:** `npm run start`
- Env (only this):
  ```
  NEXT_PUBLIC_API_URL=https://ledgerpro-api.onrender.com
  ```
  (use your real API URL — no trailing slash)

---

## Import `.env.render`

Local path: `c:\Users\LENOVO\Desktop\LedgerPro\.env.render`

1. Open the Render service → **Environment**
2. Paste each `KEY=VALUE` line, or use bulk / “Add from .env”
3. Replace placeholders with your real `*.onrender.com` URLs after first deploy
4. Redeploy after changing env vars

### Which keys go where?

| Key | API | Celery | Web |
|-----|-----|--------|-----|
| `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS` | ✅ | ✅ | ❌ |
| `DATABASE_URL`, `REDIS_URL` | ✅ | ✅ | ❌ |
| `FRONTEND_URL`, `CORS_*`, `CSRF_*` | ✅ | ❌ | ❌ |
| `GOOGLE_OAUTH_*` | ✅ | ❌ | ❌ |
| `GEMINI_API_KEY`, `R2_*` | ✅ | ✅ | ❌ |
| `EMAIL_*` | ✅ | ❌ | ❌ |
| `CELERY_TASK_ALWAYS_EAGER` | ✅ | ✅ | ❌ |
| `NEXT_PUBLIC_API_URL` | ❌ | ❌ | ✅ |

---

## After deploy — wire URLs

Assume:
- API: `https://ledgerpro-api.onrender.com`
- Web: `https://ledgerpro-web.onrender.com`

### On `ledgerpro-api`
```
FRONTEND_URL=https://ledgerpro-web.onrender.com
CORS_ALLOWED_ORIGINS=https://ledgerpro-web.onrender.com
CSRF_TRUSTED_ORIGINS=https://ledgerpro-web.onrender.com,https://ledgerpro-api.onrender.com
GOOGLE_OAUTH_REDIRECT_URI=https://ledgerpro-web.onrender.com/auth/google/callback
```

### On `ledgerpro-web`
```
NEXT_PUBLIC_API_URL=https://ledgerpro-api.onrender.com
```

Redeploy **both** after changing these.

---

## Google OAuth

In [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials):

**Authorized JavaScript origins**
```
https://ledgerpro-web.onrender.com
```

**Authorized redirect URIs**
```
https://ledgerpro-web.onrender.com/auth/google/callback
```

(Keep local `http://localhost:3001/...` for Docker if you still develop locally.)

---

## Checklist

- [ ] Blueprint or 3 services + Postgres + Redis created
- [ ] `.env.render` imported on API (and Celery)
- [ ] `NEXT_PUBLIC_API_URL` set on web only
- [ ] `https://YOUR-API.onrender.com/api/health` → `{"status":"ok"}`
- [ ] Frontend landing page loads
- [ ] Google redirect URI matches frontend callback
- [ ] Register / Login / OTP works

## Free tier notes

- Free web services sleep after idle (~15 min); first request is slow
- Free Postgres may expire; you can point `DATABASE_URL` at Neon instead
- Without Redis + Celery, set `CELERY_TASK_ALWAYS_EAGER=True` on the API (jobs run inside the request)
