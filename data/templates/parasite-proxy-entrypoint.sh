#!/bin/sh
set -eu

echo "[PARASITE-PROXY] Starting..."
echo "[PARASITE-PROXY] LibreNode RPC: http://${LIBRE_RPC_HOST}:${LIBRE_RPC_PORT}"
echo "[PARASITE-PROXY] Parasite Pool: ${PARASITE_HOST}:${PARASITE_PORT}"

# Install dependencies
cd /app
pip install requests python-bitcoinlib --quiet 2>/dev/null || true

# Run the proxy
exec python3 /app/parasite_proxy.py
