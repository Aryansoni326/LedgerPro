"""Set local OTP email env for ledgerpro.store. Does not print secrets."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"

UPDATES = {
    "DEFAULT_FROM_EMAIL": "LedgerPro <noreply@ledgerpro.store>",
    "OTP_CONSOLE_FALLBACK": "False",
}


def upsert(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                out.append(f"{key}={updates[key]}")
                seen.add(key)
                continue
        out.append(line)
    for key, val in updates.items():
        if key not in seen:
            out.append(f"{key}={val}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> None:
    if not ENV.exists():
        raise SystemExit(f"Missing {ENV}")
    upsert(ENV, UPDATES)
    # Report RESEND status without revealing value
    key = ""
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("RESEND_API_KEY="):
            key = line.split("=", 1)[1].strip().strip('"').strip("'")
    placeholder = (not key) or key.startswith("re_xxx") or "xxxx" in key.lower() or len(key) < 20
    print("Updated DEFAULT_FROM_EMAIL -> LedgerPro <noreply@ledgerpro.store>")
    print(f"RESEND_API_KEY_OK={not placeholder} len={len(key)}")
    if placeholder:
        print("ACTION_REQUIRED: paste real RESEND_API_KEY from Render into .env")


if __name__ == "__main__":
    main()
