#!/bin/bash

LOG="/workspace/logs/startup.log"
mkdir -p /workspace/logs

log()     { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"        | tee -a "$LOG"; }
log_err() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" | tee -a "$LOG" >&2; }

log "Starting Fideon AI-ML Server..."

# ── Persist Surya/Datalab model cache ─────────────────────────────────────────
mkdir -p /workspace/.cache/datalab
export DATALAB_CACHE_PATH=/workspace/.cache/datalab

# ── Python: use system Python (Docker pre-baked) or workspace venv ────────────
# Redirect pip tmp dir to /workspace so large extractions don't fill container disk
mkdir -p /workspace/tmp
export TMPDIR=/workspace/tmp

VENV=/workspace/venv
PY="$VENV/bin/python"
UVICORN_BIN="$VENV/bin/uvicorn"

if python3 -c "import torch, uvicorn, surya, transformers" 2>/dev/null; then
    # Fast path: packages baked into the Docker image — no pip install needed
    log "Docker pre-installed packages detected — using system Python"
    PY="python3"
    UVICORN_BIN="$(command -v uvicorn)"
elif [ ! -f "$VENV/bin/activate" ]; then
    log "First boot: creating venv at $VENV (~10 min)..."
    python3 -m venv "$VENV"
    "$PY" -m ensurepip --upgrade 2>>"$LOG" || \
        curl -sS https://bootstrap.pypa.io/get-pip.py | "$PY" 2>>"$LOG"
    "$PY" -m pip install --upgrade pip --quiet --no-cache-dir 2>>"$LOG"
    if "$PY" -m pip install -r /app/requirements.txt --quiet --no-cache-dir \
            --extra-index-url https://download.pytorch.org/whl/cu128 2>>"$LOG"; then
        log "Packages installed to venv"
    else
        log_err "pip install failed — some packages may be missing (check $LOG)"
    fi
    source "$VENV/bin/activate"
else
    log "venv exists — syncing packages..."
    "$PY" -m ensurepip --upgrade 2>>"$LOG" || true
    if ! "$PY" -m pip install -q --no-cache-dir -r /app/requirements.txt \
            --extra-index-url https://download.pytorch.org/whl/cu128 2>>"$LOG"; then
        log_err "pip sync failed — continuing with existing packages (check $LOG)"
    fi
    source "$VENV/bin/activate"
fi

# ── Qwen model check ──────────────────────────────────────────────────────────
QWEN_PATH="${QWEN_MODEL_ID:-/workspace/models/qwen2-vl-7b}"
if [ ! -d "$QWEN_PATH" ]; then
    log_err "Qwen model not found at $QWEN_PATH"
    log_err "Download it with: hf download Qwen/Qwen2-VL-7B --local-dir $QWEN_PATH --token <HF_TOKEN>"
else
    log "Qwen model found at $QWEN_PATH"
fi

# ── llama.cpp: compile once on GPU pod, reuse forever ─────────────────────────
LLAMA_BIN="/workspace/llama.cpp/build/bin/llama-quantize"
if [ ! -f "$LLAMA_BIN" ]; then
    log "First boot: compiling llama.cpp with CUDA (~40 min)..."
    bash /app/setup.sh --skip-pip --skip-verify 2>>"$LOG" || true
    if [ -f "$LLAMA_BIN" ]; then
        cp "$LLAMA_BIN" /usr/local/bin/llama-quantize 2>>"$LOG" || true
        [ -f /workspace/llama.cpp/requirements.txt ] && \
            "$PY" -m pip install -q -r /workspace/llama.cpp/requirements.txt 2>>"$LOG" || true
        "$PY" -m pip install -q gguf 2>>"$LOG" || true
        log "llama.cpp compiled and cached"
    else
        log_err "llama.cpp compile failed — quantization will be unavailable"
    fi
else
    log "llama.cpp already compiled — linking binaries..."
    cp "$LLAMA_BIN" /usr/local/bin/llama-quantize 2>>"$LOG" || true
    "$PY" -m pip install -q gguf 2>>"$LOG" || true
    cat > /usr/local/bin/llama-convert-hf-to-gguf <<'WRAPPER'
#!/usr/bin/env bash
exec python3 /workspace/llama.cpp/convert_hf_to_gguf.py "$@"
WRAPPER
    chmod +x /usr/local/bin/llama-convert-hf-to-gguf
fi

# ── Ollama: install → serve → load GGUF from Azure Blob ───────────────────────
# Activated only when USE_OLLAMA=true is set in the pod environment vars.
# Sequence: install binary → start service → wait ready → python model_loader.py
if [ "${USE_OLLAMA:-false}" = "true" ]; then

    # 0. Log GPU visibility — Ollama's install script auto-detects NVIDIA drivers;
    #    this confirms the GPU is visible to the container before we proceed.
    if command -v nvidia-smi &>/dev/null; then
        log "NVIDIA GPU detected:"
        nvidia-smi --query-gpu=name,memory.total,driver_version \
            --format=csv,noheader 2>/dev/null | while IFS= read -r line; do
            log "  GPU: $line"
        done
    else
        log_err "nvidia-smi not found — Ollama may run on CPU only (check RunPod GPU allocation)"
    fi

    # 1. Install Ollama binary if not present
    #    The official install script detects NVIDIA drivers and installs the CUDA-enabled binary.
    if ! command -v ollama &>/dev/null; then
        log "Ollama not found — installing (CUDA-enabled build)..."
        curl -fsSL https://ollama.com/install.sh | sh >> "$LOG" 2>&1
        if command -v ollama &>/dev/null; then
            log "Ollama installed: $(ollama --version 2>/dev/null)"
        else
            log_err "Ollama installation failed — Ollama features unavailable"
        fi
    else
        log "Ollama already installed: $(ollama --version 2>/dev/null)"
    fi

    # 2. Start ollama serve in background (models persisted in /workspace)
    if command -v ollama &>/dev/null; then
        mkdir -p /workspace/.ollama
        export OLLAMA_MODELS=/workspace/.ollama

        if pgrep -x ollama &>/dev/null; then
            log "Ollama service already running"
        else
            log "Starting Ollama service (models: /workspace/.ollama, host: 0.0.0.0:11434)..."
            # OLLAMA_HOST   — scoped to this process only; Python clients need http:// and must
            #                 not inherit the bare host:port format the daemon expects.
            # OLLAMA_NUM_GPU=999 — load ALL transformer layers onto GPU; Ollama caps this at the
            #                 real layer count automatically. Without this, Ollama's conservative
            #                 VRAM estimate can silently offload some layers to CPU.
            OLLAMA_HOST=0.0.0.0:11434 OLLAMA_NUM_GPU=999 ollama serve >> "$LOG" 2>&1 &
            OLLAMA_PID=$!
            log "Ollama PID: $OLLAMA_PID"

            # Wait up to 30 s for the Ollama HTTP API to respond
            OLLAMA_READY=0
            for i in $(seq 1 30); do
                if curl -sf http://localhost:11434/api/tags -o /dev/null 2>/dev/null; then
                    OLLAMA_READY=1
                    log "Ollama API ready (${i}s)"
                    break
                fi
                sleep 1
            done
            if [ $OLLAMA_READY -eq 0 ]; then
                log_err "Ollama API did not respond within 30s — model_loader.py may fail"
            else
                # Confirm Ollama is running on GPU (appears in /api/tags response or ps output)
                GPU_PROCS=$(nvidia-smi --query-compute-apps=pid,used_memory \
                    --format=csv,noheader 2>/dev/null | grep -c "$OLLAMA_PID" || true)
                if [ "$GPU_PROCS" -gt 0 ] 2>/dev/null; then
                    log "Ollama confirmed on GPU (PID $OLLAMA_PID has GPU memory allocation)"
                else
                    log "Ollama API ready — GPU allocation will appear after first model load"
                fi
            fi
        fi

        # 3. Download latest GGUF from Azure Blob and register with Ollama
        if [ -n "${AZURE_BLOB_ACCOUNT_URL}" ] && [ -n "${AZURE_BLOB_SAS_TOKEN}" ]; then
            log "Running model_loader.py — downloading GGUF from Azure Blob into Ollama..."
            "$PY" /app/model_loader.py --skip-if-loaded >> "$LOG" 2>&1
            if [ $? -eq 0 ]; then
                log "GGUF model loaded into Ollama successfully"
            else
                log_err "model_loader.py failed — check Azure Blob credentials in pod env vars"
                log_err "USE_OLLAMA=true but no model loaded — extraction requests will fail until resolved"
                log_err "To use transformers instead, set USE_OLLAMA=false and restart the pod"
            fi
        else
            log_err "AZURE_BLOB_ACCOUNT_URL or AZURE_BLOB_SAS_TOKEN not set"
            log_err "Set these env vars in RunPod pod config to enable Ollama GGUF inference"
        fi
    fi

else
    log "USE_OLLAMA=false — skipping Ollama (using transformers/Qwen2-VL directly)"
fi

# ── Start FastAPI ──────────────────────────────────────────────────────────────
_start_fastapi() {
    cd /app
    "$UVICORN_BIN" server:app \
        --host 0.0.0.0 \
        --port 8000 \
        --timeout-keep-alive 600 \
        --h11-max-incomplete-event-size 524288 >> "$LOG" 2>&1 &
    echo $!
}

log "Starting FastAPI on port 8000..."
UVICORN_PID=$(_start_fastapi)

log "Waiting for FastAPI (up to 60s)..."
READY=0
for i in $(seq 1 60); do
    if ! kill -0 $UVICORN_PID 2>/dev/null; then
        log_err "FastAPI process died on attempt $i — last 20 log lines:"
        tail -20 "$LOG" | while IFS= read -r line; do log_err "  $line"; done
        break
    fi
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ 2>/dev/null)
    if [ "$HTTP_CODE" != "000" ] && [ -n "$HTTP_CODE" ]; then
        READY=1
        log "FastAPI is ready (HTTP $HTTP_CODE)"
        break
    fi
    sleep 1
