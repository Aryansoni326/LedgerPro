"""Flush production (or any) Postgres pointed to by DATABASE_URL.

Usage (PowerShell) — paste External Database URL from Render Postgres → Connect:

  $env:DATABASE_URL = "postgresql://..."
  python ledgerpro_backend/scripts/flush_render_db.py

Refuses sqlite / localhost / docker `db` hosts.
Never prints the full connection string.
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
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        values[key.strip()] = val.strip().strip('"').strip("'")
    return values


def main() -> None:
    file_env = load_dotenv_file(ENV_RENDER)
    db_url = (os.environ.get("DATABASE_URL") or file_env.get("DATABASE_URL") or "").strip()
    if not db_url:
        raise SystemExit(
            "DATABASE_URL missing.\n\n"
            "1) Render → PostgreSQL (ledgerpro-db) → Connect → copy External Database URL\n"
            "2) PowerShell:\n"
            '   $env:DATABASE_URL = "paste-url-here"\n'
            "   python ledgerpro_backend/scripts/flush_render_db.py\n"
        )

    lowered = db_url.lower()
    if "sqlite" in lowered or "@db:" in lowered or "@db/" in lowered:
        raise SystemExit("Refusing to flush: DATABASE_URL looks like local Docker.")
    if "127.0.0.1" in lowered or "@localhost" in lowered:
        raise SystemExit("Refusing to flush: DATABASE_URL looks local.")

    os.environ["DATABASE_URL"] = db_url
    os.environ["USE_SQLITE"] = "False"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ledgerpro_backend.settings")
    os.environ.setdefault("SECRET_KEY", file_env.get("SECRET_KEY") or "flush-temp-secret")
    os.environ.setdefault("DEBUG", "False")
    os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1")
    for key in ("FRONTEND_URL", "REDIS_URL", "RESEND_API_KEY", "DEFAULT_FROM_EMAIL"):
        if file_env.get(key):
            os.environ.setdefault(key, file_env[key])

    sys.path.insert(0, str(BACKEND))
    import django

    django.setup()
    from django.core.management import call_command
    from django.contrib.auth import get_user_model

    host_hint = db_url.split("@")[-1].split("/")[0].split("?")[0] if "@" in db_url else "(unknown)"
    User = get_user_model()
    before = User.objects.count()
    print(f"Target host={host_hint}")
    print(f"Users before flush: {before}")
    print("Flushing ALL tables...")
    call_command("flush", interactive=False, verbosity=1)
    call_command("migrate", interactive=False, verbosity=1)
    after = User.objects.count()
    print(f"Users after flush: {after}")
    print("Done. All login credentials and uploaded data are cleared.")


if __name__ == "__main__":
    main()
