"""python -m evals — bootstrap Django then run the harness."""
from __future__ import annotations

import os


def _setup_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ledgerpro_backend.settings")
    os.environ.setdefault("USE_SQLITE", "True")
    import django

    django.setup()


def main() -> None:
    _setup_django()
    from evals.harness import main as harness_main

    raise SystemExit(harness_main())


if __name__ == "__main__":
    main()
