#!/usr/bin/env bash
# ============================================================================
# setup_local.sh  —  CPU-only llama.cpp setup for LOCAL TESTING in WSL2
# ============================================================================
# Use this instead of setup.sh when testing on a local Windows machine via WSL2.
# No CUDA required. The quantized models will be ~650MB (Q4_K_M).
#
# Run once:  bash Quantization/setup_local.sh
# ============================================================================
set -euo pipefail

LLAMA_DIR="/opt/llama.cpp"

echo "========================================"
echo " Local test setup (CPU-only, no CUDA)  "
echo "========================================"

# ── 1. System dependencies ───────────────────────────────────────────────────
echo ""
echo "[1/4] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y \
    build-essential \
    cmake \
    gpg \
    libgomp1 \
    curl \
    git \
    python3-pip \
    python3-venv \
    --no-install-recommends

# ── 2. Build llama.cpp (CPU only) ────────────────────────────────────────────
echo ""
echo "[2/4] Compiling llama.cpp (CPU only — this takes 3-5 minutes)..."

if [[ -d "$LLAMA_DIR" ]]; then
    echo "  llama.cpp already cloned at $LLAMA_DIR, pulling latest..."
    git -C "$LLAMA_DIR" pull --ff-only
else
    git clone --depth 1 https://github.com/ggerganov/llama.cpp "$LLAMA_DIR"
fi

cd "$LLAMA_DIR"
cmake -B build \
    -DCMAKE_BUILD_TYPE=Release \
    -DGGML_CUDA=OFF \
    -DGGML_METAL=OFF
cmake --build build --config Release -j"$(nproc)"

sudo cp build/bin/llama-quantize /usr/local/bin/llama-quantize
sudo chmod +x /usr/local/bin/llama-quantize

# Wrap the Python conversion script as a callable command
sudo tee /usr/local/bin/llama-convert-hf-to-gguf > /dev/null <<'WRAPPER'
#!/usr/bin/env bash
exec python3 /opt/llama.cpp/convert_hf_to_gguf.py "$@"
WRAPPER
sudo chmod +x /usr/local/bin/llama-convert-hf-to-gguf

echo "  ✓ llama-quantize installed to /usr/local/bin/"
echo "  ✓ llama-convert-hf-to-gguf wrapper installed"

# ── 3. Python packages ───────────────────────────────────────────────────────
echo ""
echo "[3/4] Installing Python packages..."
pip3 install -q --upgrade pip
pip3 install -q -r "$(dirname "$0")/requirements.txt"

# Also install huggingface_hub (needed for model download in quantize.py)
pip3 install -q huggingface_hub

# ── 4. Verify ────────────────────────────────────────────────────────────────
echo ""
echo "[4/4] Verifying installations..."

python3 -c "
import boto3, botocore, transformers, peft, supabase, huggingface_hub
print('  ✓ Python packages: boto3, transformers, peft, supabase, huggingface_hub')
"

llama-quantize --help > /dev/null 2>&1 \
    && echo "  ✓ llama-quantize OK" \
    || echo "  ✗ llama-quantize FAILED — check build output above"

llama-convert-hf-to-gguf --help > /dev/null 2>&1 \
    && echo "  ✓ llama-convert-hf-to-gguf OK" \
    || echo "  ✗ llama-convert-hf-to-gguf FAILED — check Python path"

gpg --version | head -1 \
    && echo "  ✓ GPG OK" \
    || echo "  ✗ GPG FAILED — run: sudo apt-get install -y gpg"

echo ""
echo "========================================"
echo " Setup complete!                        "
echo " Next: fill in Quantization/config.env.local"
echo "       then run Quantization/run_pipeline.sh"
echo "========================================"
