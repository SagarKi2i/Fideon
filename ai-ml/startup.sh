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
    if "$VENV/bin/pip" install -r /app/requirements.txt --quiet 2>>"$LOG"; then
        log "Packages installed to venv"
    else
        log_err "pip install failed — check $LOG for details"
    fi
else
    log "venv exists — checking for missing packages..."
    if ! "$VENV/bin/pip" install -q -r /app/requirements.txt 2>>"$LOG"; then
        log_err "pip sync failed — continuing with existing packages (check $LOG)"
    fi
fi

source "$VENV/bin/activate"

# ── llama.cpp: compile once on GPU pod, reuse forever ─────────────────────────
LLAMA_BIN="/workspace/llama.cpp/build/bin/llama-quantize"
if [ ! -f "$LLAMA_BIN" ]; then
    log "First boot: compiling llama.cpp with CUDA (~10-15 min)..."
    if bash /app/setup.sh --skip-pip --skip-verify; then
        [ -f /workspace/llama.cpp/requirements.txt ] && \
            "$VENV/bin/pip" install -q -r /workspace/llama.cpp/requirements.txt 2>>"$LOG" || true
        "$VENV/bin/pip" install -q gguf 2>>"$LOG" || true
        log "llama.cpp compiled and cached"
    else
        log_err "llama.cpp compile failed — quantization will be unavailable"
    fi
else
    log "llama.cpp already compiled — linking binaries..."
    cp "$LLAMA_BIN" /usr/local/bin/llama-quantize
    "$VENV/bin/pip" install -q gguf 2>>"$LOG" || true
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

log "Waiting for FastAPI (up to 60s)..."
READY=0
for i in $(seq 1 60); do
    if ! kill -0 $UVICORN_PID 2>/dev/null; then
        log_err "FastAPI process died on attempt $i — check $LOG for the Python traceback"
        break
    fi
    # Accept any HTTP response (even 404) — connection refused returns code 000
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ 2>/dev/null)
    if [ "$HTTP_CODE" != "000" ] && [ -n "$HTTP_CODE" ]; then
        READY=1
        log "FastAPI is ready (HTTP $HTTP_CODE)"
        break
    fi
    sleep 1
done

if [ $READY -eq 0 ] && kill -0 $UVICORN_PID 2>/dev/null; then
    log "Warning: FastAPI health check timed out after 60s — proceeding anyway (server may still be loading)"
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
    # --no-autoupdate prevents cloudflared from trying to self-update inside the container
    # tee -a makes tunnel output visible in RunPod container logs AND the log file
    cloudflared tunnel --no-autoupdate run \
        --token "${CLOUDFLARE_TUNNEL_TOKEN}" 2>&1 | tee -a "$LOG" &
    TUNNEL_PID=$!
    sleep 10
    if kill -0 $TUNNEL_PID 2>/dev/null; then
        log "Cloudflare tunnel running — Live: https://gpu-api.fideonai.fyi"
    else
        log_err "Cloudflare tunnel process exited — check above log lines for the reason"
        log_err "Common causes: invalid token, token already in use, network issue"
        log_err "Verify token at: https://one.dash.cloudflare.com -> Zero Trust -> Tunnels"
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

# ── Keep container alive, restart if FastAPI dies ─────────────────────────────
while true; do
    if ! kill -0 $UVICORN_PID 2>/dev/null; then
        log_err "FastAPI (uvicorn) has exited unexpectedly — container will exit and restart"
        exit 1
    fi
    sleep 30
done
