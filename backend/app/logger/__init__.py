import logging
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict

import structlog
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware


# -----------------------------
# PII scrubbing helpers
# -----------------------------

REDACTED_FIELDS = {
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "authorization",
    "ssn",
    "social_security",
    "credit_card",
    "card_number",
    "cvv",
    "dob",
    "date_of_birth",
    "birth_date",
    "full_name",
    "first_name",
    "last_name",
    "mobile",
    "phone",
    "phone_number",
    "address",
}


def _scrub_value(value: Any) -> Any:
    """Best-effort PII scrubbing for string / nested values."""
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if k.lower() in REDACTED_FIELDS else _scrub_value(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub_value(v) for v in value]
    if isinstance(value, str):
        # Minimal masking examples; extend as needed.
        if "@" in value:
            # Mask email user part
            user, _, domain = value.partition("@")
            if user:
                return f"{user[0]}***@{domain}"
        return value
    return value


def pii_scrubber_processor(_: structlog.types.WrappedLogger, __: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """structlog processor that scrubs PII-like fields before emitting."""
    return _scrub_value(event_dict)


def configure_logging() -> None:
    """Configure structlog for JSON, PII-safe logging, and write to logs/app.log."""
    logs_dir = Path(__file__).resolve().parents[2] / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = logs_dir / "app.log"

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=[
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.stdlib.add_log_level,
        ],
    )

    handler_stream = logging.StreamHandler(sys.stdout)
    handler_stream.setFormatter(formatter)

    handler_file = logging.FileHandler(log_file_path, encoding="utf-8")
    handler_file.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    # Avoid adding duplicate handlers if configure_logging is called twice
    if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None) == str(log_file_path) for h in root_logger.handlers):
        root_logger.handlers = [handler_stream, handler_file]

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            pii_scrubber_processor,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
    )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware to emit one structured log per HTTP request."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else None,
        )

        start = time.time()
        response = await call_next(request)
        duration_ms = int((time.time() - start) * 1000)

        logger = structlog.get_logger("http")
        logger.info(
            "http_request",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response


def setup_logging(app: FastAPI) -> None:
    """Initialize structlog and attach HTTP logging middleware to the app."""
    configure_logging()
    app.add_middleware(RequestLoggingMiddleware)


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Return a reusable structured logger instance."""
    return structlog.get_logger(name) if name else structlog.get_logger()

