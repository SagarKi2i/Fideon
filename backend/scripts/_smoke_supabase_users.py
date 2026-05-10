"""Smoke: Supabase password sign-in + backend GET /api/settings/profile.

Env (required for this smoke):
  SMOKE_USER_EMAIL, SMOKE_USER_PASSWORD
  SMOKE_ADMIN_EMAIL, SMOKE_ADMIN_PASSWORD

Reads frontend/.env.local for NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / "frontend" / ".env.local"
BACKEND = os.getenv("SMOKE_BACKEND_URL", "http://127.0.0.1:8000")


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            out[key] = val
    return out


def sign_in(supabase_url: str, anon_key: str, email: str, password: str) -> httpx.Response:
    return httpx.post(
        f"{supabase_url}/auth/v1/token?grant_type=password",
        headers={"apikey": anon_key, "Authorization": f"Bearer {anon_key}"},
        json={"email": email, "password": password},
        timeout=60.0,
    )


def profile(backend: str, access_token: str) -> httpx.Response:
    return httpx.get(
        f"{backend}/api/settings/profile",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=60.0,
    )


def main() -> int:
    pairs = [
        ("user", os.getenv("SMOKE_USER_EMAIL", "").strip(), os.getenv("SMOKE_USER_PASSWORD", "")),
        ("admin", os.getenv("SMOKE_ADMIN_EMAIL", "").strip(), os.getenv("SMOKE_ADMIN_PASSWORD", "")),
    ]
    if not all(p[1] and p[2] for p in pairs):
        print("Set SMOKE_USER_EMAIL, SMOKE_USER_PASSWORD, SMOKE_ADMIN_EMAIL, SMOKE_ADMIN_PASSWORD")
        return 2

    env = load_env(ENV_PATH)
    url = (env.get("NEXT_PUBLIC_SUPABASE_URL") or "").strip().rstrip("/")
    key = (env.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY") or "").strip()
    if not url or not key:
        print("MISSING_SUPABASE_VARS in frontend/.env.local")
        return 2

    for label, email, password in pairs:
        r = sign_in(url, key, email, password)
        print(f"supabase_signin_{label}", r.status_code)
        if r.status_code != 200:
            try:
                print("  keys", list(r.json().keys()))
            except Exception:
                print("  text_snip", (r.text or "")[:160])
            continue
        token = r.json().get("access_token")
        if not token:
            print("  no_access_token")
            continue
        pr = profile(BACKEND, token)
        print(f"backend_profile_{label}", pr.status_code)
        if pr.status_code == 200:
            data = pr.json()
            prof = data.get("profile") or {}
            print("  profile_email", prof.get("email"))
            print("  role", data.get("role"))
        else:
            try:
                print("  body", json.dumps(pr.json(), indent=2)[:500])
            except Exception:
                print("  text_snip", (pr.text or "")[:200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
