import os
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _load_local_env_file() -> None:
    """Load backend/.env into process env if variables are missing."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Prefer values from backend/.env when the process env var is missing
        # or present-but-empty. This avoids stale empty vars blocking local config.
        #
        # CORS_ALLOWED_ORIGINS is always sourced from backend/.env in local runs
        # so frontend dev ports (for example 3003) are not silently blocked by
        # stale shell-level values.
        should_override = key == "CORS_ALLOWED_ORIGINS"
        if key and (should_override or key not in os.environ or not (os.environ.get(key) or "").strip()):
            os.environ[key] = value


_load_local_env_file()

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
# Default LLM model name used by legacy RAG helpers (LLM/rag/*).
# Prefer the chat model env if provided, otherwise fall back to Groq default.
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "") or os.getenv("GROQ_MODEL_CHAT", "") or DEFAULT_GROQ_MODEL

# ── Database backend selector ─────────────────────────────────────────────────
# Change this to switch the entire DB layer. Supported: supabase | mongodb | postgres
# See backend/app/core/db/ for implementations.
DB_BACKEND = os.getenv("DB_BACKEND", "supabase").strip().lower()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
# Secret used to sign device JWTs issued by POST /api/v1/devices/register.
# Must be set — startup will refuse to boot without it (see factory.py).
DEVICE_JWT_SECRET = os.getenv("DEVICE_JWT_SECRET", "")
CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
TRUST_PROXY_HEADERS = _env_bool("TRUST_PROXY_HEADERS", default=False)
LEGACY_DEVICE_TOKEN_APIS_ENABLED = _env_bool("LEGACY_DEVICE_TOKEN_APIS_ENABLED", default=False)
# Mount POST /generate (app/routes/local_generate.py) for ACORD_USE_OFFLINE_LLM + OFFLINE_LLM_GENERATE_URL on same port.
ENABLE_LOCAL_GENERATE = _env_bool("ENABLE_LOCAL_GENERATE", default=False)
# If True, block startup until the local model is loaded (RunPod cold start; avoids first-request timeout).
ENABLE_LOCAL_GENERATE_WARMUP = _env_bool("ENABLE_LOCAL_GENERATE_WARMUP", default=False)
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_OPENAI_COMPAT_URL = os.getenv("GROQ_OPENAI_COMPAT_URL", "https://api.groq.com/openai/v1/chat/completions")
GROQ_MODEL_CHAT = os.getenv("GROQ_MODEL_CHAT", DEFAULT_GROQ_MODEL)
GROQ_MODEL_HELP = os.getenv("GROQ_MODEL_HELP", DEFAULT_GROQ_MODEL)
GROQ_MODEL_WORKFLOW = os.getenv("GROQ_MODEL_WORKFLOW", DEFAULT_GROQ_MODEL)

# RunPod
# - RUNPOD_OPENAI_COMPAT_URL supports OpenAI-compatible endpoints (legacy path)
# - RUNPOD_GENERATE_URL supports direct /generate style endpoints
# - FIDEON_SECRET_KEY is preferred for Bearer auth with /generate endpoints
RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY", "")
FIDEON_SECRET_KEY = os.getenv("FIDEON_SECRET_KEY", "")
RUNPOD_OPENAI_COMPAT_URL = os.getenv("RUNPOD_OPENAI_COMPAT_URL", "")
RUNPOD_GENERATE_URL = os.getenv("RUNPOD_GENERATE_URL", "https://8e7k92f9vcuxzh-8000.proxy.runpod.net/generate")
RUNPOD_MODEL_LLAMA = os.getenv("RUNPOD_MODEL_LLAMA", "meta-llama/Meta-Llama-3.1-8B-Instruct")
RUNPOD_MODEL_MISTRAL = os.getenv("RUNPOD_MODEL_MISTRAL", "mistralai/Mistral-7B-Instruct-v0.3")
OFFLINE_LLM_FALLBACK_ENABLED = os.getenv("OFFLINE_LLM_FALLBACK_ENABLED", "false")
# RunPod GraphQL (podResume / podStop / pod status). Uses RUNPOD_API_KEY as Bearer.
RUNPOD_POD_ID = os.getenv("RUNPOD_POD_ID", "").strip()
# Optional: ML server origin for health checks. If empty, derived from RUNPOD_GENERATE_URL (strip /generate).
RUNPOD_PROXY_BASE_URL = os.getenv("RUNPOD_PROXY_BASE_URL", "").strip()
# Upload server URL — separate port (8080) for PDF ingestion. Falls back to RUNPOD_PROXY_BASE_URL.
# Example: https://<pod-id>-8080.proxy.runpod.net
RUNPOD_UPLOAD_BASE_URL = os.getenv("RUNPOD_UPLOAD_BASE_URL", "").strip()
# Aliases (e.g. llm-gateway): POD_ID, PROXY_URL
if not RUNPOD_POD_ID:
    RUNPOD_POD_ID = (os.getenv("POD_ID") or "").strip()
if not RUNPOD_PROXY_BASE_URL:
    RUNPOD_PROXY_BASE_URL = (os.getenv("PROXY_URL") or "").strip().rstrip("/")


def runpod_proxy_base_url() -> str:
    """HTTPS origin for the RunPod-exposed ML HTTP port, no trailing slash, no /generate path."""
    explicit = RUNPOD_PROXY_BASE_URL.strip().rstrip("/")
    if explicit:
        return explicit
    gen = (RUNPOD_GENERATE_URL or "").strip().rstrip("/")
    if gen.endswith("/generate"):
        return gen[: -len("/generate")]
    return gen


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


# Device online/offline tracking
# Devices heartbeat every 60s. After N missed beats, a background sweep marks them offline.
DEVICE_OFFLINE_DETECTOR_ENABLED = _env_bool("DEVICE_OFFLINE_DETECTOR_ENABLED", default=True)
DEVICE_OFFLINE_AFTER_SECONDS = _env_float("DEVICE_OFFLINE_AFTER_SECONDS", default=180.0)
DEVICE_OFFLINE_DETECTOR_POLL_SECONDS = _env_float("DEVICE_OFFLINE_DETECTOR_POLL_SECONDS", default=30.0)

# SSH: optional — if RUNPOD_SSH_HOST is set, orchestrator runs RUNPOD_REMOTE_START_SCRIPT on the pod.
# Prefer RUNPOD_*; aliases SSH_HOST, SSH_PORT, SSH_USER, SSH_KEY_PATH (control_server / llm-gateway style).
RUNPOD_SSH_HOST = os.getenv("RUNPOD_SSH_HOST", "").strip()
RUNPOD_SSH_USER = (os.getenv("RUNPOD_SSH_USER") or os.getenv("SSH_USER") or "root").strip() or "root"
_ssh_port_raw = (os.getenv("RUNPOD_SSH_PORT") or os.getenv("SSH_PORT") or "").strip()
RUNPOD_SSH_PORT = int(_ssh_port_raw) if _ssh_port_raw else 22
RUNPOD_SSH_KEY_PATH = (os.getenv("RUNPOD_SSH_KEY_PATH") or os.getenv("SSH_KEY_PATH") or "").strip()
# PEM body (BEGIN … END …). Use in production instead of a local file path. Set via platform secret manager.
RUNPOD_SSH_PRIVATE_KEY = (os.getenv("RUNPOD_SSH_PRIVATE_KEY") or os.getenv("SSH_PRIVATE_KEY") or "").strip()
if not RUNPOD_SSH_HOST:
    RUNPOD_SSH_HOST = (os.getenv("SSH_HOST") or "").strip()
RUNPOD_REMOTE_START_SCRIPT = os.getenv("RUNPOD_REMOTE_START_SCRIPT", "/workspace/start_backend.sh").strip()
# When false, orchestrator never runs SSH (even if RUNPOD_SSH_HOST is set). HTTP-first: GraphQL
# resume + poll pod RUNNING + GET {proxy}{RUNPOD_ML_HEALTH_PATH} until 200.
RUNPOD_SSH_ENABLED = _env_bool("RUNPOD_SSH_ENABLED", default=False)
RUNPOD_SSH_MAX_RETRIES = _env_int("RUNPOD_SSH_MAX_RETRIES", 20)
RUNPOD_SSH_RETRY_DELAY_SEC = _env_float("RUNPOD_SSH_RETRY_DELAY_SEC", 5.0)
# After GraphQL reports RUNNING: optional extra wait before first ML HTTP check (proxy / GPU).
RUNPOD_POST_RESUME_GRACE_SEC = _env_float("RUNPOD_POST_RESUME_GRACE_SEC", 45.0)
# When ML HTTP is still down and SSH runs next: wait before Paramiko (sshd / port readiness).
RUNPOD_PRE_SSH_DELAY_SEC = _env_float("RUNPOD_PRE_SSH_DELAY_SEC", 60.0)
# Wait for ML HTTP readiness (GET {proxy}{RUNPOD_ML_HEALTH_PATH}) after pod RUNNING / optional SSH.
RUNPOD_ML_READY_TIMEOUT_SEC = _env_float("RUNPOD_ML_READY_TIMEOUT_SEC", 600.0)
# Path on ML server (Akshay backend) for document extract.
RUNPOD_ML_ACORD_EXTRACT_PATH = os.getenv("RUNPOD_ML_ACORD_EXTRACT_PATH", "/api/acord/extract").strip()
# Readiness GET path(s) on ML (comma-separated, tried in order). Prefer /health — always present on
# this FastAPI app; /docs returns 404 if OpenAPI UI is disabled (common in some deploys).
RUNPOD_ML_HEALTH_PATH = os.getenv(
    "RUNPOD_ML_HEALTH_PATH",
    "/health,/readyz,/docs,/openapi.json",
).strip() or "/health"
# Poll GraphQL until desiredStatus == RUNNING (after resume or cold start).
RUNPOD_POD_RUNNING_TIMEOUT_SEC = _env_float("RUNPOD_POD_RUNNING_TIMEOUT_SEC", 300.0)
RUNPOD_POD_RUNNING_POLL_INITIAL_SEC = _env_float("RUNPOD_POD_RUNNING_POLL_INITIAL_SEC", 3.0)
RUNPOD_POD_RUNNING_POLL_MAX_SEC = _env_float("RUNPOD_POD_RUNNING_POLL_MAX_SEC", 20.0)
# Exponential backoff between HTTP readiness checks toward the ML server.
RUNPOD_ML_HEALTH_POLL_INITIAL_SEC = _env_float("RUNPOD_ML_HEALTH_POLL_INITIAL_SEC", 2.0)
RUNPOD_ML_HEALTH_BACKOFF_MAX_SEC = _env_float("RUNPOD_ML_HEALTH_BACKOFF_MAX_SEC", 30.0)

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_CHAT_COMPLETIONS_URL = os.getenv("OPENAI_CHAT_COMPLETIONS_URL", "https://api.openai.com/v1/chat/completions")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Primary model name for structured extraction flows that are OpenAI-compatible.
# Used by pod extraction and some ACORD pipelines as a fallback when OPENAI_MODEL
# isn't explicitly configured.
DEFAULT_PRIMARY_LLM_MODEL = (
    os.getenv("DEFAULT_PRIMARY_LLM_MODEL", "").strip()
    or (OPENAI_MODEL or "").strip()
    or (DEFAULT_LLM_MODEL or "").strip()
    or DEFAULT_GROQ_MODEL
)

# Offline / local model endpoint configuration (used by pod_extraction and some routes).
OFFLINE_LLM_GENERATE_URL = os.getenv("OFFLINE_LLM_GENERATE_URL", "").strip()
OFFLINE_LLM_AUTH_TOKEN = os.getenv("OFFLINE_LLM_AUTH_TOKEN", "").strip()
OFFLINE_LLM_MODEL_NAME = os.getenv("OFFLINE_LLM_MODEL_NAME", "").strip()
try:
    OFFLINE_LLM_HTTP_TIMEOUT_SECONDS = float(os.getenv("OFFLINE_LLM_HTTP_TIMEOUT_SECONDS", "120").strip() or "120")
except ValueError:
    OFFLINE_LLM_HTTP_TIMEOUT_SECONDS = 120.0

# Anthropic Claude
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MESSAGES_URL = os.getenv("ANTHROPIC_MESSAGES_URL", "https://api.anthropic.com/v1/messages")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")

# ── LLM Fallback Service (ported from LLM Fallback 3) ────────────────────────
# Providers used by LLMFallbackService after Groq/RunPod:
#   HuggingFace → Gemini → OpenAI → Claude
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")
MOMENTO_API_KEY = os.getenv("MOMENTO_API_KEY", "")

# Cache backend for LLMFallbackService: "local" | "redis" | "momento"
# "local" works with zero extra dependencies (default)
LLM_CACHE_BACKEND = os.getenv("LLM_CACHE_BACKEND", "local")

# Set to "true" to enable semantic similarity caching
# Requires: pip install sentence-transformers numpy
LLM_SEMANTIC_CACHE_ENABLED = os.getenv("LLM_SEMANTIC_CACHE_ENABLED", "false")

# Optional pepper used when hashing personal API keys.
# Keep this value stable across deploys so existing key hashes remain valid.
PERSONAL_API_KEY_PEPPER = os.getenv("PERSONAL_API_KEY_PEPPER", "")

# Carrier credentials
# Used to Fernet-encrypt carrier portal passwords before storing in DB.
# Must be a stable, high-entropy secret — rotate with care (existing rows become unreadable).
# Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
CARRIER_CREDENTIAL_ENCRYPTION_KEY = os.getenv("CARRIER_CREDENTIAL_ENCRYPTION_KEY", "").strip()

# Webhooks
# Used to encrypt webhook signing secrets at rest in DB.
# Must be a stable, high-entropy secret (recommended: 32 urlsafe base64 bytes).
WEBHOOK_SECRET_ENCRYPTION_KEY = os.getenv("WEBHOOK_SECRET_ENCRYPTION_KEY", "").strip()
WEBHOOK_WORKER_ENABLED = _env_bool("WEBHOOK_WORKER_ENABLED", default=True)
WEBHOOK_MAX_ATTEMPTS = _env_int("WEBHOOK_MAX_ATTEMPTS", 4)  # SRS FR-13: 3 retries = 4 total attempts
WEBHOOK_RETRY_BASE_SECONDS = _env_float("WEBHOOK_RETRY_BASE_SECONDS", 2.0)
WEBHOOK_RETRY_MAX_SECONDS = _env_float("WEBHOOK_RETRY_MAX_SECONDS", 60.0)

# MLflow Tracking Server (REST API) — optional; used by /api/v1/model-registry/sync-mlflow
MLFLOW_TRACKING_URI = (os.getenv("MLFLOW_TRACKING_URI") or "").strip().rstrip("/")
MLFLOW_API_TOKEN = (os.getenv("MLFLOW_API_TOKEN") or "").strip()

# SeaweedFS (S3-compatible object store for GGUF model artifacts)
SEAWEEDFS_ENDPOINT = (os.getenv("SEAWEEDFS_ENDPOINT") or "").strip()
SEAWEEDFS_ACCESS_KEY = (os.getenv("SEAWEEDFS_ACCESS_KEY") or "").strip()
SEAWEEDFS_SECRET_KEY = (os.getenv("SEAWEEDFS_SECRET_KEY") or "").strip()
SEAWEEDFS_BUCKET = (os.getenv("SEAWEEDFS_BUCKET") or "").strip()

