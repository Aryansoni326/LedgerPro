"""Upsert Resend email keys into project .env without printing secrets."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"

KEYS = {
    "RESEND_API_KEY": "re_xxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "DEFAULT_FROM_EMAIL": "LedgerPro <noreply@your-verified-domain.com>",
    "OTP_CONSOLE_FALLBACK": "False",
}


def upsert(path: Path, updates: dict[str, str]) -> list[str]:
    lines: list[str] = []
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()

    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            out.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        # Also update commented keys like #EMAIL_HOST=
        raw_key = key.lstrip("#").strip()
        if raw_key in updates and not stripped.startswith("#"):
            out.append(f"{raw_key}={updates[raw_key]}")
            seen.add(raw_key)
        else:
            out.append(line)

    missing = [k for k in updates if k not in seen]
    if missing:
        if out and out[-1].strip():
            out.append("")
        out.append("# --- Email (Resend) ---")
        for key in missing:
            out.append(f"{key}={updates[key]}")

    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return missing


def main() -> None:
    if not ENV_PATH.exists():
        raise SystemExit(f"Missing {ENV_PATH}; copy .env.example to .env first.")
    added = upsert(ENV_PATH, KEYS)
    print(f"Updated {ENV_PATH.name}")
    print(f"keys_touched={','.join(KEYS)}")
    print(f"keys_appended={','.join(added) if added else '(already present)'}")
    print("Replace RESEND_API_KEY and DEFAULT_FROM_EMAIL with your Resend values, then:")
    print("  docker-compose up -d --force-recreate backend")


if __name__ == "__main__":
    main()
