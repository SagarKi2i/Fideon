"""Shared slowapi rate-limiter instance.

Import `limiter` from this module in both factory.py (to register it with the
app) and route modules (to apply per-endpoint limits).
"""
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import TRUST_PROXY_HEADERS


def _client_ip_for_rate_limit(request: Request) -> str:
    """Return a stable client IP for rate-limit keys.

    In production behind a trusted ingress/proxy, enable TRUST_PROXY_HEADERS=true
    so X-Forwarded-For / X-Real-IP can be used. Otherwise use direct remote addr.
    """
    if TRUST_PROXY_HEADERS:
        forwarded_for = (request.headers.get("x-forwarded-for") or "").strip()
        if forwarded_for:
            # RFC 7239 list format: client, proxy1, proxy2...
            first = forwarded_for.split(",")[0].strip()
            if first:
                return first

        real_ip = (request.headers.get("x-real-ip") or "").strip()
        if real_ip:
            return real_ip

    return get_remote_address(request)


limiter = Limiter(key_func=_client_ip_for_rate_limit)
