import os

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_OPENAI_COMPAT_URL = os.getenv("GROQ_OPENAI_COMPAT_URL", "https://api.groq.com/openai/v1/chat/completions")
GROQ_MODEL_CHAT = os.getenv("GROQ_MODEL_CHAT", "llama-3.3-70b-versatile")
GROQ_MODEL_HELP = os.getenv("GROQ_MODEL_HELP", "llama-3.3-70b-versatile")
GROQ_MODEL_WORKFLOW = os.getenv("GROQ_MODEL_WORKFLOW", "llama-3.3-70b-versatile")
