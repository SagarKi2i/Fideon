#!/bin/bash
set -e

LOG="/workspace/logs/startup.log"
mkdir -p /workspace/logs

log()     { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"        | tee -a "$LOG"; }
log_err() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" | tee -a "$LOG" >&2; }

log "Starting Fideon AI-ML Server..."

# ── Persist Surya/Datalab model cache ─────────────────────────────────────────
mkdir -p /workspace/.cache/datalab
export DATALAB_CACHE_PATH=/workspace/.cache/datalab

# ── Python venv: create once on volume, reuse forever ─────────────────────────
VENV=/workspace/venv
if [ ! -f "$VENV/bin/activate" ]; then
    log "First boot: creating venv at $VENV (~5-10 min)..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --upgrade pip --quiet
    "$VENV/bin/pip" install -r /app/requirements.txt --quiet
    log "Packages installed to venv"
else
    log "venv exists — checking for missing packages..."
    "$VENV/bin/pip" install -q --no-deps -r /app/requirements.txt 2>/dev/null || \
    "$VENV/bin/pip" install -q -r /app/requirements.txt
fi

source "$VENV/bin/activate"

# ── llama.cpp: compile once on GPU pod, reuse forever ─────────────────────────
LLAMA_BIN="/workspace/llama.cpp/build/bin/llama-quantize"
if [ ! -f "$LLAMA_BIN" ]; then
    log "First boot: compiling llama.cpp with CUDA (~10-15 min)..."
    bash /app/setup.sh --skip-pip --skip-verify
    # Install llama.cpp Python deps into venv (not system pip)
    [ -f /workspace/llama.cpp/requirements.txt ] && \
        "$VENV/bin/pip" install -q -r /workspace/llama.cpp/requirements.txt
    "$VENV/bin/pip" install -q gguf
    log "llama.cpp compiled and cached"
else
    log "llama.cpp already compiled — linking binaries..."
    cp "$LLAMA_BIN" /usr/local/bin/llama-quantize
    # Ensure gguf is in venv
    "$VENV/bin/pip" install -q gguf 2>/dev/null || true
    cat > /usr/local/bin/llama-convert-hf-to-gguf <<'WRAPPER'
#!/usr/bin/env bash
exec python3 /workspace/llama.cpp/convert_hf_to_gguf.py "$@"
WRAPPER
    chmod +x /usr/local/bin/llama-convert-hf-to-gguf
fi

# ── Start FastAPI ──────────────────────────────────────────────────────────────
log "Starting FastAPI..."
cd /app
"$VENV/bin/uvicorn" server:app --host 0.0.0.0 --port 8000 >> "$LOG" 2>&1 &
UVICORN_PID=$!

# Wait up to 30s for FastAPI to be ready
log "Waiting for FastAPI..."
READY=0
for i in $(seq 1 30); do
    if ! kill -0 $UVICORN_PID 2>/dev/null; then
        log_err "FastAPI crashed — check logs above"
        break
    fi
    if curl -sf http://localhost:8000/ > /dev/null 2>&1 || \
       curl -sf http://localhost:8000/health > /dev/null 2>&1 || \
       curl -sf http://localhost:8000/docs > /dev/null 2>&1; then
        READY=1
        log "FastAPI is ready"
        break
    fi
    sleep 1
done

if [ $READY -eq 0 ] && kill -0 $UVICORN_PID 2>/dev/null; then
    log "FastAPI still starting — proceeding anyway"
fi

# ── Start FileBrowser (port 8080) ─────────────────────────────────────────────
if command -v filebrowser &>/dev/null; then
    log "Starting FileBrowser on port 8080..."
    mkdir -p /workspace/.filebrowser
    filebrowser \
        --address 0.0.0.0 \
        --port 8080 \
        --root /workspace \
        --noauth \
        --database /workspace/.filebrowser/filebrowser.db >> "$LOG" 2>&1 &
    log "FileBrowser started"
else
    log "filebrowser not found — skipping"
fi

# ── Start ComfyUI (port 8188) ─────────────────────────────────────────────────
if [ -d /workspace/ComfyUI ]; then
    log "Starting ComfyUI on port 8188..."
    "$VENV/bin/python" /workspace/ComfyUI/main.py \
        --listen 0.0.0.0 \
        --port 8188 >> "$LOG" 2>&1 &
    log "ComfyUI started"
else
    log "ComfyUI not found at /workspace/ComfyUI — skipping"
fi

# ── Start JupyterLab ──────────────────────────────────────────────────────────
if command -v jupyter &>/dev/null; then
    log "Starting JupyterLab on port 8888..."
    jupyter lab \
        --ip=0.0.0.0 \
        --port=8888 \
        --no-browser \
        --allow-root \
        --ServerApp.token='' \
        --ServerApp.password='' \
        --ServerApp.root_dir=/workspace >> "$LOG" 2>&1 &
    log "JupyterLab started"
else
    log "jupyter not found — skipping JupyterLab"
fi

# ── Start Cloudflare tunnel ────────────────────────────────────────────────────
if [ -z "${CLOUDFLARE_TUNNEL_TOKEN}" ]; then
    log "CLOUDFLARE_TUNNEL_TOKEN not set — tunnel skipped"
else
    log "Starting Cloudflare tunnel..."
    cloudflared tunnel run \
        --token "${CLOUDFLARE_TUNNEL_TOKEN}" >> "$LOG" 2>&1 &
    sleep 3
    log "Live: https://gpu-api.fideonai.fyi"
fi

log "========================================"
log "FastAPI:      http://localhost:8000"
log "FileBrowser:  http://localhost:8080"
log "ComfyUI:      http://localhost:8188"
log "JupyterLab:   http://localhost:8888"
log "Public:       https://gpu-api.fideonai.fyi"
log "Logs:         /workspace/logs/startup.log"
log "========================================"

wait
