#!/bin/bash
set -e

LOG="/workspace/logs/startup.log"
mkdir -p /workspace/logs

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"; }

log "Starting Fideon AI-ML Server..."

# /workspace/bin persists across pod restarts (system volume resets, /workspace does not).
# This ensures llama-quantize and llama-convert-hf-to-gguf are always in PATH.
export PATH="/workspace/bin:$PATH"
log "PATH includes /workspace/bin (llama.cpp binaries)"

# Warn if quantization tools are missing — operator needs to re-run setup.sh
if ! command -v llama-quantize &>/dev/null; then
  log "WARNING: llama-quantize not found. Run: bash /workspace/ai-ml/setup.sh --skip-pip"
fi

# Start FastAPI
log "Starting FastAPI..."
cd /workspace/ai-ml
uvicorn server:app --host 0.0.0.0 --port 8000 >> "$LOG" 2>&1 &

sleep 5

# Start Cloudflare tunnel
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
