"""
LLM Fallback Service
Ported & adapted from LLM Fallback 3.

Full provider chain (priority order):
  1. Groq          – fast free tier (handled by upstream httpx streaming in llm.py)
  2. RunPod        – custom /generate or OpenAI-compat (handled upstream in llm.py)
  3. HuggingFace   – free inference API  ← this service picks up from here
  4. Gemini        – Google free tier
  5. OpenAI        – paid
  6. Claude        – paid, last resort

Features (ported from LLM Fallback 3):
  - Multi-provider fallback via litellm
  - Multi-layer caching: local / redis / momento
  - Optional semantic similarity cache
  - Confidence scoring
  - Token tracking
  - Auto sort by free-tier priority
"""

import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Literal, Optional

from .cache_backends import make_cache, LocalMemoryCache
from .models import CacheEntry, LLMModel, LLMResponse
from .semantic_cache import SEMANTIC_AVAILABLE, SemanticCacheManager

logger = logging.getLogger(__name__)

# litellm is required for this service
try:
    import litellm
    litellm.set_verbose = False  # suppress per-request debug noise
    _LITELLM_AVAILABLE = True
except ImportError:
    _LITELLM_AVAILABLE = False
    logger.warning(
        "litellm not installed — LLMFallbackService will be disabled. "
        "Install: pip install litellm"
    )

