#!/usr/bin/env bash
# ============================================================================
# test_backend.sh  —  Verify the adapter registry endpoints end-to-end
# ============================================================================
# Prerequisites:
#   1. Backend is running  (e.g. uvicorn app.main:app --port 8000)
#   2. SeaweedFS is running (docker compose -f docker-compose.seaweedfs-local.yml up -d)
#   3. upload.py has already run successfully (so adapter_registry has rows)
#   4. A registered device exists and you have its JWT
#
# Usage:
#   DEVICE_JWT=<jwt> bash Quantization/test_backend.sh
#   DEVICE_JWT=<jwt> API_BASE=http://localhost:8000 DOMAIN=broker bash Quantization/test_backend.sh
# ============================================================================
set -euo pipefail

API_BASE="${API_BASE:-http://localhost:8000}"
DEVICE_JWT="${DEVICE_JWT:-}"
DOMAIN="${DOMAIN:-broker}"
VERSION="${VERSION:-v0.1.0-test}"
QUANT="${QUANT:-q4_k_m}"

# ── Validate ─────────────────────────────────────────────────────────────────
if [[ -z "$DEVICE_JWT" ]]; then
    echo ""
    echo "ERROR: DEVICE_JWT is not set."
    echo ""
    echo "To get a device JWT:"
    echo "  1. Register a device via POST /api/v1/devices/register"
    echo "  2. Copy the jwt field from the response"
    echo "  3. Run:  DEVICE_JWT=<jwt> bash Quantization/test_backend.sh"
    echo ""
    echo "Quick device registration (requires user JWT):"
    echo '  curl -s -X POST http://localhost:8000/api/v1/devices/register \'
    echo '    -H "Authorization: Bearer <user_jwt>" \'
    echo '    -H "Content-Type: application/json" \'
    echo '    -d '"'"'{"device_name":"test-device","device_type":"desktop"}'"'"' | python3 -m json.tool'
    echo ""
    exit 1
fi

echo ""
echo "=================================================="
echo " Adapter Registry Backend Test"
echo "=================================================="
echo " API_BASE  : $API_BASE"
echo " DOMAIN    : $DOMAIN"
echo " VERSION   : $VERSION"
echo " QUANT     : $QUANT"
echo ""

# ── Helper ───────────────────────────────────────────────────────────────────
call_api() {
    local label="$1"
    local url="$2"
    echo "── $label ──────────────────────────────────────────"
    echo "GET $url"
    echo ""
    local status
    status=$(curl -s -o /tmp/_test_body.json -w "%{http_code}" \
        -H "Authorization: Bearer $DEVICE_JWT" \
        "$url")
    echo "HTTP $status"
    cat /tmp/_test_body.json | python3 -m json.tool 2>/dev/null || cat /tmp/_test_body.json
    echo ""
    if [[ "$status" != "200" ]]; then
        echo "FAIL: Expected HTTP 200, got $status"
        return 1
    fi
}

PASS=0
FAIL=0

# ── Test 1: Check for update ──────────────────────────────────────────────────
echo "[TEST 1] GET /api/v1/adapter/latest"
if call_api "Check update availability" \
    "$API_BASE/api/v1/adapter/latest?domain=$DOMAIN"; then
    AVAILABLE=$(python3 -c "import json,sys; d=json.load(open('/tmp/_test_body.json')); print(d.get('available','?'))")
    echo "  available = $AVAILABLE"
    if [[ "$AVAILABLE" == "True" ]] || [[ "$AVAILABLE" == "true" ]]; then
        echo "  ✓ Update IS available"
        PASS=$((PASS+1))
    else
        echo "  ✗ available=false — check that upload.py ran and CANARY_PCT=100 in config"
        FAIL=$((FAIL+1))
    fi
else
    FAIL=$((FAIL+1))
fi

echo ""

# ── Test 2: Get GGUF download URL ─────────────────────────────────────────────
echo "[TEST 2] GET /api/v1/adapter/download-url (GGUF)"
if call_api "Get GGUF presigned URL" \
    "$API_BASE/api/v1/adapter/download-url?domain=$DOMAIN&version=$VERSION&quant=$QUANT"; then
    URL=$(python3 -c "import json,sys; d=json.load(open('/tmp/_test_body.json')); print(d.get('url',''))")
    if [[ -n "$URL" ]]; then
        echo "  ✓ Got presigned URL (first 80 chars): ${URL:0:80}..."
        PASS=$((PASS+1))
    else
        echo "  ✗ No URL in response"
        FAIL=$((FAIL+1))
    fi
else
    FAIL=$((FAIL+1))
fi

echo ""

# ── Test 3: Get .sig download URL ─────────────────────────────────────────────
echo "[TEST 3] GET /api/v1/adapter/download-url?sig=true"
if call_api "Get .sig presigned URL" \
    "$API_BASE/api/v1/adapter/download-url?domain=$DOMAIN&version=$VERSION&quant=$QUANT&sig=true"; then
    URL=$(python3 -c "import json,sys; d=json.load(open('/tmp/_test_body.json')); print(d.get('url',''))")
    if [[ -n "$URL" ]]; then
        echo "  ✓ Got .sig presigned URL"
        PASS=$((PASS+1))
    else
        echo "  ✗ No URL in response for .sig"
        FAIL=$((FAIL+1))
    fi
else
    FAIL=$((FAIL+1))
fi

echo ""

# ── Test 4: Verify presigned URL actually downloads ───────────────────────────
echo "[TEST 4] Download GGUF via presigned URL (first 1MB)"
URL=$(python3 -c "import json,sys; d=json.load(open('/tmp/_test_body.json')); print(d.get('url',''))" 2>/dev/null || echo "")

# Get a fresh URL for the GGUF
GGUF_URL=$(curl -s \
    -H "Authorization: Bearer $DEVICE_JWT" \
    "$API_BASE/api/v1/adapter/download-url?domain=$DOMAIN&version=$VERSION&quant=$QUANT" \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('url',''))")

if [[ -n "$GGUF_URL" ]]; then
    echo "Downloading first 1 MB of GGUF from SeaweedFS..."
    HTTP_STATUS=$(curl -s -o /tmp/_test_gguf_partial.bin -w "%{http_code}" \
        --range 0-1048575 \
        "$GGUF_URL" 2>/dev/null || echo "000")

    if [[ "$HTTP_STATUS" == "200" ]] || [[ "$HTTP_STATUS" == "206" ]]; then
        SIZE=$(wc -c < /tmp/_test_gguf_partial.bin)
        echo "  ✓ Download successful — received $SIZE bytes"
        # Check GGUF magic header
        MAGIC=$(xxd -l 4 /tmp/_test_gguf_partial.bin 2>/dev/null | awk '{print $2$3}' | head -1 || echo "")
        if [[ "$MAGIC" == "47475546" ]]; then
            echo "  ✓ GGUF magic header verified (GGUF)"
        else
            echo "  ℹ Magic bytes: $MAGIC (expected 47475546 for GGUF)"
        fi
        PASS=$((PASS+1))
    else
        echo "  ✗ Download HTTP $HTTP_STATUS"
        FAIL=$((FAIL+1))
    fi
    rm -f /tmp/_test_gguf_partial.bin
else
    echo "  ✗ Could not get GGUF URL for download test"
    FAIL=$((FAIL+1))
fi

echo ""
echo "=================================================="
echo " Results: $PASS passed / $FAIL failed"
echo "=================================================="

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
