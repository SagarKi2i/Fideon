#!/bin/bash
# start.sh — start the Fideon PDF upload server on the RunPod pod.
# Place this file at /workspace/ai-ml/start.sh on the pod.
# Called automatically by Dockerfile CMD, or manually via SSH.

set -e

UPLOAD_DIR=${UPLOAD_DIR:-/workspace/uploads}
PORT=${UPLOAD_SERVER_PORT:-8000}

# /workspace/bin persists across pod restarts — add it to PATH so
# llama-quantize and llama-convert-hf-to-gguf are always discoverable.
export PATH="/workspace/bin:$PATH"
export SEAWEEDFS_BUCKET="${SEAWEEDFS_BUCKET:-my-bucket}"
export ACORD_NL_SUMMARY_ENABLED="${ACORD_NL_SUMMARY_ENABLED:-true}"

# Storage backend — Azure Blob (set STORAGE_BACKEND=seaweedfs to revert)
export STORAGE_BACKEND="${STORAGE_BACKEND:-azure}"
export AZURE_BLOB_ACCOUNT_URL="${AZURE_BLOB_ACCOUNT_URL:-https://swtier.blob.core.windows.net}"
export AZURE_BLOB_SAS_TOKEN="${AZURE_BLOB_SAS_TOKEN:-sv=2025-11-05&ss=bfqt&srt=sco&sp=rwdlacupiytfx&se=2026-06-04T12:54:05Z&st=2026-05-04T04:39:05Z&spr=https&sig=ZVUsGfphbkOQwoyrmx7dv0mb1UR7LeV6N7bMFF97g%2Bo%3D}"
export AZURE_BLOB_CONTAINER="${AZURE_BLOB_CONTAINER:-models}"

if ! command -v llama-quantize &>/dev/null; then
  echo "[start.sh] WARNING: llama-quantize not found in /workspace/bin."
  echo "[start.sh] Run: bash /workspace/ai-ml/setup.sh --skip-pip"
fi

mkdir -p "$UPLOAD_DIR"
echo "[start.sh] Upload dir: $UPLOAD_DIR"
echo "[start.sh] Starting Fideon RunPod Upload Server on port $PORT"

cd /workspace/ai-ml

exec python -m uvicorn server:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --log-level info
