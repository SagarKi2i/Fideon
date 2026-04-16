# Local Pipeline Test Guide

Full end-to-end test: quantization → SeaweedFS (VM) → backend → Electron download.

## SeaweedFS VM — already running, no Docker needed

| Key | Value |
|-----|-------|
| Endpoint | `http://20.40.61.106:8333` |
| Access Key | `c3926443bcca0766aae1b7802327f820` |
| Secret Key | `8e90a92ccc55bd3d3f5b8e4ceb01020f854188d1568af6aaf008bc5b158c5ad6` |
| Bucket | `my-bucket` |

Services running on VM: Master :9333, Volume :8080, Filer :8888, S3 API :8333 ✅

## What you need before starting

| Requirement | Check |
|-------------|-------|
| WSL2 with Ubuntu | `wsl -l -v` in PowerShell |
| Python 3.10+ in WSL2 | `python3 --version` |
| Supabase project URL + service role key | Supabase dashboard → Settings → API |
| Ollama installed (for Electron install step) | `ollama --version` |

**Estimated time:** 30–40 minutes (most of it is model download + llama.cpp compile)

---

## Phase 1 — Install tools in WSL2 (once only, ~5 min)

Open WSL2 terminal:

```bash
cd /mnt/c/Users/samar/Downloads/neura-box-cloud-main

# Compiles llama.cpp (CPU-only) + installs Python packages
bash Quantization/setup_local.sh
```

---

## Phase 2 — Configure the pipeline (1 min)

```bash
cd /mnt/c/Users/samar/Downloads/neura-box-cloud-main/Quantization

cp config.env.local config.env

# Open and fill in ONLY your Supabase values (2 lines)
nano config.env
```

Edit these two lines — everything else is already filled in:
```
SUPABASE_URL=https://<your-project-id>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>
```

---

## Phase 3 — Verify SeaweedFS connectivity (1 min)

```bash
cd /mnt/c/Users/samar/Downloads/neura-box-cloud-main

python3 Quantization/init_seaweedfs.py
```

Expected output:
```
SeaweedFS endpoint : http://20.40.61.106:8333
Bucket             : my-bucket
✓ Bucket 'my-bucket' already exists — nothing to do
✓ Round-trip test passed — SeaweedFS is healthy
```

If you see `my-bucket already exists` — perfect, it's live and reachable.

---

## Phase 4 — Generate the test LoRA adapter (~5 min, CPU)

```bash
cd /mnt/c/Users/samar/Downloads/neura-box-cloud-main

python3 Quantization/create_test_adapter.py --output-dir /workspace/test_adapter
```

This will:
1. Download TinyLlama-1.1B from HuggingFace (~2.2 GB, free, no token needed)
2. Attach a LoRA adapter (r=8, targets q_proj + v_proj)
3. Run 1 training step on a synthetic insurance sentence
4. Save the adapter to `/workspace/test_adapter/`

Expected output:
```
[1/4] Loading tokenizer...
[2/4] Loading model (float32, CPU)...
[3/4] Attaching LoRA adapter...
trainable params: 2,097,152 || all params: 1,102,048,256 || trainable%: 0.19
[4/4] Running 1 training step...
      Training loss: 2.3471
✓ Adapter saved to: /workspace/test_adapter
```

---

## Phase 5 — Run the full quantization + upload pipeline (~15–25 min, CPU)

```bash
cd /mnt/c/Users/samar/Downloads/neura-box-cloud-main/Quantization

bash run_pipeline.sh
```

Pipeline steps:
1. Downloads TinyLlama base (cached after Phase 4)
2. Loads base model + merges the LoRA adapter
3. Converts merged model → GGUF FP16
4. Quantizes to Q5_K_M (~900 MB) and Q4_K_M (~670 MB)
5. GPG-signs both GGUF files
6. **Uploads both GGUF + .sig files to your SeaweedFS VM** (`my-bucket/broker/v0.1.0-test/`)
7. Streams back from SeaweedFS and verifies SHA-256 matches
8. Registers both artifacts in Supabase `adapter_registry`

Expected final output:
```
Uploading model-q5_k_m.gguf (900 MB)...
  ✓ Remote integrity verified
Uploading model-q4_k_m.gguf (670 MB)...
  ✓ Remote integrity verified
manifest.json uploaded
Upload & registry update complete.
```

