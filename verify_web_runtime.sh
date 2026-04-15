#!/usr/bin/env bash
# Verify runtime assumptions for the web sequence manager on port 5000.

set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:5000}"
SEQUENCE_URL="${BASE_URL%/}/sequence/"
V3_URL="${BASE_URL%/}/sequence/v3"

check_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[FAIL] missing command: $1"
    exit 1
  fi
}

check_cmd curl
check_cmd grep

echo "[INFO] checking web runtime at: $BASE_URL"

if ! curl -fsS "$SEQUENCE_URL" >/tmp/biolab_sequence_page.html; then
  echo "[FAIL] cannot fetch $SEQUENCE_URL"
  echo "       ensure server is running on port 5000"
  exit 1
fi

if grep -Eq 'react/assets/index\.(js|css)\?v=[0-9]+' /tmp/biolab_sequence_page.html; then
  echo "[PASS] versioned React assets detected"
else
  echo "[FAIL] versioned React assets not found"
  exit 1
fi

if grep -Eq 'static/js/main.js|project-tree.js|sequence-viewer.js|ove-editor.js' /tmp/biolab_sequence_page.html; then
  echo "[FAIL] legacy scripts still present in /sequence/"
  exit 1
else
  echo "[PASS] no legacy scripts injected on /sequence/"
fi

V3_STATUS="$(curl -s -o /dev/null -w '%{http_code}' "$V3_URL")"
if [ "$V3_STATUS" = "302" ]; then
  echo "[PASS] /sequence/v3 redirects (302)"
else
  echo "[WARN] /sequence/v3 returned status: $V3_STATUS (expected 302)"
fi

echo "[DONE] runtime checks completed."
