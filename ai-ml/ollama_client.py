"""
Ollama HTTP client for ACORD extraction and policy comparison.

Wraps the Ollama /api/chat endpoint.
Supports both text-only and vision (base64-encoded page images).

Usage:
    from ollama_client import OllamaClient

    client = OllamaClient()
    response = client.chat(prompt="Extract fields...", images=[pil_img1, pil_img2])

Required env vars:
    OLLAMA_HOST         (default: http://localhost:11434)
    OLLAMA_MODEL_NAME   (default: fideon-acord)
    OLLAMA_TIMEOUT_SEC  (default: 600)
"""
from __future__ import annotations

import base64
import io
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

OLLAMA_HOST    = os.getenv("OLLAMA_HOST",           "http://localhost:11434")
OLLAMA_MODEL   = os.getenv("OLLAMA_MODEL_NAME",     "fideon-acord")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT_SEC", "600"))


class OllamaClient:
    """
    Thin wrapper around the Ollama /api/chat REST endpoint.

    All requests are synchronous (blocking). Designed to be called from
    background threads in server.py (same pattern as the transformers path).
    """

    def __init__(
        self,
        host:    str = OLLAMA_HOST,
        model:   str = OLLAMA_MODEL,
        timeout: int = OLLAMA_TIMEOUT,
    ) -> None:
        self.host    = host.rstrip("/")
        self.model   = model
        self.timeout = timeout

    # ── Health ───────────────────────────────────────────────────────────────

    def is_ready(self) -> bool:
        """Return True if Ollama is up and the target model is loaded."""
        try:
            with urllib.request.urlopen(f"{self.host}/api/tags", timeout=5) as resp:
                data = json.loads(resp.read())
                names = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
                return self.model in names
        except Exception:
            return False

    def wait_until_ready(self, timeout_sec: int = 120) -> None:
        """Block until Ollama is up and model is loaded, or raise RuntimeError."""
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if self.is_ready():
                return
            time.sleep(3)
        raise RuntimeError(
            f"Ollama model '{self.model}' not ready at {self.host} after {timeout_sec}s. "
            "Run model_loader.py to download and register the model."
        )

    # ── Image encoding ───────────────────────────────────────────────────────

    @staticmethod
    def _encode_image(img) -> str:
        """Convert a PIL Image to a base64 string (JPEG, quality 85)."""
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    # ── Core chat call ───────────────────────────────────────────────────────

    def chat(
        self,
        prompt: str,
        images: Optional[List[Any]] = None,
        system: Optional[str] = None,
        temperature: float = 0.1,
        num_ctx: int = 8192,
        max_tokens: int = 4096,
    ) -> str:
        """
        Send a chat request to Ollama.

        Args:
            prompt:      User message text.
            images:      Optional list of PIL Images (encoded as base64 JPEG).
            system:      Optional system message override.
            temperature: Sampling temperature.
            num_ctx:     Context window size (tokens).
            max_tokens:  Maximum tokens to generate.

        Returns:
            The assistant's reply as a plain string.
        """
        messages: List[Dict[str, Any]] = []

        if system:
            messages.append({"role": "system", "content": system})

        user_msg: Dict[str, Any] = {"role": "user", "content": prompt}
        if images:
            user_msg["images"] = [self._encode_image(img) for img in images]
        messages.append(user_msg)

        payload = {
            "model":   self.model,
            "messages": messages,
            "stream":  False,
            "options": {
                "temperature": temperature,
                "num_ctx":     num_ctx,
                "num_predict": max_tokens,
            },
        }

        body = json.dumps(payload).encode("utf-8")
        req  = urllib.request.Request(
            f"{self.host}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(
                f"Ollama /api/chat returned HTTP {exc.code}: {raw}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc

        return (data.get("message") or {}).get("content") or ""

    # ── Convenience wrappers ─────────────────────────────────────────────────

    def extract_acord_fields(
        self,
        prompt: str,
        images: Optional[List[Any]] = None,
    ) -> str:
        """
        Call Ollama for ACORD field extraction.
        Mirrors the interface previously used by _run_qwen_extraction().
        """
        return self.chat(
            prompt=prompt,
            images=images,
            num_ctx=8192,
            max_tokens=4096,
            temperature=0.1,
        )

    def compare_policies(
        self,
        prompt: str,
    ) -> str:
        """
        Call Ollama for policy comparison (text-only — no images needed).
        Uses a larger context window to handle full policy documents.
        """
        return self.chat(
            prompt=prompt,
            images=None,
            num_ctx=16384,
            max_tokens=8192,
            temperature=0.1,
        )
