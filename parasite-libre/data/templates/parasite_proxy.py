import socket
import threading
import json
import time
import requests
import os

# ============================
# CONFIG FROM ENVIRONMENT
# ============================
LISTEN_PORT = int(os.getenv("LISTEN_PORT", 3333))

UPSTREAM_HOST = os.getenv("UPSTREAM_HOST", "parasite.wtf")
UPSTREAM_PORT = int(os.getenv("UPSTREAM_PORT", 42069))

LIBRE_RPC_HOST = os.getenv("LIBRE_RPC_HOST", "192.168.50.103")
LIBRE_RPC_PORT = int(os.getenv("LIBRE_RPC_PORT", 8442))
LIBRE_RPC_USER = os.getenv("LIBRE_RPC_USER")
LIBRE_RPC_PASS = os.getenv("LIBRE_RPC_PASS")

miner_connections = []
upstream_socket = None
upstream_lock = threading.Lock()

def rpc_call(method, params=[]):
    try:
        url = f"http://{LIBRE_RPC_HOST}:{LIBRE_RPC_PORT}"
        payload = {
            "jsonrpc": "2.0",
            "id": "parasite-gateway",
            "method": method,
            "params": params
        }
        auth = (LIBRE_RPC_USER, LIBRE_RPC_PASS) if LIBRE_RPC_USER and LIBRE_RPC_PASS else None
        r = requests.post(url, json=payload, auth=auth, timeout=12)
        r.raise_for_status()
        result = r.json().get("result")
        print(f"[LIBRE RPC] ✅ {method} success")
        return result
    except Exception as e:
        print(f"[LIBRE RPC] ❌ {method} failed → {e}")
        return None

# Rest of the code (connect_upstream, listen_upstream, etc.) remains the same...
# (I can give you the full file if you want)

if __name__ == "__main__":
    print("=== Parasite Pool Gateway + Libre Node ===")
    print(f"Libre RPC → {LIBRE_RPC_HOST}:{LIBRE_RPC_PORT} | User: {LIBRE_RPC_USER}")
    print(f"Upstream  → {UPSTREAM_HOST}:{UPSTREAM_PORT}")
    
    # Start services...
