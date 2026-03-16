import asyncio
import logging
import logging.handlers
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Optional

import structlog
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware


# ── Configuration from environment ────────────────────────────────────────────

_LOG_LEVEL_NAME = os.getenv("LOG_LEVEL", "INFO").upper()
_LOG_LEVEL = getattr(logging, _LOG_LEVEL_NAME, logging.INFO)

# Prevent RecursionError on deeply nested log payloads.
_MAX_SCRUB_DEPTH = 10


# ── Presidio — content-based PII detection (Pass 2) ───────────────────────────
# Loaded once at startup. Runs in a dedicated ThreadPoolExecutor so it never
# blocks the asyncio event loop. If unavailable, degrades to Pass-1 only and
# emits a startup warning.

_PRESIDIO_AVAILABLE = False
_analyzer = None
_anonymizer = None
_PRESIDIO_EXECUTOR: Optional[ThreadPoolExecutor] = None

try:
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig

    _analyzer = AnalyzerEngine()
    _anonymizer = AnonymizerEngine()
    _PRESIDIO_AVAILABLE = True
    _PRESIDIO_EXECUTOR = ThreadPoolExecutor(
        max_workers=2, thread_name_prefix="presidio"
    )
except Exception:
    _analyzer = None
    _anonymizer = None
    _PRESIDIO_AVAILABLE = False

# Entity types Presidio detects. IP_ADDRESS intentionally excluded — kept for forensics.
_PRESIDIO_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "US_SSN",
    "IBAN_CODE",
    "LOCATION",
]

_PRESIDIO_OPERATORS = (
    {
        entity: OperatorConfig("replace", {"new_value": f"<{entity}>"})
        for entity in _PRESIDIO_ENTITIES
    }
    if _PRESIDIO_AVAILABLE
    else {}
)


def _presidio_scrub_sync(text: str) -> str:
    """Run Presidio synchronously.

    MUST be called from a thread pool only — never directly from the event loop.
    Catches all runtime exceptions so a Presidio failure (e.g. OOM) never
    propagates and breaks log emission.
    """
    try:
        results = _analyzer.analyze(
            text=text, language="en", entities=_PRESIDIO_ENTITIES
        )
        if not results:
            return text
        return _anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators=_PRESIDIO_OPERATORS,
        ).text
    except Exception:
        return text  # degrade gracefully — never let a runtime error propagate


async def scrub_text(text: str) -> str:
    """Async Pass-2 Presidio scrub — safe to await from route handlers or middleware.

    Offloads blocking NLP work to the Presidio thread pool so the event loop
    is never stalled. Falls back to the raw value if Presidio is unavailable.

    Usage in a route::

        safe_msg = await scrub_text(user_supplied_message)
        logger.info("user_action", details=safe_msg)
    """
    if not _PRESIDIO_AVAILABLE or not text:
        return text
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_PRESIDIO_EXECUTOR, _presidio_scrub_sync, text)


# ── Field-name PII scrubbing (Pass 1 — fast, synchronous) ─────────────────────

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


def _scrub_value(value: Any, _depth: int = 0) -> Any:
    """Pass-1 PII scrubbing: field-name keyword match → '[REDACTED]'.

    Also applies cheap email masking (u***@domain) on string values.
    Presidio (Pass 2) is NOT called here — it runs async via scrub_text().
    A depth counter prevents RecursionError on deeply nested payloads.
    """
    if _depth > _MAX_SCRUB_DEPTH:
        return value
    if isinstance(value, dict):
        return {
            k: (
                "[REDACTED]"
                if k.lower() in REDACTED_FIELDS
                else _scrub_value(v, _depth + 1)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_scrub_value(v, _depth + 1) for v in value]
    if isinstance(value, str) and "@" in value:
        # Cheap email masking — cheaper than running NLP for the most common case.
        user, _, domain = value.partition("@")
        if user:
            return f"{user[0]}***@{domain}"
    return value


def pii_scrubber_processor(
    _: structlog.types.WrappedLogger, __: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """structlog processor: fast Pass-1 field-name scrub only.

    Pass-2 Presidio content scan is intentionally excluded here. Running
    blocking NLP inside a sync structlog processor stalls the asyncio event
    loop under load. Use scrub_text() from async contexts instead.
    """
    return _scrub_value(event_dict)


# ── Logging setup ──────────────────────────────────────────────────────────────

def configure_logging() -> None:
    """Configure structlog for JSON, PII-safe, rotating-file logging.

    Reads LOG_LEVEL from the environment (default: INFO).
    Rotates log files at 10 MB, keeping 5 backups (50 MB max on disk).
    Emits a startup warning if Presidio content scanning is unavailable.
    Safe to call multiple times — installs handlers only once.
    """
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

    handler_file = logging.handlers.RotatingFileHandler(
        log_file_path,
        maxBytes=10 * 1024 * 1024,  # rotate at 10 MB
        backupCount=5,               # keep app.log + 5 backups = 50 MB max
        encoding="utf-8",
    )
    handler_file.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(_LOG_LEVEL)

    # Install our handlers only once — guard against hot-reload / double init.
    already_configured = any(
        isinstance(h, logging.handlers.RotatingFileHandler)
        and getattr(h, "baseFilename", None) == str(log_file_path)
        for h in root_logger.handlers
    )
    if not already_configured:
        # Remove pre-existing handlers (uvicorn/gunicorn defaults) so we own
        # the full output pipeline and avoid duplicate lines.
        for h in root_logger.handlers[:]:
            root_logger.removeHandler(h)
        root_logger.addHandler(handler_stream)
        root_logger.addHandler(handler_file)

        # Redirect uvicorn's own loggers through root so our formatter and
        # rotating file handler apply to all output uniformly.
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi"):
            uv_log = logging.getLogger(name)
            uv_log.handlers.clear()
            uv_log.propagate = True

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            pii_scrubber_processor,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
    )

    # Warn at startup if Pass-2 Presidio content scanning is degraded.
    if not _PRESIDIO_AVAILABLE:
        logging.getLogger("startup").warning(
            "Presidio PII content scanner unavailable — running Pass-1 "
            "field-name scrubbing only. Install presidio-analyzer, "
            "presidio-anonymizer, and en_core_web_sm to enable Pass-2."
        )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware: one structured JSON log line per HTTP request.

    Captured fields: request_id, method, path, client_ip, status_code,
    duration_ms.

    Unhandled exceptions are logged at ERROR level with full traceback
    (exc_info=True) before being re-raised so the framework can return a
    500 response. This ensures 500s are never invisible in the log.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else None,
        )

        logger = structlog.get_logger("http")
        start = time.perf_counter()

        try:
            response = await call_next(request)
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.info(
                "http_request",
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
            return response
        except Exception:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "http_request_error",
                duration_ms=duration_ms,
                exc_info=True,
            )
            raise


def setup_logging(app: FastAPI) -> None:
    """Initialize structlog and attach HTTP request logging middleware to the app."""
    configure_logging()
    app.add_middleware(RequestLoggingMiddleware)


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """Return a named structured logger instance."""
    return structlog.get_logger(name) if name else structlog.get_logger()
