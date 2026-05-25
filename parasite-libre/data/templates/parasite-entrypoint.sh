#!/bin/sh
set -eu

echo "[PARASITE-LIBRE] Starting proxy..."
echo "[PARASITE-LIBRE] LibreNode RPC: http://${LIBRE_RPC_HOST}:${LIBRE_RPC_PORT}"
echo "[PARASITE-LIBRE] Parasite Pool: ${PARASITE_HOST}:${PARASITE_PORT}"
echo "[PARASITE-LIBRE] Miner Port: 3333"

# Install dependencies
cd /app
pip install --quiet requests 2>/dev/null || true

# Run the proxy
exec python3 /app/parasite_proxy.py
