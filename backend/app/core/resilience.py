"""
W2 — Retry decorators and circuit breaker for external service calls.

Covers:
  - RunPod /generate HTTP endpoint
  - RunPod GraphQL (pod resume / status)
  - Supabase PostgREST (optional — only use for non-auth reads)

Usage:
    from app.core.resilience import runpod_retry, runpod_circuit_breaker

    # 1. As a decorator on an async function:
    @runpod_retry
    async def call_runpod(...):
        ...

    # 2. Manual circuit-breaker check before a block:
    runpod_circuit_breaker.before_call()   # raises 503 if circuit is OPEN
    try:
        result = await call_runpod(...)
        runpod_circuit_breaker.record_success()
    except Exception as exc:
        runpod_circuit_breaker.record_failure()
        raise
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from functools import wraps
from typing import Any, Callable

from fastapi import HTTPException

logger = logging.getLogger("fideon.resilience")

# ── tenacity retry ────────────────────────────────────────────────────────────

try:
    from tenacity import (
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
        before_sleep_log,
        RetryError,
    )
    _TENACITY_AVAILABLE = True
except ImportError:
    _TENACITY_AVAILABLE = False
    logger.warning(
        "tenacity not installed — retry decorators are no-ops. "
        "Run: pip install tenacity>=8.2.0"
    )


def runpod_retry(fn: Callable) -> Callable:
    """
    Retry decorator for RunPod HTTP calls.
    Retries up to 3 times with exponential backoff (2s → 4s → 8s).
    Only retries on RuntimeError and httpx.HTTPError (not on 4xx auth errors).
    """
    if not _TENACITY_AVAILABLE:
        return fn  # no-op if tenacity not installed

    import httpx

    decorated = retry(
        reraise=True,
        retry=retry_if_exception_type((RuntimeError, httpx.HTTPError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )(fn)

    @wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await decorated(*args, **kwargs)
        except RetryError as exc:
            logger.error("RunPod call failed after 3 retries: %s", exc)
            raise RuntimeError(f"RunPod unavailable after retries: {exc}") from exc

    return wrapper


def postgrest_retry(fn: Callable) -> Callable:
    """
    Retry decorator for Supabase PostgREST HTTP calls.
    Retries up to 2 times with short backoff (1s → 2s).
    Does NOT retry on 4xx (auth/validation errors — no point retrying those).
    """
    if not _TENACITY_AVAILABLE:
        return fn

    import httpx

    decorated = retry(
        reraise=True,
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=2),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )(fn)

    @wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        return await decorated(*args, **kwargs)

    return wrapper


# ── Circuit breaker ───────────────────────────────────────────────────────────

class CircuitState(Enum):
    CLOSED  = "closed"   # normal — requests flow through
    OPEN    = "open"     # tripped — requests blocked immediately
    HALF    = "half"     # recovery probe — one request allowed through


class SimpleCircuitBreaker:
    """
    Thread-safe-enough circuit breaker for async FastAPI workloads.

    States:
        CLOSED  → all calls pass through
        OPEN    → calls rejected with 503 immediately (no upstream hit)
        HALF    → one probe call allowed; success → CLOSED, failure → OPEN

    Config:
        failure_threshold  – consecutive failures to trip (default: 5)
        recovery_timeout   – seconds in OPEN before moving to HALF (default: 60)
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ) -> None:
        self.name              = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout  = recovery_timeout
        self._state            = CircuitState.CLOSED
        self._failure_count    = 0
        self._opened_at: float = 0.0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._opened_at >= self.recovery_timeout:
                logger.info("Circuit %s entering HALF-OPEN for recovery probe", self.name)
                self._state = CircuitState.HALF
        return self._state

    def before_call(self) -> None:
        """Call this before every external request. Raises 503 if circuit is OPEN."""
        if self.state == CircuitState.OPEN:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Service '{self.name}' is temporarily unavailable. "
                    f"Retry after {int(self.recovery_timeout)}s."
                ),
                headers={"Retry-After": str(int(self.recovery_timeout))},
            )

    def record_success(self) -> None:
        """Call after a successful response."""
        if self._state in (CircuitState.HALF, CircuitState.OPEN):
            logger.info("Circuit %s CLOSED (recovered)", self.name)
        self._state         = CircuitState.CLOSED
        self._failure_count = 0

    def record_failure(self) -> None:
        """Call after a failed response."""
        self._failure_count += 1
        logger.warning(
            "Circuit %s failure %d/%d",
            self.name,
            self._failure_count,
            self.failure_threshold,
        )
        if self._failure_count >= self.failure_threshold or self._state == CircuitState.HALF:
            self._state     = CircuitState.OPEN
            self._opened_at = time.monotonic()
            logger.error(
                "Circuit %s OPENED after %d failures. Blocking for %ds.",
                self.name,
                self._failure_count,
                int(self.recovery_timeout),
            )

    def __repr__(self) -> str:
        return (
            f"<CircuitBreaker name={self.name!r} state={self.state.value} "
            f"failures={self._failure_count}/{self.failure_threshold}>"
        )


# ── Singleton circuit breakers (module-level — shared across requests) ────────

runpod_circuit_breaker   = SimpleCircuitBreaker("runpod",   failure_threshold=5, recovery_timeout=60)
supabase_circuit_breaker = SimpleCircuitBreaker("supabase", failure_threshold=10, recovery_timeout=30)
