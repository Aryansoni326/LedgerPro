# Deploy LedgerPro Frontend on Vercel

The repo is a monorepo. Vercel must deploy **`ledgerpro_frontend`**, not the repository root.

## Fix Vercel 404 NOT_FOUND

1. Open [Vercel Dashboard](https://vercel.com/dashboard) → your **ledgerpro** project
2. Go to **Settings** → **General**
3. Set **Root Directory** to: `ledgerpro_frontend`
4. Click **Save**
5. Go to **Settings** → **Environment Variables**
6. Add:
   - `NEXT_PUBLIC_API_URL` = your backend API URL (e.g. `https://your-backend.onrender.com`)
7. **Deployments** → open latest deployment → **Redeploy**

After redeploy, the site should load at your Vercel URL (landing page).

## Build settings (auto-detected)

| Setting | Value |
|---------|--------|
| Framework | Next.js |
| Root Directory | `ledgerpro_frontend` |
| Build Command | `npm run build` |
| Install Command | `npm ci` |
| Output Directory | (leave default — Vercel detects `.next`) |

## Backend (not on Vercel)

Deploy `ledgerpro_backend` separately (Render, Railway, Fly.io, etc.) with PostgreSQL + Redis + Celery.

Required backend env for production:
- `ALLOWED_HOSTS` — your backend domain
- `GOOGLE_OAUTH_REDIRECT_URI` — `https://<backend-domain>/api/auth/google/callback`
- Database and Redis URLs
- Email / Google OAuth / Gemini keys from `.env.example`

## GitHub push (VS Code)

1. Source Control → commit changes
2. Push to `origin main`
3. Vercel redeploys automatically if GitHub is connected
