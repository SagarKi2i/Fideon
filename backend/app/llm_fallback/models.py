"""
Data models for LLM Fallback Service.
Ported from LLM Fallback 3 with optional numpy dependency.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any

try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False


@dataclass
class LLMModel:
    """
    Represents a single LLM provider + model configuration.

    Attributes:
        name:       Model name (e.g. "llama-3.3-70b-versatile", "gpt-4o-mini")
        provider:   Provider slug used by litellm (e.g. "groq", "openai", "anthropic",
                    "huggingface", "gemini")
        api_key:    Explicit key — if omitted the service reads it from env
        api_base:   Optional override URL (RunPod OpenAI-compat, offline vLLM, etc.)
        priority:   Lower = tried first in sorted chains
        free_tier:  Informational — set automatically for known free providers
    """

    name: str
    provider: Optional[str] = None
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    priority: int = 100
    free_tier: bool = False

    _FREE_PROVIDERS = {
        "groq", "huggingface", "deepinfra", "openrouter",
        "fireworks", "together", "cloudflare", "novita",
        "sambanova", "gemini", "perplexity",
    }

    def __post_init__(self) -> None:
        if self.provider and self.provider.lower() in self._FREE_PROVIDERS:
            self.free_tier = True


@dataclass
class CacheEntry:
    """Cached LLM response with metadata."""

    content: str
    tokens: int
    timestamp: float
    confidence_score: float = 1.0
    parsed_json: Optional[Dict[str, Any]] = None
    model_used: Optional[str] = None
    cache_hits: int = 0
    embedding: Optional[Any] = None  # numpy array when available

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "content": self.content,
            "tokens": self.tokens,
            "timestamp": self.timestamp,
            "confidence_score": self.confidence_score,
            "parsed_json": self.parsed_json,
            "model_used": self.model_used,
            "cache_hits": self.cache_hits,
            "embedding": None,
        }
        if self.embedding is not None and _NUMPY_AVAILABLE:
            data["embedding"] = self.embedding.tolist()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        embedding = None
        raw_emb = data.get("embedding")
        if raw_emb is not None and _NUMPY_AVAILABLE:
            import numpy as np
            embedding = np.array(raw_emb)
        return cls(
            content=data.get("content", ""),
            tokens=data.get("tokens", 0),
            timestamp=data.get("timestamp", 0.0),
            confidence_score=data.get("confidence_score", 1.0),
            parsed_json=data.get("parsed_json"),
            model_used=data.get("model_used"),
            cache_hits=data.get("cache_hits", 0),
            embedding=embedding,
        )


@dataclass
class LLMResponse:
    """
    Unified response from LLMFallbackService.

    Attributes:
        content:         Text content returned by the model
        tokens:          Approximate token count
        model:           Model name that produced the response
        success:         True when at least one provider succeeded
        cached:          True when served from cache
        errors:          Accumulated error strings from failed providers
        confidence_score: 0.0–1.0 quality estimate
        cache_method:    "exact" | "permanent" | "none"
        fallback_count:  How many providers were skipped before success
    """

    content: str
    tokens: int
    model: str
    success: bool = True
    cached: bool = False
    errors: Optional[List[str]] = None
    confidence_score: float = 1.0
    cache_method: str = "none"
    fallback_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "tokens": self.tokens,
            "model": self.model,
            "success": self.success,
            "cached": self.cached,
            "errors": self.errors,
            "confidence_score": self.confidence_score,
            "cache_method": self.cache_method,
            "fallback_count": self.fallback_count,
        }
