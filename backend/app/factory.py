import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import CORS_ALLOWED_ORIGINS, DEVICE_JWT_SECRET
from app.core.limiter import limiter

from app.logger import setup_logging
from app.routes.activity import router as activity_router
from app.routes.admin import router as admin_router
from app.routes.chat import router as chat_router
from app.routes.device import router as device_router
from app.routes.federated_learning import router as federated_router
from app.routes.health import router as health_router
from app.routes.help_assistant import router as help_router
from app.routes.pod_activation import router as pod_activation_router
from app.routes.settings import router as settings_router
from app.routes.tenants import router as tenants_router
from app.routes.workflow_ai import router as workflow_router

# Heartbeat period (seconds). Devices call PUT /api/v1/devices/heartbeat this often.
_HEARTBEAT_INTERVAL = 60
# A device is considered offline after this many missed beats.
_MISSED_BEATS_THRESHOLD = 3
_OFFLINE_AFTER_SECONDS = _HEARTBEAT_INTERVAL * _MISSED_BEATS_THRESHOLD  # 180 s

# Circuit-breaker: after this many consecutive sweep failures, log CRITICAL.
_DETECTOR_FAILURE_THRESHOLD = 5


async def _offline_detector_loop() -> None:
    """Background task: marks devices offline when last_seen_at is stale.

    Circuit breaker: consecutive failures are counted. Once the count reaches
    _DETECTOR_FAILURE_THRESHOLD a CRITICAL log is emitted (alertable in
    production log aggregators) so on-call can investigate. The loop always
    continues so devices are marked offline as soon as connectivity recovers.
    """
    from app.core.supabase import postgrest_patch
    from urllib.parse import quote

    log = structlog.get_logger("offline_detector")
    consecutive_failures = 0

    while True:
        await asyncio.sleep(_HEARTBEAT_INTERVAL)
        try:
            threshold = (datetime.now(timezone.utc) - timedelta(seconds=_OFFLINE_AFTER_SECONDS)).isoformat()
            # Single bulk UPDATE — PostgREST applies the PATCH to every matching row.
            await postgrest_patch(
                "devices",
                f"status=eq.online&last_seen_at=lt.{quote(threshold, safe='')}",
                {"status": "offline"},
            )
            if consecutive_failures > 0:
                log.info("offline_detector.sweep_recovered", after_failures=consecutive_failures)
            consecutive_failures = 0
            log.debug("offline_detector.sweep_ok", threshold=threshold)
        except Exception as exc:
            consecutive_failures += 1
            log.error("offline_detector.sweep_failed", error=str(exc), consecutive=consecutive_failures)
            if consecutive_failures >= _DETECTOR_FAILURE_THRESHOLD:
                log.critical(
                    "offline_detector.circuit_open",
                    consecutive=consecutive_failures,
                    msg="Offline detector has failed repeatedly — devices may appear stuck online. "
                        "Check Supabase connectivity and SUPABASE_SERVICE_ROLE_KEY.",
                )


@asynccontextmanager
async def _lifespan(app: FastAPI):
    log = structlog.get_logger("startup")
    if not DEVICE_JWT_SECRET.strip():
        raise RuntimeError(
            "DEVICE_JWT_SECRET environment variable is not set. "
            "Set a strong, random secret dedicated to signing device JWTs. "
            "Using SUPABASE_SERVICE_ROLE_KEY as a signing secret is not permitted "
            "because a compromised device token would grant service-role privileges."
        )
    task = asyncio.create_task(_offline_detector_loop())
    log.info("startup.offline_detector_started", interval_s=_HEARTBEAT_INTERVAL, threshold_s=_OFFLINE_AFTER_SECONDS)
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def create_app() -> FastAPI:
    app = FastAPI(title="Fideon FastAPI Backend", lifespan=_lifespan)

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    allow_origins = [o.strip() for o in CORS_ALLOWED_ORIGINS.split(",") if o.strip()]
    # Keep explicit origins from env, but always allow localhost development
    # ports to avoid CORS failures when frontend runs on non-default ports.
    local_dev_origins = [
        "http://localhost:3000",
        "http://localhost:3003",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3003",
    ]
    for origin in local_dev_origins:
        if origin not in allow_origins:
            allow_origins.append(origin)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(activity_router)
    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(help_router)
    app.include_router(workflow_router)
    app.include_router(device_router)
    app.include_router(federated_router)
    app.include_router(admin_router)
    app.include_router(pod_activation_router)
    app.include_router(tenants_router)
    app.include_router(settings_router)

    # Configure structured logging and HTTP request audit logs
    setup_logging(app)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

    return app
