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

# Env var defaults — set here so uvicorn workers inherit them without needing
# RunPod environment variables explicitly configured.
export SEAWEEDFS_BUCKET="${SEAWEEDFS_BUCKET:-my-bucket}"
export ACORD_NL_SUMMARY_ENABLED="${ACORD_NL_SUMMARY_ENABLED:-true}"
log "SEAWEEDFS_BUCKET=${SEAWEEDFS_BUCKET}  ACORD_NL_SUMMARY_ENABLED=${ACORD_NL_SUMMARY_ENABLED}"

# Storage backend — Azure Blob Storage (set STORAGE_BACKEND=seaweedfs to revert to legacy)
export STORAGE_BACKEND="${STORAGE_BACKEND:-azure}"
export AZURE_BLOB_ACCOUNT_URL="${AZURE_BLOB_ACCOUNT_URL:-https://swtier.blob.core.windows.net}"
export AZURE_BLOB_SAS_TOKEN="${AZURE_BLOB_SAS_TOKEN:-sv=2025-11-05&ss=bfqt&srt=sco&sp=rwdlacupiytfx&se=2026-06-04T12:54:05Z&st=2026-05-04T04:39:05Z&spr=https&sig=ZVUsGfphbkOQwoyrmx7dv0mb1UR7LeV6N7bMFF97g%2Bo%3D}"
export AZURE_BLOB_CONTAINER="${AZURE_BLOB_CONTAINER:-models}"
log "STORAGE_BACKEND=${STORAGE_BACKEND}  AZURE_BLOB_CONTAINER=${AZURE_BLOB_CONTAINER}  AZURE_BLOB_ACCOUNT_URL=${AZURE_BLOB_ACCOUNT_URL}"

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
