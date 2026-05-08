"""SSRF prevention for webhook endpoint URLs (SEC-07 / SEC-11).

Validates that a URL:
  1. Uses the HTTPS scheme only.
  2. Does not resolve to a private, loopback, link-local, or cloud-metadata IP.

Two entry points:
  - `validate_webhook_url(url)`       — synchronous, use only in sync contexts.
  - `async_validate_webhook_url(url)` — async-safe; runs DNS in a thread executor
    so the event loop is never blocked. Use this everywhere in FastAPI routes and
    the async delivery worker.

Both raise `SSRFBlockedError` (a ValueError subclass) on rejection.
"""

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse


class SSRFBlockedError(ValueError):
    """Raised when a URL resolves to a blocked address."""


# ── Blocked network ranges ────────────────────────────────────────────────────
# RFC-1918 private ranges
# Loopback (IPv4 + IPv6)
# Link-local (169.254.x.x — includes Azure IMDS at 169.254.169.254)
# IPv6 link-local (fe80::/10)
# IPv6 unique-local (fc00::/7)
# Unspecified / broadcast

_BLOCKED_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    # IPv4
    ipaddress.ip_network("10.0.0.0/8"),         # RFC-1918
    ipaddress.ip_network("172.16.0.0/12"),       # RFC-1918
    ipaddress.ip_network("192.168.0.0/16"),      # RFC-1918
    ipaddress.ip_network("127.0.0.0/8"),         # Loopback
    ipaddress.ip_network("169.254.0.0/16"),      # Link-local / Azure IMDS
    ipaddress.ip_network("0.0.0.0/8"),           # Unspecified
    ipaddress.ip_network("100.64.0.0/10"),       # Carrier-grade NAT (RFC-6598)
    ipaddress.ip_network("192.0.0.0/24"),        # IETF protocol (RFC-6890)
    ipaddress.ip_network("192.0.2.0/24"),        # TEST-NET-1
    ipaddress.ip_network("198.51.100.0/24"),     # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),      # TEST-NET-3
    ipaddress.ip_network("240.0.0.0/4"),         # Reserved
    ipaddress.ip_network("255.255.255.255/32"),  # Broadcast
    # IPv6
    ipaddress.ip_network("::1/128"),             # Loopback
    ipaddress.ip_network("::/128"),              # Unspecified
    ipaddress.ip_network("fc00::/7"),            # Unique-local
    ipaddress.ip_network("fe80::/10"),           # Link-local
    ipaddress.ip_network("::ffff:0:0/96"),       # IPv4-mapped IPv6
]


def _is_blocked_ip(addr: str) -> bool:
    """Return True if *addr* falls within any blocked network."""
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        # Not a valid IP — treat as blocked (shouldn't happen after resolution).
        return True

    for net in _BLOCKED_NETWORKS:
        if ip in net:
            return True
    return False


def _resolve_host_sync(hostname: str) -> list[str]:
    """Resolve *hostname* to all associated IP addresses (blocking).

    Uses the stdlib `socket.getaddrinfo` which honours /etc/hosts and the OS
    resolver.  Returns a list of IP strings (may include both IPv4 and IPv6).

    Raises `SSRFBlockedError` if the hostname cannot be resolved.
    """
    try:
        results = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise SSRFBlockedError(f"Cannot resolve hostname '{hostname}': {exc}") from exc

    return [r[4][0] for r in results if r[4]]


def _validate_parsed(parsed, hostname: str, resolved_ips: list[str]) -> None:
    """Shared validation logic after DNS resolution."""
    if parsed.username or parsed.password:
        raise SSRFBlockedError("Webhook URL must not contain credentials")
    if not resolved_ips:
        raise SSRFBlockedError(f"Hostname '{hostname}' resolved to no addresses")
    for ip_str in resolved_ips:
        if _is_blocked_ip(ip_str):
            raise SSRFBlockedError(
                f"Webhook URL hostname '{hostname}' resolves to blocked IP: {ip_str}"
            )


def validate_webhook_url(url: str) -> None:
    """Validate *url* for SSRF safety (synchronous).

    Only use in non-async contexts (tests, CLI tools).  In FastAPI routes or
    the async delivery worker, call `async_validate_webhook_url` instead to
    avoid blocking the event loop during DNS resolution.

    Raises `SSRFBlockedError` on any violation.
    """
    parsed = urlparse(url)

    if parsed.scheme != "https":
        raise SSRFBlockedError(
            f"Webhook URL must use HTTPS (got scheme '{parsed.scheme or 'none'}')"
        )

    hostname = parsed.hostname
    if not hostname:
        raise SSRFBlockedError("Webhook URL must contain a valid hostname")

    if parsed.username or parsed.password:
        raise SSRFBlockedError("Webhook URL must not contain credentials")

    # IP literal — no DNS needed.
    try:
        ip_literal = ipaddress.ip_address(hostname)
        if _is_blocked_ip(str(ip_literal)):
            raise SSRFBlockedError(
                f"Webhook URL points to a blocked IP address: {hostname}"
            )
        return
    except ValueError:
        pass

    resolved_ips = _resolve_host_sync(hostname)
    _validate_parsed(parsed, hostname, resolved_ips)


async def async_validate_webhook_url(url: str) -> None:
    """Async-safe SSRF validation — runs blocking DNS in a thread executor.

    Use this in all FastAPI route handlers and the async delivery worker so
    DNS resolution never blocks the event loop.

    Raises `SSRFBlockedError` on any violation.
    """
    parsed = urlparse(url)

    if parsed.scheme != "https":
        raise SSRFBlockedError(
            f"Webhook URL must use HTTPS (got scheme '{parsed.scheme or 'none'}')"
        )

    hostname = parsed.hostname
    if not hostname:
        raise SSRFBlockedError("Webhook URL must contain a valid hostname")

    if parsed.username or parsed.password:
        raise SSRFBlockedError("Webhook URL must not contain credentials")

    # IP literal — no DNS needed, no blocking call.
    try:
        ip_literal = ipaddress.ip_address(hostname)
        if _is_blocked_ip(str(ip_literal)):
            raise SSRFBlockedError(
                f"Webhook URL points to a blocked IP address: {hostname}"
            )
        return
    except ValueError:
        pass

    # Run blocking getaddrinfo in a thread pool so the event loop stays free.
    loop = asyncio.get_event_loop()
    resolved_ips = await loop.run_in_executor(None, _resolve_host_sync, hostname)
    _validate_parsed(parsed, hostname, resolved_ips)
