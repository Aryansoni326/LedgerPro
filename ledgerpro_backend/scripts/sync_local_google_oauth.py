"""Copy Google OAuth client credentials from .env.render into local .env.

Keeps local redirect URI on localhost:3001. Does not print secrets.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / ".env"
RENDER = ROOT / ".env.render"

COPY_KEYS = ("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET")
FORCE = {
    "GOOGLE_OAUTH_REDIRECT_URI": "http://localhost:3001/auth/google/callback",
    "FRONTEND_URL": "http://localhost:3001",
}


def parse(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for ln in path.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        data[k.strip()] = v.strip().strip('"').strip("'")
    return data


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
    if not RENDER.exists() or not LOCAL.exists():
        raise SystemExit("Need both .env and .env.render")
    render = parse(RENDER)
    updates = {k: render[k] for k in COPY_KEYS if render.get(k)}
    if len(updates) < 2:
        raise SystemExit("Missing Google OAuth keys in .env.render")
    updates.update(FORCE)
    upsert(LOCAL, updates)
    cid = updates["GOOGLE_OAUTH_CLIENT_ID"]
    print("Copied Google OAuth client id/secret from .env.render -> .env")
    print(f"CLIENT_ID_LEN={len(cid)} REDIRECT={updates['GOOGLE_OAUTH_REDIRECT_URI']}")
    print(
        "Also add this Authorized redirect URI in Google Cloud Console:\n"
        "  http://localhost:3001/auth/google/callback"
    )


if __name__ == "__main__":
    main()
