#!/usr/bin/env bash
# =============================================================================
# Fideon RunPod — one-shot setup script
# Run once after uploading the runpod/ folder to /workspace/runpod/
#
#   bash /workspace/runpod/setup.sh
# =============================================================================
set -euo pipefail

SKIP_PIP=0
for arg in "$@"; do [[ "$arg" == "--skip-pip" ]] && SKIP_PIP=1; done

echo "================================================================"
echo " Fideon RunPod Setup"
echo "================================================================"

# ── 1. Python dependencies ────────────────────────────────────────────────────
if [[ "$SKIP_PIP" -eq 0 ]]; then
  echo ""
  echo "[1/3] Installing Python packages..."
  pip install -q -r /workspace/runpod/requirements.txt
  echo "✓ Python packages installed"
else
  echo "[1/3] Skipping pip install (--skip-pip)"
fi

# ── 2. llama.cpp (GGUF quantization — compiled with CUDA for H100) ────────────
echo ""
echo "[2/3] Building llama.cpp with CUDA support..."
apt-get update -qq && apt-get install -y -q build-essential cmake libgomp1 curl git

git clone --depth 1 https://github.com/ggerganov/llama.cpp /opt/llama.cpp
cd /opt/llama.cpp
cmake -B build -DGGML_CUDA=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j$(nproc)
cp build/bin/llama-quantize /usr/local/bin/

# Wrap convert_hf_to_gguf.py as a callable command
cat > /usr/local/bin/llama-convert-hf-to-gguf <<'WRAPPER'
#!/usr/bin/env bash
exec python3 /opt/llama.cpp/convert_hf_to_gguf.py "$@"
WRAPPER
chmod +x /usr/local/bin/llama-convert-hf-to-gguf

echo "✓ llama.cpp built with CUDA"

# ── 3. Verify ─────────────────────────────────────────────────────────────────
echo ""
echo "[3/3] Verifying..."
python3 -c "import torch; print(f'✓ torch {torch.__version__}  |  CUDA: {torch.cuda.is_available()}')"
python3 -c "import transformers; print(f'✓ transformers {transformers.__version__}')"
python3 -c "import peft; print(f'✓ peft {peft.__version__}')"
python3 -c "import bitsandbytes; print(f'✓ bitsandbytes {bitsandbytes.__version__}')"
python3 -c "import boto3; print(f'✓ boto3 {boto3.__version__}')"
llama-quantize --help > /dev/null && echo "✓ llama-quantize (CUDA)"
llama-convert-hf-to-gguf --help > /dev/null && echo "✓ llama-convert-hf-to-gguf"

echo ""
echo "================================================================"
echo " Setup complete! Start the server with:"
echo "   cd /workspace/runpod && python server.py"
echo "================================================================"
