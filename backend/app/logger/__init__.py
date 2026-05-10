import asyncio
import logging
import logging.handlers
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
    import spacy.util as _spacy_util
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig

    _SPACY_MODEL = "en_core_web_lg"
    if not _spacy_util.is_package(_SPACY_MODEL):
        raise ImportError(f"spaCy model '{_SPACY_MODEL}' is not installed — skipping Presidio PII scanner. "
                          f"Run: python -m spacy download {_SPACY_MODEL}")

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
    loop = asyncio.get_running_loop()
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


# ── SHAP Reasoning ─────────────────────────────────────────────────────────────

def generate_shap_reasoning(
    shap_values: Dict[str, float],
    prediction: Any,
    model_id: str = "unknown",
    top_n: int = 5,
) -> str:
    """Generate a human-readable explanation from SHAP feature contributions.

    Sorts features by absolute SHAP value (most influential first) and
    produces a single sentence suitable for storing in audit_logs.reasoning.

    Args:
        shap_values: Mapping of feature name → SHAP float value.
                     Positive values push the prediction up (increasing risk /
                     confidence); negative values push it down.
        prediction:  The model's output (scalar, label string, or dict).
                     Rendered as a string in the explanation.
        model_id:    Human-readable model identifier (e.g. "fraud-v3").
        top_n:       Maximum number of features to include in the explanation.

    Returns:
        A string like:
        "Model 'fraud-v3' predicted 'high_risk'. "
        "Top factors: transaction_amount (+0.42, ↑), account_age (-0.31, ↓), "
        "hour_of_day (+0.18, ↑)."

    Example::

        reasoning = generate_shap_reasoning(
            shap_values={"transaction_amount": 0.42, "account_age": -0.31},
            prediction={"label": "high_risk", "confidence": 0.87},
            model_id="fraud-v3",
        )
        await insert_audit_log(..., reasoning=reasoning, shap_values=shap_values)
    """
    if not shap_values:
        return f"Model '{model_id}' produced prediction '{prediction}'. No SHAP values available."

    # Sort by absolute contribution magnitude, descending.
    ranked: List[Tuple[str, float]] = sorted(
        shap_values.items(), key=lambda kv: abs(kv[1]), reverse=True
    )[:top_n]

    # Render prediction cleanly whether it's a scalar or a dict.
    if isinstance(prediction, dict):
        pred_label = prediction.get("label") or prediction.get("class") or str(prediction)
        confidence = prediction.get("confidence") or prediction.get("score")
        pred_str = f"'{pred_label}'"
        if confidence is not None:
            try:
                pred_str += f" (confidence {float(confidence):.1%})"
            except (TypeError, ValueError):
                pass
    else:
        pred_str = f"'{prediction}'"

    # Build the factor list.
    factor_parts = []
    for feature, value in ranked:
        direction = "↑" if value >= 0 else "↓"
        factor_parts.append(f"{feature} ({value:+.4f}, {direction})")

    factors_str = ", ".join(factor_parts) if factor_parts else "none"
    return (
        f"Model '{model_id}' predicted {pred_str}. "
        f"Top factors: {factors_str}."
    )


async def log_ai_decision_audit(
    request: Any,
    user_id: Optional[str],
    action: str,
    resource_type: str,
    model_id: str,
    shap_values: Dict[str, float],
    prediction: Any,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    previous_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    top_n: int = 5,
    reasoning: Optional[str] = None,
) -> None:
    """Convenience wrapper: generate SHAP reasoning and write an audit ledger row.

    Combines generate_shap_reasoning() with insert_audit_log() so callers
    don't have to construct the explanation manually.  If *reasoning* is
    supplied explicitly it is used as-is; otherwise it is auto-generated
    from *shap_values* and *prediction*.

    The resulting audit row contains:
      - standard fields  : user_id, action, resource_type, resource_id,
                           details, previous_value, new_value, ip_address,
                           user_agent, created_at
      - integrity_hash   : SHA-256 over all non-PII fields including SHAP data
      - chain_hash       : computed by DB trigger — links this row to the
                           previous ledger entry (cryptographic audit ledger)
      - shap_values      : raw SHAP dict for downstream analysis
      - model_id         : model identifier
      - prediction       : model output
      - reasoning        : human-readable explanation

    Example::

        await log_ai_decision_audit(
            request=request,
            user_id=current_user["id"],
            action="risk_assessment",
            resource_type="transaction",
            resource_id=transaction_id,
            model_id="fraud-detector-v3",
            shap_values={"amount": 0.42, "account_age": -0.31, "hour": 0.18},
            prediction={"label": "high_risk", "confidence": 0.87},
        )
    """
    # Defer import to avoid circular dependencies — supabase.py is in app.core.
    from app.core.supabase import insert_audit_log  # noqa: PLC0415

    if reasoning is None:
        reasoning = generate_shap_reasoning(
            shap_values=shap_values,
            prediction=prediction,
            model_id=model_id,
            top_n=top_n,
        )

    # Normalise prediction to a dict so PostgREST stores it as JSONB.
    prediction_payload: Optional[Dict[str, Any]]
    if isinstance(prediction, dict):
        prediction_payload = prediction
    else:
        prediction_payload = {"value": prediction}

    await insert_audit_log(
        request=request,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        previous_value=previous_value,
        new_value=new_value,
        shap_values=shap_values,
        model_id=model_id,
        prediction=prediction_payload,
        reasoning=reasoning,
    )

    # Emit a structured log line alongside the audit ledger entry.
    structlog.get_logger("ai_decision").info(
        "ai_decision_audited",
        model_id=model_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        reasoning=reasoning,
    )
