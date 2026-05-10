from __future__ import annotations

import asyncio
import logging
import os
from functools import partial
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from fine_tuning.inference import (
    generate as local_generate,
    generate_from_raw_prompt,
    load_base_model_only,
    load_model_for_inference,
)

logger = logging.getLogger("fideon.local_generate")
router = APIRouter()

_MODEL_CACHE: dict[str, tuple[Any, Any]] = {}
# Serialize model loading + generation so two concurrent requests
# don't race to load the model or cause GPU OOM.
_GPU_LOCK = asyncio.Lock()


class GenerateRequest(BaseModel):
    # Matches the payload sent by `app.services.llm` offline mode.
    prompt: Optional[str] = None
    # Optional: used to pick `${POD_ADAPTERS_ROOT}/pods/<pod_id>/CURRENT`.
    pod_id: Optional[str] = None
    # model field accepted but used only for logging; actual model is from env/adapter.
    model: Optional[str] = None
    max_new_tokens: Optional[int] = 256
    temperature: Optional[float] = 0.0
    # When True (default), send prompt directly to the model without template wrapping.
    # Set to False only when calling from a fine-tuning context that needs ### Instruction format.
    raw: Optional[bool] = True


def _default_pod_adapter_root() -> Path:
    # backend/app/routes/local_generate.py -> backend/
    backend_dir = Path(__file__).resolve().parents[2]
    return Path(os.getenv("POD_ADAPTERS_ROOT") or (backend_dir / "fine_tuning" / "runs"))


def _read_current_adapter(pod_id: str) -> Optional[Path]:
    adapter_root = _default_pod_adapter_root()
    current_file = adapter_root / "pods" / pod_id / "CURRENT"
    if not current_file.exists():
        return None
    raw = current_file.read_text(encoding="utf-8", errors="replace").strip()
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = current_file.parent / raw
    p = p.resolve()
    return p if p.exists() else None


def _adapter_base_model() -> str:
    # Prefer local path for speed/offline.
    explicit = (
        os.getenv("FINE_TUNE_BASE_MODEL")
        or os.getenv("POD_ADAPTER_BASE_MODEL")
        or ""
    ).strip()
    if explicit:
        return explicit

    # RunPod model registry mode:
    # - MODEL_REGISTRY_ROOT=/workspace/models
    # - CURRENT_MODEL_FILE=/workspace/current_model.txt (optional)
    # If pointer exists and points to vN, use /workspace/models/vN as the base.
    registry_root = (os.getenv("MODEL_REGISTRY_ROOT") or "").strip()
    current_model_file = (
        (os.getenv("CURRENT_MODEL_FILE") or "").strip()
        or "/workspace/current_model.txt"
    )
    if registry_root:
        pointer = Path(current_model_file)
        if pointer.exists():
            version_name = pointer.read_text(encoding="utf-8", errors="replace").strip()
            if version_name:
                candidate = Path(registry_root) / version_name
                if candidate.exists():
                    return str(candidate)

    return "/workspace/models/qwen2.5-14b-instruct"


def _load_model_sync(base_model: str, adapter_path: Optional[Path]) -> tuple[Any, Any]:
    """Blocking model load — call via run_in_executor to avoid blocking the event loop."""
    if adapter_path:
        return load_model_for_inference(
            base_model,
            adapter_path,
            load_in_4bit=True,
            use_auth_token=False,
            local_files_only=True,
        )
    return load_base_model_only(
        base_model,
        load_in_4bit=True,
        use_auth_token=False,
        local_files_only=True,
    )


async def _get_model(base_model: str, adapter_path: Optional[Path]) -> tuple[Any, Any]:
    """Return cached model or load it in a thread (non-blocking for the event loop)."""
    cache_key = f"{base_model}|{str(adapter_path.resolve()) if adapter_path else 'base_only'}"
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]
    # Acquire GPU lock so concurrent requests don't both try to load.
    async with _GPU_LOCK:
        if cache_key in _MODEL_CACHE:  # re-check after acquiring lock
            return _MODEL_CACHE[cache_key]
        logger.info("Loading model %s (adapter=%s) …", base_model, adapter_path)
        loop = asyncio.get_running_loop()
        model, tokenizer = await loop.run_in_executor(
            None, partial(_load_model_sync, base_model, adapter_path)
        )
        _MODEL_CACHE[cache_key] = (model, tokenizer)
        logger.info("Model loaded and cached: %s", cache_key)
        return model, tokenizer


async def startup_warmup() -> None:
    """Called by the FastAPI lifespan in factory.py.

    Blocks application startup until the model is fully loaded into GPU memory.
    On RunPod this takes ~2 minutes on first start, but every subsequent request
    is served from the warm cache in ~33s — eliminating Cloudflare 524 cold-start
    timeouts entirely.

    On a developer laptop where the model path does not exist the function returns
    immediately so local development is unaffected.
    """
    base = _adapter_base_model()
    is_local_path = base.startswith("/") or base.startswith("\\") or (len(base) > 2 and base[1] == ":")
    if is_local_path and not Path(base).exists():
        logger.debug(
            "Model path %s does not exist on this machine; skipping startup pre-warm.",
            base,
        )
        return
    cache_key = f"{base}|base_only"
    if cache_key in _MODEL_CACHE:
        logger.debug("Model already cached; skipping startup pre-warm.")
        return
    logger.info("Startup: loading model %s into GPU — server will accept connections once done …", base)
    loop = asyncio.get_running_loop()
    try:
        model, tokenizer = await loop.run_in_executor(
            None, partial(_load_model_sync, base, None)
        )
        _MODEL_CACHE[cache_key] = (model, tokenizer)
        logger.info("Startup: model %s loaded and cached. Ready to serve requests.", base)
    except Exception as exc:
        logger.warning(
            "Startup model load failed (%s). First request will trigger a fresh load attempt.", exc
        )


@router.post("/generate")
async def generate(req: GenerateRequest):
    prompt = (req.prompt or "").strip()
    if not prompt:
        return {"response": ""}

    pod_id = (req.pod_id or "").strip() or None
    base_model = _adapter_base_model()
    adapter_path: Optional[Path] = None
    if pod_id:
        adapter_path = _read_current_adapter(pod_id)

    model, tokenizer = await _get_model(base_model, adapter_path)

    max_new_tokens = int(req.max_new_tokens or 256)
    temperature = float(req.temperature if req.temperature is not None else 0.0)
    use_raw = req.raw is not False  # default True; only False when explicitly set

    loop = asyncio.get_running_loop()

    # Run the blocking GPU call in a thread executor so the event loop is not frozen.
    if use_raw:
        text = await loop.run_in_executor(
            None,
            partial(generate_from_raw_prompt, model, tokenizer, prompt,
                    max_new_tokens=max_new_tokens, temperature=temperature),
        )
    else:
        text = await loop.run_in_executor(
            None,
            partial(local_generate, model, tokenizer, prompt, "",
                    max_new_tokens=max_new_tokens, temperature=temperature,
                    do_sample=temperature > 0),
        )
    return {"response": text}

