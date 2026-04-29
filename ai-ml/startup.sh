#!/bin/bash
set -e

LOG="/workspace/logs/startup.log"
mkdir -p /workspace/logs

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"; }

log "Starting Fideon AI-ML Server..."

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

# ── Start FastAPI ──────────────────────────────────────────────────────────────
log "Starting FastAPI..."
cd /app
uvicorn server:app --host 0.0.0.0 --port 8000 >> "$LOG" 2>&1 &

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