done

if [ $READY -eq 0 ] && kill -0 $UVICORN_PID 2>/dev/null; then
    log "Warning: FastAPI health check timed out after 60s — proceeding anyway"
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
    "$PY" /workspace/ComfyUI/main.py \
        --listen 0.0.0.0 \
        --port 8188 >> "$LOG" 2>&1 &
    log "ComfyUI started"
else
    log "ComfyUI not found at /workspace/ComfyUI — skipping port 8188"
fi

# ── Start JupyterLab (port 8888) ──────────────────────────────────────────────
JUPYTER_BIN="$VENV/bin/jupyter"
[ "$PY" = "python3" ] && JUPYTER_BIN="$(command -v jupyter 2>/dev/null || echo '')"
if [ -n "$JUPYTER_BIN" ] && [ -f "$JUPYTER_BIN" ]; then
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
    log "jupyter not found — skipping port 8888"
fi

# ── Start Cloudflare tunnel ────────────────────────────────────────────────────
if [ -z "${CLOUDFLARE_TUNNEL_TOKEN}" ]; then
    log_err "CLOUDFLARE_TUNNEL_TOKEN not set — tunnel skipped (set it in RunPod pod env vars)"
else
    log "Starting Cloudflare tunnel..."
    cloudflared tunnel --no-autoupdate \
        --proxy-connection-timeout 600s \
        --proxy-expect-continue-timeout 600s \
        run --token "${CLOUDFLARE_TUNNEL_TOKEN}" 2>&1 | tee -a "$LOG" &
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

