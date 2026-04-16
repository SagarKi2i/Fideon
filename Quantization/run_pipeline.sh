#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

START=$(date +%s)
echo "=== Quantization Pipeline — $(date -u) ==="

# Validate config.env exists and is populated
if [[ ! -f config.env ]]; then
    echo "ERROR: config.env not found. Copy config.env.example and populate it."
    exit 1
fi

source config.env

# Validate all required env vars
for var in SEAWEEDFS_ENDPOINT SEAWEEDFS_ACCESS_KEY SEAWEEDFS_SECRET_KEY \
           SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY \
           ADAPTER_PATH OUTPUT_DIR MODEL_VERSION DOMAIN \
           MIN_ELECTRON_VER CANARY_PCT ROLLBACK_SAFE; do
    [[ -z "${!var:-}" ]] && { echo "ERROR: $var is not set in config.env"; exit 1; }
done

# Validate adapter exists
[[ ! -d "$ADAPTER_PATH" ]] && { echo "ERROR: ADAPTER_PATH not found: $ADAPTER_PATH"; exit 1; }

# Validate GPG key is imported — fail before wasting GPU time
if ! gpg --list-secret-keys 2>/dev/null | grep -q "sec"; then
    echo "ERROR: No GPG secret key found. Import your release key first:"
    echo "  gpg --import release-private.key"
    exit 1
fi
echo "✓ GPG key present"

Q5_FILE="$OUTPUT_DIR/model-q5_k_m.gguf"
Q4_FILE="$OUTPUT_DIR/model-q4_k_m.gguf"
MANIFEST="$OUTPUT_DIR/manifest.json"

if [[ -f "$Q5_FILE" && -f "$Q4_FILE" && -f "$MANIFEST" ]]; then
    echo "[1/2] GGUF artifacts already exist — skipping quantization"
    echo "      Delete $OUTPUT_DIR to force re-quantization"
else
    echo "[1/2] Running quantize.py..."
    python3 quantize.py
fi

echo "[2/2] Running upload.py..."
python3 upload.py

END=$(date +%s)
echo "=== Pipeline finished successfully in $((END-START))s ==="
