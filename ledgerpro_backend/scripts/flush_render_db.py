"""Flush the database pointed to by DATABASE_URL in .env.render (production).

Never prints connection secrets. Usage from repo root:
  python ledgerpro_backend/scripts/flush_render_db.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_RENDER = ROOT / ".env.render"
BACKEND = ROOT / "ledgerpro_backend"


def load_dotenv_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        raise SystemExit(f"Missing {path}")
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        values[key.strip()] = val.strip().strip('"').strip("'")
    return values


def main() -> None:
    env = load_dotenv_file(ENV_RENDER)
    db_url = (env.get("DATABASE_URL") or "").strip()
    if not db_url:
        raise SystemExit(
            "DATABASE_URL not found in .env.render.\n"
            "Copy Internal Database URL from Render Postgres into .env.render, then retry.\n"
            "Or run on Render Shell: python manage.py flush --no-input"
        )

    # Refuse accidental local sqlite / docker db
    if "sqlite" in db_url.lower() or "@db:" in db_url or "localhost" in db_url or "127.0.0.1" in db_url:
        raise SystemExit("Refusing to flush: DATABASE_URL looks local, not Render.")

    os.environ["DATABASE_URL"] = db_url
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ledgerpro_backend.settings")
    # Avoid USE_SQLITE path
    os.environ["USE_SQLITE"] = "False"
    for key in (
        "SECRET_KEY",
        "DEBUG",
        "ALLOWED_HOSTS",
        "FRONTEND_URL",
        "REDIS_URL",
        "RESEND_API_KEY",
        "DEFAULT_FROM_EMAIL",
    ):
        if key in env and env[key]:
            os.environ.setdefault(key, env[key])

    sys.path.insert(0, str(BACKEND))
    import django

    django.setup()
    from django.core.management import call_command

    host_hint = db_url.split("@")[-1].split("/")[0] if "@" in db_url else "(unknown)"
    print(f"Flushing database host={host_hint} ...")
    call_command("flush", interactive=False, verbosity=1)
    call_command("migrate", interactive=False, verbosity=1)
    print("Done. Production data cleared; schema intact.")


if __name__ == "__main__":
    main()