# ---------------------------------------------------------------------------
# Provider → env-var mapping  (mirrors LLM Fallback 3)
# ---------------------------------------------------------------------------
_PROVIDER_ENV_MAP: Dict[str, str] = {
    "groq": "GROQ_API_KEY",
    "huggingface": "HUGGINGFACE_API_KEY",
    "deepinfra": "DEEPINFRA_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "fireworks": "FIREWORKS_API_KEY",
    "together": "TOGETHER_API_KEY",
    "cloudflare": "CLOUDFLARE_API_KEY",
    "novita": "NOVITA_API_KEY",
    "sambanova": "SAMBANOVA_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}

# Free-tier priority (lower = better, matches LLM Fallback 3)
_FREE_TIER_PRIORITY: Dict[str, int] = {
    "groq": 1,
    "huggingface": 2,
    "deepinfra": 2,
    "openrouter": 2,
    "fireworks": 3,
    "together": 3,
    "cloudflare": 3,
    "novita": 3,
    "sambanova": 3,
    "gemini": 4,
    "perplexity": 4,
    "openai": 5,
    "anthropic": 6,
}


# ---------------------------------------------------------------------------
# Default provider chain used by llm.py after Groq/RunPod fail
# ---------------------------------------------------------------------------

def build_default_fallback_chain() -> List[LLMModel]:
    """
    Build the default fallback chain from configured env vars.
    Returns models that have API keys available — skips unconfigured ones.
    Priority: HuggingFace(2) → Gemini(4) → OpenAI(5) → Claude(6)
    """
    candidates: List[LLMModel] = [
        LLMModel(
            name="meta-llama/Llama-3.1-8B-Instruct",
            provider="huggingface",
            priority=2,
        ),
        LLMModel(
            name="Qwen/Qwen2.5-7B-Instruct",
            provider="huggingface",
            priority=2,
        ),
        LLMModel(
            name="gemini-1.5-flash-001",
            provider="gemini",
            priority=4,
        ),
        LLMModel(
            name="gpt-4o-mini",
            provider="openai",
            priority=5,
        ),
        LLMModel(
            name="claude-3-5-sonnet-20241022",
            provider="anthropic",
            priority=6,
        ),
    ]

    available: List[LLMModel] = []
    for m in candidates:
        env_var = _PROVIDER_ENV_MAP.get((m.provider or "").lower(), "")
        key = os.getenv(env_var, "").strip() if env_var else ""
        if key:
            available.append(m)

    return available


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class LLMFallbackService:
    """
    Core LLM fallback service with multi-provider support and caching.

    Usage in llm.py:
        service = LLMFallbackService()
        result = await service.execute(messages=[...])
        if result.success:
            # wrap result.content in SSE stream

    Mirrors LLM Fallback 3's LLMService API but is fully async.
    """

    def __init__(
        self,
        cache_backend: Literal["local", "redis", "momento"] = "local",
        semantic_caching: bool = False,
        similarity_threshold: float = 0.85,
        embedding_model: str = "all-MiniLM-L6-v2",
        auto_sort_by_free_tier: bool = True,
    ):
        self.cache_backend_name = cache_backend
        self.semantic_caching = semantic_caching
        self.auto_sort_by_free_tier = auto_sort_by_free_tier

        self._cache = make_cache(cache_backend)

        self._semantic: Optional[SemanticCacheManager] = None
        if semantic_caching and SEMANTIC_AVAILABLE:
            try:
                persistence = self._cache if hasattr(self._cache, "save_embedding") else None
                self._semantic = SemanticCacheManager(
                    embedding_model=embedding_model,
                    similarity_threshold=similarity_threshold,
                    persistence_backend=persistence,
                )
            except Exception as exc:
                logger.warning(f"Semantic cache init failed: {exc}")

        logger.info(
            f"LLMFallbackService ready — cache={cache_backend}, semantic={semantic_caching}, "
            f"litellm={'yes' if _LITELLM_AVAILABLE else 'NO (install litellm)'}"
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_api_key(self, model: LLMModel) -> str:
        if model.api_key:
            return model.api_key
        env_var = _PROVIDER_ENV_MAP.get((model.provider or "").lower(), "")
        key = os.getenv(env_var, "").strip() if env_var else ""
        if key:
            return key
        raise ValueError(
            f"No API key for provider '{model.provider}'. "
            f"Set {env_var} in backend/.env"
        )

    def _generate_cache_key(self, messages: List[Dict[str, Any]], model_name: str) -> str:
        payload = {"messages": messages, "model": model_name}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def _sort_by_free_tier(self, models: List[LLMModel]) -> List[LLMModel]:
        if not self.auto_sort_by_free_tier:
            return models
        return sorted(
            models,
            key=lambda m: _FREE_TIER_PRIORITY.get((m.provider or "").lower(), 999),
        )

    def _confidence_score(self, response: Any, model_id: str) -> float:
        try:
            if hasattr(response, "choices") and response.choices:
                reason = getattr(response.choices[0], "finish_reason", None)
                score = {"stop": 0.95, "length": 0.60, "tool_calls": 0.90}.get(reason, 0.75)
                # Anthropic cache-read bonus
                if "anthropic" in model_id.lower():
                    usage = getattr(response, "usage", None)
                    if usage and getattr(usage, "cache_read_input_tokens", 0) > 0:
                        score = min(0.98, score + 0.05)
                return score
        except Exception:
            pass
        return 0.80

    def _user_text(self, messages: List[Dict[str, Any]]) -> str:
        return " ".join(m.get("content", "") for m in messages if m.get("role") == "user")

    def _semantic_cache_response(self, messages: List[Dict[str, Any]]) -> Optional[LLMResponse]:
        if not self._semantic:
            return None
        try:
            emb = self._semantic.get_embedding(self._user_text(messages))
            match = self._semantic.find_similar(emb)
            if not match:
                return None
            score, sim_key = match
            cached = self._cache.get(sim_key)
            if not cached:
                return None
            logger.info(f"Semantic cache hit ({score:.2%})")
            return LLMResponse(
                content=cached.content,
                tokens=cached.tokens,
                model=cached.model_used or "",
                cached=True,
                success=True,
                confidence_score=cached.confidence_score,
                cache_method="semantic",
            )
        except Exception as exc:
            logger.warning(f"Semantic cache lookup failed: {exc}")
            return None

    def _exact_cache_method(self, cache_key: str) -> str:
        if hasattr(self._cache, "permanent_cache") and cache_key in getattr(self._cache, "permanent_cache", {}):
            return "permanent"
        return "exact"

    def _exact_cache_response(self, cache_key: str) -> Optional[LLMResponse]:
        cached = self._cache.get(cache_key)
        if not cached:
            return None
        logger.info("Exact cache hit")
        return LLMResponse(
            content=cached.content,
            tokens=cached.tokens,
            model=cached.model_used or "",
            cached=True,
            success=True,
            confidence_score=cached.confidence_score,
            cache_method=self._exact_cache_method(cache_key),
        )

    def _cache_success(
        self,
        cache_key: str,
        messages: List[Dict[str, Any]],
        model: LLMModel,
        result: Dict[str, Any],
        cache_permanent: bool,
    ) -> None:
        entry = CacheEntry(
            content=result["content"],
            tokens=result["tokens"],
            timestamp=time.time(),
            confidence_score=result["confidence_score"],
            model_used=model.name,
        )
        if self._semantic:
            try:
                emb = self._semantic.get_embedding(self._user_text(messages))
                entry.embedding = emb
                self._semantic.add_to_index(emb, cache_key)
            except Exception as exc:
                logger.warning(f"Semantic index add failed: {exc}")

        if cache_permanent:
            self._cache.set_permanent(cache_key, entry)
        else:
            self._cache.set(cache_key, entry)

    def _success_response(self, model: LLMModel, result: Dict[str, Any], fallback_count: int) -> LLMResponse:
        return LLMResponse(
            content=result["content"],
            tokens=result["tokens"],
            model=model.name,
            success=True,
            fallback_count=fallback_count,
            confidence_score=result["confidence_score"],
            cache_method="none",
        )

    async def _call_model(
        self,
        model: LLMModel,
        messages: List[Dict[str, Any]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Call one provider via litellm.acompletion. Returns dict or None."""
        if not _LITELLM_AVAILABLE:
            raise RuntimeError("litellm not installed — run: pip install litellm")

        api_key = self._get_api_key(model)
        model_id = f"{model.provider}/{model.name}" if model.provider else model.name

        params: Dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "api_key": api_key,
            "max_tokens": max_tokens or 1024,
        }
        if model.api_base:
            params["api_base"] = model.api_base
        if temperature is not None:
            params["temperature"] = temperature

        logger.info(f"LLMFallback → calling {model_id}")
        response = await litellm.acompletion(**params)

        content = ""
        if response.choices:
            content = response.choices[0].message.content or ""
        tokens = 0
        if hasattr(response, "usage") and response.usage:
            tokens = (response.usage.prompt_tokens or 0) + (response.usage.completion_tokens or 0)

        return {
            "content": content,
            "tokens": tokens,
            "response": response,
            "confidence_score": self._confidence_score(response, model_id),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute(
        self,
        messages: List[Dict[str, Any]],
        models: Optional[List[LLMModel]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        cache_permanent: bool = True,
    ) -> LLMResponse:
        """
        Try each model in priority order until one succeeds.

        Args:
            messages:        Full message list (system + user + history)
            models:          Provider chain — defaults to build_default_fallback_chain()
            temperature:     LLM temperature
            max_tokens:      Max tokens per response
            cache_permanent: Store successful responses permanently

        Returns:
            LLMResponse with content, tokens, model, success flag, errors list
        """
        if models is None:
            models = build_default_fallback_chain()

        if not models:
            return LLMResponse(
                content="",
                tokens=0,
                model="",
                success=False,
                errors=["No fallback providers configured or all API keys missing"],
            )

        models = self._sort_by_free_tier(models)
        cache_key = self._generate_cache_key(messages, models[0].name)

        semantic_cached = self._semantic_cache_response(messages)
        if semantic_cached:
            return semantic_cached

        exact_cached = self._exact_cache_response(cache_key)
        if exact_cached:
            return exact_cached

        # ── Provider loop ─────────────────────────────────────────────
        errors: List[str] = []
        fallback_count = 0

        for idx, model in enumerate(models):
            if idx > 0:
                fallback_count += 1
                logger.info(f"Falling back to provider {idx + 1}/{len(models)}: {model.provider}/{model.name}")

            try:
                result = await self._call_model(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                if result and result.get("content") is not None:
                    self._cache_success(cache_key, messages, model, result, cache_permanent)
                    return self._success_response(model, result, fallback_count)

            except Exception as exc:
                err = f"{model.provider}/{model.name}: {exc}"
                errors.append(err)
                logger.warning(f"LLMFallback provider failed: {err}")

        return LLMResponse(
            content="",
            tokens=0,
            model="",
            success=False,
            errors=errors,
            fallback_count=fallback_count,
        )

    # ------------------------------------------------------------------
    def get_cache_stats(self) -> Dict[str, Any]:
        stats = self._cache.get_stats()
        if self._semantic:
            stats["semantic"] = self._semantic.get_stats()
        return stats

    def clear_cache(self) -> None:
        self._cache.clear()
        logger.info("LLMFallbackService cache cleared")
