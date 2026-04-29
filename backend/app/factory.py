from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Iterable, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.responses import PlainTextResponse

from app.core.config import (
    CORS_ALLOWED_ORIGINS,
    DEVICE_JWT_SECRET,
    ENABLE_LOCAL_GENERATE,
    ENABLE_LOCAL_GENERATE_WARMUP,
    DEVICE_OFFLINE_DETECTOR_ENABLED,
    WEBHOOK_SECRET_ENCRYPTION_KEY,
    WEBHOOK_WORKER_ENABLED,
    SUPABASE_URL,
)
from app.core.limiter import limiter
from app.logger import setup_logging


def _split_origins(raw: str) -> List[str]:
    parts = [p.strip() for p in (raw or "").split(",")]
    out: List[str] = []
    for p in parts:
        if not p:
            continue
        out.append(p.rstrip("/"))
    return out


def _local_dev_origins() -> List[str]:
    # Keep these in sync with README/.env.example guidance.
    ports = (3000, 3003)
    hosts = ("http://localhost", "http://127.0.0.1")
    return [f"{h}:{p}" for h in hosts for p in ports]


def _cors_origins() -> List[str]:
    configured = _split_origins(CORS_ALLOWED_ORIGINS)
    # Ensure local dev ports are never accidentally blocked by stale env values.
    merged = {o for o in configured if o}
    merged.update(_local_dev_origins())
    return sorted(merged)


def _require_secrets() -> None:
    log = logging.getLogger("startup")
    log.info(
        "startup.config "
        f"SUPABASE_URL={SUPABASE_URL!r} "
        f"DEVICE_JWT_SECRET=SET (len={len(DEVICE_JWT_SECRET)})"
    )


@asynccontextmanager
async def _lifespan(app: FastAPI):
    bg_tasks: list[asyncio.Task] = []

    # Optional warmup to eliminate first-request cold start timeouts for local /generate.
    if ENABLE_LOCAL_GENERATE and ENABLE_LOCAL_GENERATE_WARMUP:
        from app.routes.local_generate import startup_warmup  # local import: heavy deps

        await startup_warmup()

    if WEBHOOK_WORKER_ENABLED and (WEBHOOK_SECRET_ENCRYPTION_KEY or "").strip():
        from app.services.webhook_engine import delivery_worker_loop

        bg_tasks.append(asyncio.create_task(delivery_worker_loop(), name="webhook_delivery_worker"))
    elif WEBHOOK_WORKER_ENABLED:
        logging.getLogger("startup").warning(
            "WEBHOOK_WORKER_ENABLED is true but WEBHOOK_SECRET_ENCRYPTION_KEY is unset — "
            "webhook delivery worker not started (set key to decrypt secrets for delivery)."
        )

    if DEVICE_OFFLINE_DETECTOR_ENABLED:
        from app.services.device_offline_detector import offline_detector_loop

        bg_tasks.append(asyncio.create_task(offline_detector_loop(), name="device_offline_detector"))

    try:
        yield
    finally:
        for t in bg_tasks:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass


def _register_rate_limit_handlers(app: FastAPI) -> None:
    # slowapi uses a Starlette exception; map to a simple 429 response.
    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_exceeded_handler(_request, _exc):  # type: ignore[no-redef]
        return PlainTextResponse("Rate limit exceeded", status_code=429)

    # Normalize API errors for frontend/tests: {"error": "..."} instead of {"detail": "..."}.
    @app.exception_handler(HTTPException)
    async def _http_exception_handler(_request, exc: HTTPException):  # type: ignore[no-redef]
        detail = exc.detail
        if isinstance(detail, (dict, list)):
            message = str(detail)
        else:
            message = str(detail or "")
        return JSONResponse(status_code=exc.status_code, content={"error": message})

    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(_request, exc: RequestValidationError):  # type: ignore[no-redef]
        # Keep it concise for clients; full details still appear in logs if needed.
        return JSONResponse(status_code=422, content={"error": "Invalid request", "details": exc.errors()})


def _include_routers(app: FastAPI) -> None:
    # Keep imports inside to reduce import-time side effects in tooling.
    from app.routes import (
        acord,
        activity,
        adapter_registry,
        admin,
        agents,
        auth_proxy,
        chat,
        decision_reviews,
        device,
        device_admin,
        federated_learning,
        federated_admin,
        health,
        help_assistant,
        ml_acord_proxy,
        model_registry,
        notifications,
        password_reset,
        pdf_upload,
        pod_activation,
        pods,
        runpod_control,
        settings,
        tenants,
        user_data,
        webhooks,
        workflow_ai,
    )

    routers: Iterable = (
        health.router,
        activity.router,
        adapter_registry.router,
        admin.router,
        agents.router,
        auth_proxy.router,
        chat.router,
        decision_reviews.router,
        device.router,
        device_admin.router,
        federated_learning.router,
        federated_admin.router,
        help_assistant.router,
        notifications.router,
        password_reset.router,
        pods.router,
        pod_activation.router,
        runpod_control.router,
        pdf_upload.router,
        settings.router,
        tenants.router,
        user_data.router,
        workflow_ai.router,
        acord.router,
        ml_acord_proxy.router,
        model_registry.router,
        webhooks.router,
    )
    for r in routers:
        app.include_router(r)

    if ENABLE_LOCAL_GENERATE:
        from app.routes import local_generate

        app.include_router(local_generate.router)


def create_app() -> FastAPI:
    _require_secrets()

    app = FastAPI(
        title="Fideon Fabric API",
        lifespan=_lifespan,
    )

    setup_logging(app)

    # Rate limiting (slowapi)
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    _register_rate_limit_handlers(app)

    # CORS
    allow_origins = _cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _include_routers(app)
    return app
