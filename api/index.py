import os
import sys
from pathlib import Path

# api/ → repo root → ledgerpro_backend
ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "ledgerpro_backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ledgerpro_backend.settings")
os.environ.setdefault("VERCEL", "1")

from django.core.wsgi import get_wsgi_application
from django.core.management import call_command

app = get_wsgi_application()
application = app

try:
    call_command("migrate", "--noinput", verbosity=0)
except Exception as exc:  # noqa: BLE001
    print(f"[ledgerpro] migrate on cold start: {exc}")
