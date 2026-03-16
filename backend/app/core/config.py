import os
from pathlib import Path


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
        if key and (key not in os.environ or not (os.environ.get(key) or "").strip()):
            os.environ[key] = value


_load_local_env_file()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_OPENAI_COMPAT_URL = os.getenv("GROQ_OPENAI_COMPAT_URL", "https://api.groq.com/openai/v1/chat/completions")
GROQ_MODEL_CHAT = os.getenv("GROQ_MODEL_CHAT", "llama-3.3-70b-versatile")
GROQ_MODEL_HELP = os.getenv("GROQ_MODEL_HELP", "llama-3.3-70b-versatile")
GROQ_MODEL_WORKFLOW = os.getenv("GROQ_MODEL_WORKFLOW", "llama-3.3-70b-versatile")

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

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_CHAT_COMPLETIONS_URL = os.getenv("OPENAI_CHAT_COMPLETIONS_URL", "https://api.openai.com/v1/chat/completions")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

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
