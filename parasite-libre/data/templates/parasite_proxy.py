import socket
import threading
import json
import time
import requests
import os

# ============================
# CONFIGURATION FROM ENVIRONMENT VARIABLES
# ============================
LISTEN_PORT = int(os.getenv("LISTEN_PORT", 3333))

UPSTREAM_HOST = os.getenv("UPSTREAM_HOST", "parasite.wtf")
UPSTREAM_PORT = int(os.getenv("UPSTREAM_PORT", 42069))

# Libre Node RPC
LIBRE_RPC_HOST = os.getenv("LIBRE_RPC_HOST", "192.168.50.103")
LIBRE_RPC_PORT = int(os.getenv("LIBRE_RPC_PORT", 8442))
LIBRE_RPC_USER = os.getenv("LIBRE_RPC_USER")
LIBRE_RPC_PASS = os.getenv("LIBRE_RPC_PASS")

# Global variables
miner_connections = []
upstream_socket = None
upstream_lock = threading.Lock()


def rpc_call(method, params=[]):
    """Call Libre Node RPC"""
    try:
        url = f"http://{LIBRE_RPC_HOST}:{LIBRE_RPC_PORT}"
        payload = {
            "jsonrpc": "2.0",
            "id": "parasite-proxy",
            "method": method,
            "params": params
        }
        auth = (LIBRE_RPC_USER, LIBRE_RPC_PASS) if LIBRE_RPC_USER and LIBRE_RPC_PASS else None
        r = requests.post(url, json=payload, auth=auth, timeout=10)
        r.raise_for_status()
        result = r.json().get("result")
        print(f"[LIBRE RPC] ✅ {method} success")
        return result
    except Exception as e:
        print(f"[LIBRE RPC] ❌ {method} failed: {e}")
        return None


def get_block_template():
    """Get current block template from Libre Node"""
    return rpc_call("getblocktemplate", [{"rules": ["segwit"]}])


def connect_upstream():
    """Connect to Parasite Pool"""
    global upstream_socket
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((UPSTREAM_HOST, UPSTREAM_PORT))
            with upstream_lock:
                upstream_socket = s
            print(f"[UPSTREAM] ✅ Connected to Parasite Pool ({UPSTREAM_HOST}:{UPSTREAM_PORT})")
            return True
        except Exception as e:
            print(f"[UPSTREAM] ❌ Connection failed: {e} - retrying in 5s...")
            time.sleep(5)


def listen_upstream():
    """Listen for messages from Parasite Pool and broadcast to miners"""
    global upstream_socket
    buffer = b""
    while True:
        try:
            with upstream_lock:
                if not upstream_socket:
                    time.sleep(1)
                    continue
                data = upstream_socket.recv(4096)
            if not data:
                print("[UPSTREAM] Disconnected, reconnecting...")
                connect_upstream()
                continue

            buffer += data
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                if line.strip():
                    try:
                        msg = json.loads(line.decode())
                        broadcast_to_miners(msg)
                    except:
                        pass
        except Exception as e:
            print(f"[UPSTREAM LISTEN ERROR] {e}")
            connect_upstream()


def broadcast_to_miners(msg):
    """Send message to all connected miners"""
    dead = []
    for conn, addr in miner_connections[:]:
        try:
            conn.send((json.dumps(msg) + "\n").encode())
        except:
            dead.append((conn, addr))
    for d in dead:
        if d in miner_connections:
            miner_connections.remove(d)


def forward_to_pool(data):
    """Forward miner data (shares, subscribe, etc.) to Parasite Pool"""
    global upstream_socket
    try:
        with upstream_lock:
            if upstream_socket:
                upstream_socket.send(data)
                return True
    except:
        pass
    return False


def handle_miner(conn, addr):
    """Handle individual miner connection"""
    print(f"[MINER] {addr} connected")
    miner_connections.append((conn, addr))

    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            forward_to_pool(data)
    except:
        pass
    finally:
        if (conn, addr) in miner_connections:
            miner_connections.remove((conn, addr))
        conn.close()
        print(f"[MINER] {addr} disconnected")


def start_stratum_server():
    """Start Stratum server for miners"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", LISTEN_PORT))
    server.listen(50)
    print(f"[GATEWAY] ✅ Listening for miners on port {LISTEN_PORT}")

    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_miner, args=(conn, addr), daemon=True).start()


# ============================
# MAIN
# ============================
if __name__ == "__main__":
    print("=" * 50)
    print("Parasite Pool Proxy + Libre Node")
    print("=" * 50)
    print(f"Libre Node  → {LIBRE_RPC_HOST}:{LIBRE_RPC_PORT}")
    print(f"Upstream    → {UPSTREAM_HOST}:{UPSTREAM_PORT}")
    print(f"Listening   → 0.0.0.0:{LISTEN_PORT}")
    print("=" * 50)

    # Start upstream connection to Parasite
    connect_upstream()
    threading.Thread(target=listen_upstream, daemon=True).start()

    # Start miner server
    threading.Thread(target=start_stratum_server, daemon=True).start()

    # Periodic Libre Node status
    while True:
        template = get_block_template()
        time.sleep(60)
