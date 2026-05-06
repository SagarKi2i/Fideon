#!/usr/bin/env bash
# =============================================================================
# Fideon RunPod — one-shot setup script
# Run once after uploading the ai-ml/ folder to /workspace/ai-ml/
#
#   bash /workspace/ai-ml/setup.sh
#
# WHY /workspace/ for llama.cpp and binaries:
#   RunPod resets the system volume (/opt/, /usr/local/) on every pod restart.
#   Only /workspace/ (the network volume) persists. Installing here means
#   setup.sh only needs to run once — not after every restart.
# =============================================================================
# -e is intentionally omitted: cmake --build can receive SIGTERM at the very
# end of a long build (RunPod timeout / container preemption) and would exit
# non-zero even though all binaries were already written to disk.  We check
# for the binary explicitly after the build instead of relying on exit codes.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLAMA_DIR="/workspace/llama.cpp"
BIN_DIR="/workspace/bin"
SKIP_PIP=0
SKIP_VERIFY=0
for arg in "$@"; do
  [[ "$arg" == "--skip-pip" ]]    && SKIP_PIP=1
  [[ "$arg" == "--skip-verify" ]] && SKIP_VERIFY=1
done

mkdir -p "$BIN_DIR"

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

if [[ -d "$LLAMA_DIR" ]]; then
  echo "  llama.cpp already cloned at $LLAMA_DIR — pulling latest..."
  git -C "$LLAMA_DIR" pull --ff-only || true
else
  git clone --depth 1 https://github.com/ggerganov/llama.cpp "$LLAMA_DIR"
fi

cd "$LLAMA_DIR"

# Skip cmake entirely if the binary is already present (e.g. interrupted build
# that wrote the binary before the SIGTERM arrived).
if [[ -f build/bin/llama-quantize ]]; then
  echo "  llama-quantize already built — skipping cmake"
else
  cmake -B build -DGGML_CUDA=ON -DCMAKE_BUILD_TYPE=Release
  cmake --build build --config Release -j$(nproc)
fi

# Install to /workspace/bin so binaries survive pod restarts
cp build/bin/llama-quantize "$BIN_DIR/llama-quantize" 2>/dev/null || true

# ── 3. llama.cpp Python dependencies (needed by convert_hf_to_gguf.py) ───────
echo ""
echo "[3/4] Installing llama.cpp Python requirements..."
if [[ -f "$LLAMA_DIR/requirements.txt" ]]; then
  pip install -q -r "$LLAMA_DIR/requirements.txt"
fi
# Ensure gguf package is available (converter dependency)
pip install -q gguf

# Wrap convert_hf_to_gguf.py as a callable command in /workspace/bin
cat > "$BIN_DIR/llama-convert-hf-to-gguf" <<WRAPPER
#!/usr/bin/env bash
exec python3 $LLAMA_DIR/convert_hf_to_gguf.py "\$@"
WRAPPER
chmod +x "$BIN_DIR/llama-convert-hf-to-gguf"

echo "✓ llama.cpp built with CUDA — binaries in $BIN_DIR"

# ── 4. Verify ─────────────────────────────────────────────────────────────────
if [[ "$SKIP_VERIFY" -eq 0 ]]; then
  echo ""
  echo "[4/4] Verifying..."
  export PATH="$BIN_DIR:$PATH"
  python3 -c "import torch; print(f'✓ torch {torch.__version__}  |  CUDA: {torch.cuda.is_available()}')"
  python3 -c "import transformers; print(f'✓ transformers {transformers.__version__}')"
  python3 -c "import peft; print(f'✓ peft {peft.__version__}')"
  python3 -c "import bitsandbytes; print(f'✓ bitsandbytes {bitsandbytes.__version__}')"
  python3 -c "import boto3; print(f'✓ boto3 {boto3.__version__}')"
  python3 -c "import gguf; print(f'✓ gguf (llama.cpp converter dependency)')"
  "$BIN_DIR/llama-quantize" --help > /dev/null && echo "✓ llama-quantize (CUDA)"
  "$BIN_DIR/llama-convert-hf-to-gguf" --help > /dev/null && echo "✓ llama-convert-hf-to-gguf"
else
  echo "[4/4] Skipping verification (--skip-verify)"
fi

echo ""
echo "================================================================"
echo " Setup complete! Binaries persist at $BIN_DIR — no re-run needed"
echo " after pod restart."
echo ""
echo " Start the server with:"
echo "   bash /workspace/ai-ml/startup.sh"
echo "================================================================"