# ── Keep container alive, auto-restart FastAPI on crash ───────────────────────
MAX_RESTARTS=5
RESTART_COUNT=0
STABLE_CYCLES=0
STABLE_THRESHOLD=10
while true; do
    sleep 30
    if ! kill -0 $UVICORN_PID 2>/dev/null; then
        STABLE_CYCLES=0
        RESTART_COUNT=$((RESTART_COUNT + 1))
        if [ $RESTART_COUNT -gt $MAX_RESTARTS ]; then
            log_err "FastAPI has crashed $RESTART_COUNT times — giving up, exiting container"
            log_err "Check the Python traceback above in $LOG"
            exit 1
        fi
        log_err "FastAPI died (attempt $RESTART_COUNT/$MAX_RESTARTS) — restarting in 5s..."
        sleep 5
        UVICORN_PID=$(_start_fastapi)
        log "FastAPI restarted (PID $UVICORN_PID)"
    else
        STABLE_CYCLES=$((STABLE_CYCLES + 1))
        if [ $STABLE_CYCLES -ge $STABLE_THRESHOLD ] && [ $RESTART_COUNT -gt 0 ]; then
            log "FastAPI stable for $((STABLE_CYCLES * 30))s — resetting crash counter"
            RESTART_COUNT=0
            STABLE_CYCLES=0
        fi
    fi
done
