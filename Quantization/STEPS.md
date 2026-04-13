# Quantization Pipeline — Step-by-Step Guide

Complete guide from renting the Vast.ai node to having the model registered in Supabase.

---

## Files in This Folder

| File | Purpose |
|---|---|
| `setup.sh` | Run once on the node — installs llama.cpp (CUDA) + Python deps |
| `config.env.example` | Copy to `config.env` and fill in your values |
| `quantize.py` | Downloads base model, merges LoRA adapter → BF16 → FP16 GGUF → Q5_K_M → Q4_K_M |
| `upload.py` | Verifies + uploads GGUF + .sig files to SeaweedFS, registers in Supabase |
| `run_pipeline.sh` | Master script — validates env, then runs quantize.py then upload.py |
| `requirements.txt` | Python dependencies |

---

## PHASE 0 — Before You Start (Do This on Your Local Machine)

### 0.1 — Prepare your config.env
```bash
cd Quantization/
cp config.env.example config.env
```

Fill in `config.env` with your actual values:

```bash
# SeaweedFS (S3-compatible — your infra team provides these)
SEAWEEDFS_ENDPOINT=https://<seaweedfs-filer-ip>:8333
SEAWEEDFS_ACCESS_KEY=<your-access-key>
SEAWEEDFS_SECRET_KEY=<your-secret-key>
SEAWEEDFS_BUCKET=<your-bucket-name>

# Supabase
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>

# Model
BASE_MODEL_ID=Qwen/Qwen2.5-14B-Instruct
BASE_MODEL_PATH=/workspace/base_model
ADAPTER_PATH=/workspace/adapter
OUTPUT_DIR=/workspace/gguf_output
MODEL_VERSION=1.2.0
DOMAIN=broker

# Rollout config
MIN_ELECTRON_VER=28.0.0
CANARY_PCT=5
ROLLBACK_SAFE=true

# Optional: HuggingFace token (needed if model is gated)
HF_TOKEN=hf_...
```

### 0.2 — Export your GPG release private key (on your local machine)
```bash
# Find your key ID
gpg --list-secret-keys

# Export the private key
gpg --export-secret-keys --armor <KEY-ID> > release-private.key
```
You will import this on the Vast.ai node before running the pipeline.

### 0.3 — Know where your adapter is
After training, your LoRA adapter folder contains:
```
adapter_model.safetensors
adapter_config.json
tokenizer.json
tokenizer_config.json
special_tokens_map.json
```

---

## PHASE 1 — Rent Vast.ai Node

1. Go to vast.ai
2. Select template: **PyTorch (Vast)**
3. Filter: `1X GPU` · search `A100 SXM4`
4. Pick an instance with at least **80 GB VRAM** and 99%+ reliability
5. Set **Container Disk to 200 GB** (FP16 GGUF is ~28 GB, plus base model ~30 GB)
6. Click **RENT**
7. Wait ~2–3 min for it to boot
8. Vast.ai will show you an SSH command like:
   ```
   ssh root@123.45.67.89 -p 12345
   ```

---

## PHASE 2 — Transfer Files to the Node

Open a terminal on your local machine.

### 2.1 — Transfer the Quantization folder
```bash
scp -P <PORT> -r ./Quantization root@<IP>:/workspace/
```

### 2.2 — Transfer your LoRA adapter
```bash
scp -P <PORT> -r ./path/to/your/adapter root@<IP>:/workspace/adapter
```

### 2.3 — Transfer your GPG private key
```bash
scp -P <PORT> ./release-private.key root@<IP>:/workspace/
```

> **Note:** `config.env` is already inside the Quantization folder you transferred in step 2.1. No separate transfer needed.

---

## PHASE 3 — SSH Into the Node

```bash
ssh root@<IP> -p <PORT>
```

---

## PHASE 4 — Import GPG Key (REQUIRED before pipeline runs)

```bash
gpg --import /workspace/release-private.key

# Verify it was imported
gpg --list-secret-keys
# Should show a line starting with "sec"
```

> `run_pipeline.sh` will fail fast if no GPG key is found — this check prevents wasting GPU time.

---

## PHASE 5 — Run Setup (Once Per Node)

```bash
cd /workspace/Quantization
chmod +x setup.sh
./setup.sh
```

This will:
- Install system packages: `build-essential cmake gpg libgomp1 curl git`
- Clone and build llama.cpp with CUDA support (`-DGGML_CUDA=ON`)
- Copy `llama-quantize` and `llama-convert-hf-to-gguf` to `/usr/local/bin/`
- Install Python packages from `requirements.txt`

**Expected time: ~10–15 min**

After it finishes you will see:
```
✓ Python packages OK
✓ llama-quantize OK
✓ llama-convert OK
✓ GPG OK
Setup complete. Run ./run_pipeline.sh to start.
```

---

## PHASE 6 — Verify Everything is Ready

