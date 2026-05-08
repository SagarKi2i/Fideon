#!/usr/bin/env bash
# Run the full quantization pipeline inside Docker (no WSL2 needed)
# Usage: bash Quantization/run_pipeline_docker.sh
# Run this from the project root in PowerShell:
#   docker run --rm -it \
#     -v "$(pwd)/Quantization:/app" \
#     -v "/workspace:/workspace" \
#     python:3.11-slim bash /app/run_pipeline_docker.sh
# Fix Windows CRLF line endings (harmless if already Unix)
dos2unix /app/*.sh /app/*.py 2>/dev/null || true

# ── Skip adapter creation if it already exists in the named volume ──────────
if [[ -d /workspace/test_adapter && -f /workspace/test_adapter/adapter_config.json ]]; then
    echo "Test adapter already exists at /workspace/test_adapter — skipping creation"
else
    echo "Creating test adapter..."
    python3 /app/create_test_adapter.py --output-dir /workspace/test_adapter
fi

echo "Running pipeline..."
cd /app && bash run_pipeline.sh
