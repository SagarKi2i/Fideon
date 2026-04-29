#!/bin/bash
set -e

LOG="/workspace/logs/startup.log"
mkdir -p /workspace/logs

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"; }

log "Starting Fideon AI-ML Server..."

# ── Persist Surya/Datalab model cache to /workspace ───────────────────────────
mkdir -p /workspace/.cache/datalab
export DATALAB_CACHE_PATH=/workspace/.cache/datalab

# ── Python venv: create once on volume, reuse forever ─────────────────────────
if [ ! -f "/workspace/venv/bin/activate" ]; then
    log "First boot: creating venv and installing packages to /workspace/venv..."
    python3 -m venv /workspace/venv
    /workspace/venv/bin/pip install --upgrade pip
    /workspace/venv/bin/pip install -r /app/requirements.txt
    log "Packages installed to /workspace/venv"
else
    log "venv already exists at /workspace/venv — skipping install"
fi

source /workspace/venv/bin/activate

# ── llama.cpp: compile once on GPU pod, reuse forever from /workspace ─────────
LLAMA_BIN="/workspace/llama.cpp/build/bin/llama-quantize"

if [ ! -f "$LLAMA_BIN" ]; then
    log "First boot: compiling llama.cpp with CUDA (~10-15 min on RunPod GPU)..."
    bash /app/setup.sh --skip-pip --skip-verify
    log "llama.cpp compiled and stored in /workspace/llama.cpp"
else
    log "llama.cpp already compiled — linking binaries..."
    cp "$LLAMA_BIN" /usr/local/bin/llama-quantize
    cat > /usr/local/bin/llama-convert-hf-to-gguf <<'WRAPPER'
#!/usr/bin/env bash
exec python3 /workspace/llama.cpp/convert_hf_to_gguf.py "$@"
WRAPPER
    chmod +x /usr/local/bin/llama-convert-hf-to-gguf
fi

# ── Start FastAPI using venv ───────────────────────────────────────────────────
log "Starting FastAPI..."
cd /app
/workspace/venv/bin/uvicorn server:app --host 0.0.0.0 --port 8000 >> "$LOG" 2>&1 &

sleep 5

# ── Start Cloudflare tunnel ────────────────────────────────────────────────────
if [ -z "${CLOUDFLARE_TUNNEL_TOKEN}" ]; then
    log "CLOUDFLARE_TUNNEL_TOKEN not set -- tunnel skipped"
else
    log "Starting Cloudflare tunnel..."
    cloudflared tunnel run \
        --token "${CLOUDFLARE_TUNNEL_TOKEN}" \
        --no-autoupdate >> "$LOG" 2>&1 &
    sleep 3
    log "Live: https://gpu-api.fideonai.fyi"
fi

log "========================================"
log "Server:  http://localhost:8000"
log "Public:  https://gpu-api.fideonai.fyi"
log "Logs:    /workspace/logs/startup.log"
log "========================================"

wait
