#!/bin/bash
# start.sh — start the Fideon PDF upload server on the RunPod pod.
# Place this file at /workspace/ai-ml/start.sh on the pod.
# Called automatically by Dockerfile CMD, or manually via SSH.

set -e

UPLOAD_DIR=${UPLOAD_DIR:-/workspace/uploads}
PORT=${UPLOAD_SERVER_PORT:-8080}

mkdir -p "$UPLOAD_DIR"
echo "[start.sh] Upload dir: $UPLOAD_DIR"
echo "[start.sh] Starting Fideon RunPod Upload Server on port $PORT"

cd /workspace/ai-ml

exec python -m uvicorn server:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --log-level info
