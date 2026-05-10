#!/usr/bin/env bash
set -euo pipefail

echo "[1/4] Installing system dependencies..."
apt-get update -qq && apt-get install -y build-essential cmake gpg libgomp1 curl git

echo "[2/4] Compiling llama.cpp with CUDA support..."
git clone --depth 1 https://github.com/ggerganov/llama.cpp /opt/llama.cpp
cd /opt/llama.cpp
cmake -B build -DGGML_CUDA=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j$(nproc)
cp build/bin/llama-quantize /usr/local/bin/

# Wrap convert_hf_to_gguf.py as a callable command — works on any llama.cpp version
cat > /usr/local/bin/llama-convert-hf-to-gguf <<'WRAPPER'
#!/usr/bin/env bash
exec python3 /opt/llama.cpp/convert_hf_to_gguf.py "$@"
WRAPPER
chmod +x /usr/local/bin/llama-convert-hf-to-gguf

echo "[3/4] Installing Python packages..."
pip install -q -r "$(dirname "$0")/requirements.txt"

echo "[4/4] Verifying installations..."
python3 -c "import boto3, botocore, transformers, peft, supabase; print('✓ Python packages OK')"
llama-quantize            --help > /dev/null && echo "✓ llama-quantize OK"
llama-convert-hf-to-gguf --help > /dev/null && echo "✓ llama-convert OK"
gpg --version | head -1           && echo "✓ GPG OK"

echo "Setup complete. Run ./run_pipeline.sh to start."
