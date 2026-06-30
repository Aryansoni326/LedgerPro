# LedgerPro v2 - AI Invoice Automation SaaS

This is the project foundation for LedgerPro v2, featuring a Django 5 REST backend and a Next.js 14 App Router frontend. The entire stack is containerized with Docker Compose.

## Project Structure

```
LedgerPro/
├── docker-compose.yml
├── .env.example
├── README.md
├── ledgerpro_backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── manage.py
│   ├── ledgerpro_backend/      # settings, urls, celery
│   └── accounts/               # auth/users + Celery test task
│   └── firms/                  # firm/client management
│   └── invoices/               # bills
│   └── trade_docs/             # import-export + e-way bills
│   └── vault/                  # cloud storage index
│   └── analytics/              # business reports
└── ledgerpro_frontend/
    ├── Dockerfile
    ├── tailwind.config.ts      # grayscale design token config
    ├── package.json
    └── app/                    # ThemeProvider + Toggle + Landing Page
```

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)

## How to Run Local Development

1. **Set up Environment Variables**:
   Copy the `.env.example` file to `.env`:
   ```bash
   cp .env.example .env
   ```
   *(Note: For Windows PowerShell, you can run `Copy-Item .env.example .env`)*

2. **Start the Services**:
   Run the following command to build and run all services (db, redis, backend, celery, frontend):
   ```bash
   docker-compose up --build
   ```

3. **Verify the Services**:
   - **Next.js Frontend**: Visit [http://localhost:3000](http://localhost:3000) (verify the theme toggle works between light and dark modes).
   - **Django Admin**: Visit [http://localhost:8000/admin](http://localhost:8000/admin).
   - **Celery Test Task**: Verify that the Celery logs show the worker is listening and tasks run successfully.

## Useful Commands

- **Run database migrations**:
  ```bash
  docker-compose exec backend python manage.py migrate
  ```

- **Create a superuser**:
  ```bash
  docker-compose exec backend python manage.py createsuperuser
  ```

- **Trigger Celery test task from shell**:
  ```bash
  docker-compose exec backend python manage.py shell
  ```
  And run:
  ```python
  from accounts.tasks import test_celery_task
  test_celery_task.delay("Developer")
  ```
