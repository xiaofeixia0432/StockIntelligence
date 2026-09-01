#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:5000}"

curl -fsS "$BASE_URL/api/health" >/dev/null

echo "Health check passed: $BASE_URL/api/health"