```bash
# Check adapter is there
ls /workspace/adapter/
# Should show: adapter_model.safetensors, adapter_config.json, tokenizer.json ...

# Check config.env is filled in
cat /workspace/Quantization/config.env

# Check binaries are in PATH
llama-quantize --help > /dev/null && echo "OK"
llama-convert-hf-to-gguf --help > /dev/null && echo "OK"

# Check CUDA is visible
python3 -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
# Should print: True  and  NVIDIA A100 ...
```

---

## PHASE 7 — Run the Pipeline

```bash
cd /workspace/Quantization
chmod +x run_pipeline.sh
./run_pipeline.sh
```

The script validates all 12 required env vars, checks the adapter directory exists, and verifies the GPG key is imported — before spending any GPU time.

---

## PHASE 8 — What Happens During the Run

```
[Validation]
  ✓ 12 env vars present
  ✓ ADAPTER_PATH directory exists
  ✓ GPG secret key imported

[quantize.py]
  Step 1: Download Qwen2.5-14B-Instruct to /workspace/base_model/   (~30 GB, ~5 min)
  Step 2: Load base model in BF16 + load LoRA adapter                (~8–12 min on A100)
          merge_and_unload() — bakes adapter weights into base model
          Save merged BF16 to /workspace/gguf_output/merged_bf16/
  Step 3: Convert BF16 → GGUF FP16 (CI reference copy)              (~3–5 min)
          Output: model-fp16.gguf (~28 GB)
  Step 4: Quantize → Q5_K_M                                          (~3–4 min)
          Output: model-q5_k_m.gguf (~10.7 GB)
          SHA-256 computed, GPG .sig file created
  Step 5: Quantize → Q4_K_M                                          (~2–3 min)
          Output: model-q4_k_m.gguf (~8.0 GB)
          SHA-256 computed, GPG .sig file created
  Step 6: manifest.json written

[upload.py]
  For each artifact (Q5_K_M, Q4_K_M):
    - Local SHA-256 verified against manifest
    - GGUF + .sig uploaded to SeaweedFS
      Path: {domain}/v{version}/{filename}
      e.g.: broker/v1.2.0/model-q5_k_m.gguf
    - Downloaded back and re-hashed (streaming) to verify integrity
    - Presigned URL generated (24h)
  manifest.json uploaded to SeaweedFS
  Supabase adapter_registry rows inserted (one per artifact)
```

**Total expected time on A100 SXM4: ~25–35 min**

---

## PHASE 9 — Verify Upload Succeeded

```bash
# Check output files
ls -lh /workspace/gguf_output/
# Should show:
#   merged_bf16/              (directory)
#   model-fp16.gguf           (~28 GB)
#   model-q5_k_m.gguf         (~10.7 GB)
#   model-q5_k_m.gguf.sig
#   model-q4_k_m.gguf         (~8.0 GB)
#   model-q4_k_m.gguf.sig
#   manifest.json
```

Check Supabase — go to your project → Table Editor → `adapter_registry`:
- Two new rows should appear (one for q5_k_m, one for q4_k_m)
- `is_available = true`, `blocked = false`
- `blob_url` has the presigned SeaweedFS URL

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ERROR: <VAR> is not set in config.env` | Open `config.env` and fill in the missing variable |
| `ERROR: ADAPTER_PATH not found` | Check `ADAPTER_PATH` in config.env matches where adapter was transferred |
| `ERROR: No GPG secret key found` | Run `gpg --import /workspace/release-private.key` first |
| `CUDA not available` | Check CUDA 12.x image was selected. Run `nvidia-smi` to verify GPU |
| `merge_and_unload() OOM` | Need ≥80 GB VRAM — switch to A100 80GB or H100 |
| `llama-quantize not found` | setup.sh cmake build failed — re-run `./setup.sh` |
| `Local hash mismatch` | GGUF file was corrupted during quantization — re-run quantize.py |
| `Remote hash mismatch` | Upload was corrupted — script auto-deletes the remote file, re-run upload.py |
| `Supabase insert fails` | Check `SUPABASE_SERVICE_ROLE_KEY` — must be service role key, not anon key |
| `GPG signature missing` | sign_file() failed during quantize.py — check GPG key is imported and not expired |

---

## SeaweedFS Blob Structure After Successful Run

```
{SEAWEEDFS_BUCKET}/
  broker/
    v1.2.0/
      model-q5_k_m.gguf
      model-q5_k_m.gguf.sig
      model-q4_k_m.gguf
      model-q4_k_m.gguf.sig
      manifest.json
```

The Supabase `adapter_registry` table will have new rows with:
- `domain` — e.g. `broker`
- `adapter_version` — e.g. `1.2.0`
- `quant_level` — `q5_k_m` or `q4_k_m`
- `sha256` — `sha256:<hex>` (with prefix)
- `blob_url` — presigned SeaweedFS URL (24h) for Electron to download
- `min_electron_ver`, `canary_pct`, `rollback_safe` — rollout control fields
- `is_available = true`, `blocked = false`
