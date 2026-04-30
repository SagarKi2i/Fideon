#!/bin/bash

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
    if "$VENV/bin/pip" install -r /app/requirements.txt --quiet; then
        log "Packages installed to venv"
    else
        log_err "pip install failed — some packages may be missing"
    fi
else
    log "venv exists — checking for missing packages..."
    "$VENV/bin/pip" install -q --no-deps -r /app/requirements.txt 2>/dev/null || \
    "$VENV/bin/pip" install -q -r /app/requirements.txt 2>/dev/null || \
    log_err "pip sync failed — continuing with existing packages"
fi

source "$VENV/bin/activate"

# ── llama.cpp: compile once on GPU pod, reuse forever ─────────────────────────
LLAMA_BIN="/workspace/llama.cpp/build/bin/llama-quantize"
if [ ! -f "$LLAMA_BIN" ]; then
    log "First boot: compiling llama.cpp with CUDA (~10-15 min)..."
    if bash /app/setup.sh --skip-pip --skip-verify; then
        [ -f /workspace/llama.cpp/requirements.txt ] && \
            "$VENV/bin/pip" install -q -r /workspace/llama.cpp/requirements.txt 2>/dev/null || true
        "$VENV/bin/pip" install -q gguf 2>/dev/null || true
        log "llama.cpp compiled and cached"
    else
        log_err "llama.cpp compile failed — quantization will be unavailable"
    fi
else
    log "llama.cpp already compiled — linking binaries..."
    cp "$LLAMA_BIN" /usr/local/bin/llama-quantize
    "$VENV/bin/pip" install -q gguf 2>/dev/null || true
    cat > /usr/local/bin/llama-convert-hf-to-gguf <<'WRAPPER'
#!/usr/bin/env bash
exec python3 /workspace/llama.cpp/convert_hf_to_gguf.py "$@"
WRAPPER
    chmod +x /usr/local/bin/llama-convert-hf-to-gguf
fi

# ── Start FastAPI ──────────────────────────────────────────────────────────────
log "Starting FastAPI on port 8000..."
cd /app
"$VENV/bin/uvicorn" server:app --host 0.0.0.0 --port 8000 >> "$LOG" 2>&1 &
UVICORN_PID=$!

log "Waiting for FastAPI (up to 30s)..."
READY=0
for i in $(seq 1 30); do
    if ! kill -0 $UVICORN_PID 2>/dev/null; then
        log_err "FastAPI process died — check logs above"
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
    log "filebrowser not found — skipping port 8080"
fi

# ── Start ComfyUI (port 8188) ─────────────────────────────────────────────────
if [ -d /workspace/ComfyUI ]; then
    log "Starting ComfyUI on port 8188..."
    "$VENV/bin/python" /workspace/ComfyUI/main.py \
        --listen 0.0.0.0 \
        --port 8188 >> "$LOG" 2>&1 &
    log "ComfyUI started"
else
    log "ComfyUI not found at /workspace/ComfyUI — skipping port 8188"
fi

# ── Start JupyterLab (port 8888) ──────────────────────────────────────────────
JUPYTER_BIN="$VENV/bin/jupyter"
if [ -f "$JUPYTER_BIN" ]; then
    log "Starting JupyterLab on port 8888..."
    "$JUPYTER_BIN" lab \
        --ip=0.0.0.0 \
        --port=8888 \
        --no-browser \
        --allow-root \
        --ServerApp.token='' \
        --ServerApp.password='' \
        --ServerApp.root_dir=/workspace >> "$LOG" 2>&1 &
    log "JupyterLab started"
else
    log "jupyter not found in venv — skipping port 8888"
fi

# ── Start Cloudflare tunnel ────────────────────────────────────────────────────
if [ -z "${CLOUDFLARE_TUNNEL_TOKEN}" ]; then
    log_err "CLOUDFLARE_TUNNEL_TOKEN not set — tunnel skipped (set it in RunPod pod env vars)"
else
    log "Starting Cloudflare tunnel..."
    cloudflared tunnel run \
        --token "${CLOUDFLARE_TUNNEL_TOKEN}" >> "$LOG" 2>&1 &
    TUNNEL_PID=$!
    sleep 5
    if kill -0 $TUNNEL_PID 2>/dev/null; then
        log "Cloudflare tunnel running — Live: https://gpu-api.fideonai.fyi"
    else
        log_err "Cloudflare tunnel crashed — check token and cloudflared logs"
    fi
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
