import os, gc, json, hashlib, subprocess, time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel


def load_env():
    """Load config.env into os.environ."""
    env_path = os.path.join(os.path.dirname(__file__), "config.env")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()


def sha256_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sign_file(filepath: str):
    """Create GPG detached signature. Requires GPG key imported on node."""
    subprocess.run(
        ["gpg", "--batch", "--yes", "--detach-sign", filepath],
        check=True,
    )


def download_base_model():
    """Download base model from HF Hub if not already present."""
    base_path = os.environ["BASE_MODEL_PATH"]
    model_id  = os.environ["BASE_MODEL_ID"]
    if os.path.isdir(base_path) and os.listdir(base_path):
        print(f"Base model already at {base_path}, skipping download.")
        return
    print(f"Downloading {model_id} to {base_path}...")
    from huggingface_hub import snapshot_download
    snapshot_download(
        repo_id=model_id,
        local_dir=base_path,
        token=os.environ.get("HF_TOKEN"),
    )


def main():
    load_env()
    out_dir = os.environ["OUTPUT_DIR"]
    os.makedirs(out_dir, exist_ok=True)
    pipeline_start = time.time()

    # ── Step 1: Download base model ─────────────────────────────────
    download_base_model()

    # ── Step 2: Load and merge LoRA adapter ─────────────────────────
    print("Loading base model...")
    t0 = time.time()
    tokenizer  = AutoTokenizer.from_pretrained(os.environ["BASE_MODEL_PATH"])
    base_model = AutoModelForCausalLM.from_pretrained(
        os.environ["BASE_MODEL_PATH"],
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    model = PeftModel.from_pretrained(base_model, os.environ["ADAPTER_PATH"])
    print(f"  Loaded in {time.time()-t0:.0f}s")

    print("Merging LoRA adapter (merge_and_unload)...")
    t0 = time.time()
    merged = model.merge_and_unload()
    merged_path = os.path.join(out_dir, "merged_bf16")
    merged.save_pretrained(merged_path)
    tokenizer.save_pretrained(merged_path)
    print(f"  Merged in {time.time()-t0:.0f}s")

    # Free VRAM before quantization
    del model, base_model, merged
    gc.collect()
    torch.cuda.empty_cache()

    # ── Step 3: Convert merged BF16 to GGUF FP16 ────────────────────
    fp16_path = os.path.join(out_dir, "model-fp16.gguf")
    print("Converting to GGUF FP16 (CI reference)...")
    t0 = time.time()
    subprocess.run([
        "llama-convert-hf-to-gguf",
        merged_path,
        "--outtype", "f16",
        "--outfile", fp16_path,
    ], check=True)
    print(f"  FP16 GGUF ready in {time.time()-t0:.0f}s")

    # ── Step 4: Quantize to Q5_K_M and Q4_K_M ───────────────────────
    quantizations = ["Q5_K_M", "Q4_K_M"]
    artifacts = []

    for q_name in quantizations:
        out_path = os.path.join(out_dir, f"model-{q_name.lower()}.gguf")
        print(f"Quantizing {q_name}...")
        t0 = time.time()
        subprocess.run(["llama-quantize", fp16_path, out_path, q_name], check=True)
        print(f"  {q_name} done in {time.time()-t0:.0f}s  size={os.path.getsize(out_path)//1_000_000}MB")

        sha = sha256_file(out_path)
        sign_file(out_path)
        artifacts.append({
            "filename":    f"model-{q_name.lower()}.gguf",
            "quant_level": q_name.lower(),
            "sha256":      f"sha256:{sha}",
            "size_bytes":  os.path.getsize(out_path),
            "sig_file":    f"model-{q_name.lower()}.gguf.sig",
        })

    # ── Step 5: Write manifest.json ──────────────────────────────────
    manifest = {
        "adapter_version":  os.environ["MODEL_VERSION"],
        "schema_version":   "2.0",
        "domain":           os.environ["DOMAIN"],
        "min_electron_ver": os.environ["MIN_ELECTRON_VER"],
        "canary_pct":       int(os.environ["CANARY_PCT"]),
        "rollback_safe":    os.environ["ROLLBACK_SAFE"].lower() == "true",
        "artifacts":        artifacts,
    }
    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    elapsed = time.time() - pipeline_start
    print(f"Quantization complete in {elapsed:.0f}s. Artifacts in {out_dir}")


if __name__ == "__main__":
    main()