### If GPG signing fails (first run only)

```bash
gpg --batch --gen-key <<EOF
Key-Type: RSA
Key-Length: 2048
Name-Real: Test Pipeline
Name-Email: test@local
Expire-Date: 0
%no-passphrase
%commit
EOF
```

Then re-run `run_pipeline.sh`.

---

## Phase 6 — Start the backend

Open a second WSL2 terminal:

```bash
cd /mnt/c/Users/samar/Downloads/neura-box-cloud-main/backend

export SEAWEEDFS_ENDPOINT=http://20.40.61.106:8333
export SEAWEEDFS_ACCESS_KEY=c3926443bcca0766aae1b7802327f820
export SEAWEEDFS_SECRET_KEY=8e90a92ccc55bd3d3f5b8e4ceb01020f854188d1568af6aaf008bc5b158c5ad6
export SEAWEEDFS_BUCKET=my-bucket

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Phase 7 — Test the backend API

In a third terminal, get a device JWT first:

```bash
# Register a device (requires your user JWT from Supabase Auth)
DEVICE_JWT=$(curl -s -X POST http://localhost:8000/api/v1/devices/register \
  -H "Authorization: Bearer <your-user-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"device_name":"test-device","device_type":"desktop"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['jwt'])")

echo "Device JWT: $DEVICE_JWT"
```

Run all 4 backend tests:

```bash
DEVICE_JWT="$DEVICE_JWT" bash Quantization/test_backend.sh
```

Expected output:
```
[TEST 1] GET /api/v1/adapter/latest          → available=true  ✓
[TEST 2] GET /api/v1/adapter/download-url    → presigned URL   ✓
[TEST 3] GET /api/v1/adapter/download-url?sig=true → .sig URL  ✓
[TEST 4] Download GGUF via presigned URL     → GGUF magic OK   ✓
Results: 4 passed / 0 failed
```

---

## Phase 8 — Test the full Electron download path

```bash
# Get presigned URL for Q4 model
GGUF_URL=$(curl -s \
  -H "Authorization: Bearer $DEVICE_JWT" \
  "http://localhost:8000/api/v1/adapter/download-url?domain=broker&version=v0.1.0-test&quant=q4_k_m" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['url'])")

# Download the full GGUF
curl -L -o /tmp/model-q4_k_m.gguf "$GGUF_URL"

# Verify GGUF magic header
python3 -c "
with open('/tmp/model-q4_k_m.gguf','rb') as f:
    magic = f.read(4)
print('Magic bytes:', magic)
assert magic == b'GGUF', 'Not a valid GGUF file!'
print('✓ Valid GGUF file confirmed')
"

# (Optional) Import into Ollama
cat > /tmp/Modelfile << 'EOF'
FROM /tmp/model-q4_k_m.gguf
EOF
ollama create broker-v0.1.0-test-q4_k_m -f /tmp/Modelfile
ollama list | grep broker
```

---

## Summary — What each phase proves

| Phase | What it proves |
|-------|---------------|
| 3 | SeaweedFS VM is reachable and `my-bucket` exists |
| 4 | TinyLlama download + PEFT LoRA adapter creation works |
| 5 quantize.py | Adapter merge + GGUF conversion + quantization + GPG signing works |
| 5 upload.py | Upload to VM SeaweedFS + SHA-256 integrity + Supabase registration works |
| 6–7 | Backend reads from Supabase, generates presigned URLs into VM SeaweedFS |
| 8 | Full Electron download path: presigned URL → GGUF → verify → Ollama import |

---

## Troubleshooting

**`Connection refused` to `http://20.40.61.106:8333`**
- Check your VM is on and the SeaweedFS S3 service is running on port 8333.
- From WSL2: `curl -s http://20.40.61.106:8333/ | head` should return an XML response.

**`llama-quantize: command not found`**
```bash
bash Quantization/setup_local.sh
```

**`No available artifact`** from `/api/v1/adapter/latest`
- Check Supabase `adapter_registry` table has rows with `is_available=true` and `blocked=false`.
- Verify `domain=broker` matches what `upload.py` registered.
- Confirm `CANARY_PCT=100` is set in config.env.

**Quantization is slow on CPU**
- TinyLlama Q4_K_M takes ~8–15 min on CPU — expected.
- On a production GPU node, this takes ~90 seconds.
