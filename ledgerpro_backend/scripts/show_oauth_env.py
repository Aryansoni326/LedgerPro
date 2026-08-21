from pathlib import Path

KEYS = (
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "GOOGLE_OAUTH_REDIRECT_URI",
    "FRONTEND_URL",
    "NEXT_PUBLIC_API_URL",
)


def show(path: str) -> None:
    p = Path(path)
    if not p.exists():
        print(path, "MISSING")
        return
    for ln in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = ln.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k not in KEYS:
            continue
        if "SECRET" in k:
            placeholder = (not v) or "your-" in v.lower() or "replace" in v.lower() or v.endswith(".apps.googleusercontent.com") and "your" in v
            print(f"{path}: {k} len={len(v)} placeholder={'(looks empty/placeholder)' if not v or 'your-' in v.lower() else 'maybe-real'}")
        elif "CLIENT_ID" in k:
            looks_placeholder = (not v) or "your-" in v.lower() or v.startswith("your-")
            print(f"{path}: {k} len={len(v)} ends_with_apps={v.endswith('.apps.googleusercontent.com')} placeholder={looks_placeholder} suffix={v[-28:] if len(v)>28 else v}")
        else:
            print(f"{path}: {k}={v}")


show(".env")
show(".env.render")
show(".env.example")
