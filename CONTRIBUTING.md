# Contributing to LedgerPro

Thank you for contributing to LedgerPro. This guide covers local setup using the same Docker Compose stack from Phase 0, plus how to run checks before opening a pull request.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose v2)
- [Git](https://git-scm.com/)
- Optional (for running lint/tests outside Docker):
  - Python 3.11+
  - Node.js 20+

## Local setup (Docker Compose)

The full stack runs five services: **PostgreSQL**, **Redis**, **Django backend**, **Celery worker**, and **Next.js frontend**.

### 1. Clone and configure environment

```bash
git clone <repository-url>
cd LedgerPro
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Edit `.env` if you need to change secrets or third-party API keys. Defaults work for local development.

### 2. Start all services

```bash
docker compose up --build
```

This builds images and starts all containers. Migrations are **not** run automatically — complete step 3 before using the app.

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Django Admin | http://localhost:8000/admin |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

### 3. Database setup (required on first run)

In a second terminal, after containers are healthy:

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
```

### 4. Verify Celery

```bash
docker compose logs celery_worker
```

You should see the worker listening for tasks. Optional smoke test:

```bash
docker compose exec backend python manage.py shell
```

```python
from accounts.tasks import test_celery_task
test_celery_task.delay("Contributor")
```

## Development workflow

### Backend changes

Backend code lives in `ledgerpro_backend/`. The Compose file bind-mounts this directory into the container, so Python changes reload automatically with `runserver`.

Run management commands inside the backend container:

```bash
docker compose exec backend python manage.py <command>
```

### Frontend changes

Frontend code lives in `ledgerpro_frontend/`. The dev server runs inside the `frontend` container with hot reload (`WATCHPACK_POLLING=true`).

To run the frontend on the host instead:

```bash
cd ledgerpro_frontend
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `.env`.

### Stopping services

```bash
docker compose down
```

To remove the PostgreSQL volume as well:

```bash
docker compose down -v
```

## Running checks locally

CI runs on every push. Reproduce the same checks before submitting a PR.

### Backend (from `ledgerpro_backend/`)

```bash
pip install -r requirements.txt -r requirements-dev.txt

# Lint
ruff check .

# Tests (SQLite, no Docker required)
set USE_SQLITE=True          # Windows CMD
# export USE_SQLITE=True     # macOS/Linux
pytest -v
```

Cross-firm isolation probe (optional):

```bash
python scripts/test_cross_firm_access.py
```

### Frontend (from `ledgerpro_frontend/`)

```bash
npm ci
npm run lint
npm run type-check
npm run build
```

## Project layout

```
LedgerPro/
├── .github/workflows/ci.yml   # CI pipeline
├── docker-compose.yml         # Local dev stack
├── .env.example               # Environment template (copy to .env)
├── ledgerpro_backend/         # Django REST API
├── ledgerpro_frontend/        # Next.js App Router UI
├── SECURITY.md                # Auth & data isolation overview
└── CONTRIBUTING.md            # This file
```

## Pull request checklist

- [ ] `ruff check .` passes in `ledgerpro_backend/`
- [ ] `pytest` passes in `ledgerpro_backend/`
- [ ] `npm run lint`, `npm run type-check`, and `npm run build` pass in `ledgerpro_frontend/`
- [ ] No secrets or `.env` files committed
- [ ] Database migrations included if models changed (`python manage.py makemigrations`)

## Getting help

- See [README.md](README.md) for a quick overview.
- See [SECURITY.md](SECURITY.md) for authentication and firm isolation details.
