#!/usr/bin/env bash
# =============================================================================
# Fideon RunPod — one-shot setup script
# Run once after pod starts:
#
#   bash /workspace/ai-ml/setup.sh
# =============================================================================
set -euo pipefail

LLAMA_DIR="/workspace/llama.cpp"
LLAMA_BIN="$LLAMA_DIR/build/bin/llama-quantize"
LLAMA_CONVERT="$LLAMA_DIR/convert_hf_to_gguf.py"

echo "================================================================"
echo " Fideon RunPod Setup"
echo "================================================================"

# ── 1. Persist Surya/Datalab model cache to /workspace ───────────────────────
echo ""
echo "[1/2] Configuring model cache..."
mkdir -p /workspace/.cache/datalab
export DATALAB_CACHE_PATH=/workspace/.cache/datalab
grep -qxF 'export DATALAB_CACHE_PATH=/workspace/.cache/datalab' ~/.bashrc \
  || echo 'export DATALAB_CACHE_PATH=/workspace/.cache/datalab' >> ~/.bashrc
echo "✓ DATALAB_CACHE_PATH → /workspace/.cache/datalab (persists across restarts)"

# ── 2. llama.cpp (GGUF quantization) ─────────────────────────────────────────
echo ""
if [[ -f "$LLAMA_BIN" && -f "$LLAMA_CONVERT" ]]; then
  echo "[2/2] llama.cpp already built — restoring from /workspace cache (fast)..."
  apt-get install -y -q libgomp1
  cp "$LLAMA_BIN" /usr/local/bin/llama-quantize
  cat > /usr/local/bin/llama-convert-hf-to-gguf <<WRAPPER
#!/usr/bin/env bash
exec python3 $LLAMA_CONVERT "\$@"
WRAPPER
  chmod +x /usr/local/bin/llama-convert-hf-to-gguf
  echo "✓ llama.cpp binaries restored from cache"
else
  echo "[2/2] Building llama.cpp (first time — cached to /workspace for future restarts)..."
  apt-get update -qq && apt-get install -y -q build-essential cmake libgomp1 curl git

  export PATH=/usr/local/cuda/bin:$PATH
  export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH

  rm -rf "$LLAMA_DIR"
  git clone --depth 1 https://github.com/ggerganov/llama.cpp "$LLAMA_DIR"
  cd "$LLAMA_DIR"
  cmake -B build -DGGML_CUDA=ON -DCMAKE_BUILD_TYPE=Release
  cmake --build build --config Release -j$(nproc)
  cp build/bin/llama-quantize /usr/local/bin/

  cat > /usr/local/bin/llama-convert-hf-to-gguf <<WRAPPER
#!/usr/bin/env bash
exec python3 $LLAMA_CONVERT "\$@"
WRAPPER
  chmod +x /usr/local/bin/llama-convert-hf-to-gguf

  echo "✓ llama.cpp built and cached to $LLAMA_DIR"
  echo "  Next pod restart will skip the build entirely."
fi

# ── Verify ────────────────────────────────────────────────────────────────────
echo ""
echo "Verifying..."
python3 -c "import torch; print(f'✓ torch {torch.__version__}  |  CUDA: {torch.cuda.is_available()}')"
python3 -c "import transformers; print(f'✓ transformers {transformers.__version__}')"
python3 -c "import peft; print(f'✓ peft {peft.__version__}')"
python3 -c "import bitsandbytes; print(f'✓ bitsandbytes {bitsandbytes.__version__}')"
python3 -c "import boto3; print(f'✓ boto3 {boto3.__version__}')"
llama-quantize --help > /dev/null 2>&1 && echo "✓ llama-quantize"
llama-convert-hf-to-gguf --help > /dev/null 2>&1 && echo "✓ llama-convert-hf-to-gguf"

echo ""
echo "================================================================"
echo " Setup complete! Start the server with:"
echo "   cd /workspace && DATALAB_CACHE_PATH=/workspace/.cache/datalab \\"
echo "   python -m uvicorn ai-ml.server:app --host 0.0.0.0 --port 8000 --log-level info"
echo "================================================================"