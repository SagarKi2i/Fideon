"""
GGUF quantization — runs after AdapterMerger produces a merged HF model.

Requires llama.cpp tools in PATH:
  llama-convert-hf-to-gguf   (HF safetensors → GGUF FP16)
  llama-quantize              (FP16 GGUF → Q5_K_M / Q4_K_M)

Install once on the pod:
  bash /workspace/ai-ml/setup.sh

If the binaries are not found, quantization is skipped non-fatally and an
empty dict is returned — the pipeline continues and only the HF model is
uploaded to SeaweedFS.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

QUANT_LEVELS: List[str] = ["Q4_K_M"]


def tools_available() -> bool:
    return (
        shutil.which("llama-convert-hf-to-gguf") is not None
        and shutil.which("llama-quantize") is not None
    )


def run_quantization(
    merged_model_path: str,
    output_dir: str,
    version: int,
) -> Dict[str, str]:
    """
    Convert merged HF model → GGUF FP16 → Q5_K_M + Q4_K_M.

    Parameters
    ----------
    merged_model_path : local path to the merged HF model directory
    output_dir        : where GGUF files will be written
    version           : SLM version number (written into manifest.json)

    Returns
    -------
    Dict mapping quant level key → local GGUF path.
    e.g. {"q5_k_m": "/path/model-q5_k_m.gguf", "q4_k_m": "/path/model-q4_k_m.gguf"}
    Returns {} if llama.cpp tools are not installed.
    """
    if not tools_available():
        print("[quantizer] llama-convert-hf-to-gguf or llama-quantize not found — skipping.")
        print("[quantizer] To enable: bash /workspace/ai-ml/setup.sh --skip-pip")
        return {}

    # Free GPU VRAM left over from the merge step before running llama-quantize
    # (llama-quantize is compiled with DGGML_CUDA=ON and uses the H100 directly)
    try:
        import gc, torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            print("[quantizer] VRAM freed — GPU ready for quantization.")
    except Exception:
        pass

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Step 1: HF safetensors → GGUF FP16
    fp16_path = out / "model-fp16.gguf"
    print(f"[quantizer] Converting HF model → GGUF FP16 …")
    subprocess.run(
        [
            "llama-convert-hf-to-gguf",
            merged_model_path,
            "--outtype", "f16",
            "--outfile", str(fp16_path),
        ],
        check=True,
    )
    print(f"[quantizer] FP16 GGUF ready ({fp16_path.stat().st_size // 1_000_000} MB)")

    # Step 2: Quantize each level
    results: Dict[str, str] = {}
    for q_name in QUANT_LEVELS:
        key = q_name.lower()
        out_path = out / f"model-{key}.gguf"
        print(f"[quantizer] Quantizing → {q_name} …")
        subprocess.run(
            ["llama-quantize", str(fp16_path), str(out_path), q_name],
            check=True,
        )
        size_mb = out_path.stat().st_size // 1_000_000
        print(f"[quantizer] {q_name} done ({size_mb} MB) → {out_path}")
        results[key] = str(out_path)

    # Remove fp16 intermediate — it's 16 GB and not uploaded or used further
    fp16_path.unlink()
    print(f"[quantizer] Removed fp16 intermediate ({fp16_path.name})")

    # Step 3: Write manifest.json
    manifest = {
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "artifacts": [
            {
                "quant_level": k,
                "filename": f"model-{k}.gguf",
                "size_bytes": Path(v).stat().st_size,
            }
            for k, v in results.items()
        ],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[quantizer] Done — {len(results)} GGUF artifacts in {output_dir}")
    return results
