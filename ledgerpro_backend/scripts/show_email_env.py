from pathlib import Path

KEYS = {
    "DEFAULT_FROM_EMAIL",
    "RESEND_API_KEY",
    "OTP_CONSOLE_FALLBACK",
    "EMAIL_HOST",
    "EMAIL_HOST_USER",
    "NEXT_PUBLIC_API_URL",
}


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
        if "KEY" in k or "PASSWORD" in k:
            placeholder = (not v) or v.startswith("re_xxx") or "xxxx" in v.lower()
            print(f"{path}: {k} len={len(v)} placeholder={placeholder}")
        else:
            print(f"{path}: {k}={v}")


show(".env")
show(".env.render")
