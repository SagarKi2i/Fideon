#!/usr/bin/env bash
# =============================================================================
# Fideon RunPod — one-shot setup script
# Run once after uploading the ai-ml/ folder to /workspace/ai-ml/
#
#   bash /workspace/ai-ml/setup.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKIP_PIP=0
SKIP_VERIFY=0
for arg in "$@"; do
  [[ "$arg" == "--skip-pip" ]]    && SKIP_PIP=1
  [[ "$arg" == "--skip-verify" ]] && SKIP_VERIFY=1
done

echo "================================================================"
echo " Fideon RunPod Setup"
echo "================================================================"

# ── 1. Python dependencies ────────────────────────────────────────────────────
if [[ "$SKIP_PIP" -eq 0 ]]; then
  echo ""
  echo "[1/4] Installing Python packages..."
  pip install -q -r "$SCRIPT_DIR/requirements.txt"
  echo "✓ Python packages installed"
else
  echo "[1/4] Skipping pip install (--skip-pip)"
fi

# ── 2. llama.cpp (GGUF quantization — compiled with CUDA) ────────────────────
echo ""
echo "[2/4] Building llama.cpp with CUDA support..."
apt-get update -qq && apt-get install -y -q build-essential cmake libgomp1 curl git

export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH

if [[ -d /workspace/llama.cpp ]]; then
  echo "  llama.cpp already cloned — pulling latest..."
  git -C /workspace/llama.cpp pull --ff-only || true
else
  git clone --depth 1 https://github.com/ggerganov/llama.cpp /workspace/llama.cpp
fi

cd /workspace/llama.cpp
cmake -B build -DGGML_CUDA=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j$(nproc)
cp build/bin/llama-quantize /usr/local/bin/

# ── 3. llama.cpp Python dependencies (needed by convert_hf_to_gguf.py) ───────
echo ""
echo "[3/4] Installing llama.cpp Python requirements..."
if [[ -f /workspace/llama.cpp/requirements.txt ]]; then
  pip install -q -r /workspace/llama.cpp/requirements.txt
fi
# Ensure gguf package is available (converter dependency)
pip install -q gguf

# Wrap convert_hf_to_gguf.py as a callable command
cat > /usr/local/bin/llama-convert-hf-to-gguf <<'WRAPPER'
#!/usr/bin/env bash
exec python3 /workspace/llama.cpp/convert_hf_to_gguf.py "$@"
WRAPPER
chmod +x /usr/local/bin/llama-convert-hf-to-gguf

echo "✓ llama.cpp built with CUDA"

# ── 4. Verify ─────────────────────────────────────────────────────────────────
if [[ "$SKIP_VERIFY" -eq 0 ]]; then
  echo ""
  echo "[4/4] Verifying..."
  python3 -c "import torch; print(f'✓ torch {torch.__version__}  |  CUDA: {torch.cuda.is_available()}')"
  python3 -c "import transformers; print(f'✓ transformers {transformers.__version__}')"
  python3 -c "import peft; print(f'✓ peft {peft.__version__}')"
  python3 -c "import bitsandbytes; print(f'✓ bitsandbytes {bitsandbytes.__version__}')"
  python3 -c "import boto3; print(f'✓ boto3 {boto3.__version__}')"
  python3 -c "import gguf; print(f'✓ gguf (llama.cpp converter dependency)')"
  llama-quantize --help > /dev/null && echo "✓ llama-quantize (CUDA)"
  llama-convert-hf-to-gguf --help > /dev/null && echo "✓ llama-convert-hf-to-gguf"
else
  echo "[4/4] Skipping verification (--skip-verify)"
fi

echo ""
echo "================================================================"
echo " Setup complete! Start the server with:"
echo "   cd /workspace && python -m uvicorn ai-ml.server:app --host 0.0.0.0 --port 8000"
echo "================================================================"
