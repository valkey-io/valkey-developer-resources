#!/usr/bin/env bash
# Health check for Valkey instance used by the Gorse cookbook sample.
set -euo pipefail

VALKEY_HOST="${VALKEY_HOST:-localhost}"
VALKEY_PORT="${VALKEY_PORT:-6379}"

echo "Checking Valkey at ${VALKEY_HOST}:${VALKEY_PORT}..."

# PING
if ! valkey-cli -h "$VALKEY_HOST" -p "$VALKEY_PORT" PING | grep -q PONG; then
  echo "❌ PING failed"
  exit 1
fi
echo "PING: PONG"

# Server info
VERSION=$(valkey-cli -h "$VALKEY_HOST" -p "$VALKEY_PORT" INFO server | grep -E "^(valkey_version|redis_version):" | head -1)
echo "Version: ${VERSION}"

# Check search module
if valkey-cli -h "$VALKEY_HOST" -p "$VALKEY_PORT" MODULE LIST | grep -q "search"; then
  echo "✅ valkey-search module loaded"
else
  echo "⚠️  valkey-search module NOT loaded"
fi

echo ""
echo "✅ Health check passed — Valkey is ready."
