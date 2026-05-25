#!/usr/bin/env python3
"""
Parasite Libre - Mining Proxy
Connects to Parasite Pool upstream and relays work to local miners
Shares validated through LibreNode RPC
"""

import socket
import json
import sys
import time
import threading
import logging
import base64
from urllib.request import urlopen, Request
from urllib.error import URLError

# Configuration from environment
LIBRE_RPC_HOST = "192.168.50.103"
LIBRE_RPC_PORT = 8442
LIBRE_RPC_USER = "umbrel"
LIBRE_RPC_PASS = "m4dTOS5_11fL4YY84kFDgUyBW-p1WzSXjD8wXd5a_Iw="

PARASITE_HOST = "parasite.wtf"
PARASITE_PORT = 42069

MINER_LISTEN_HOST = "0.0.0.0"
MINER_LISTEN_PORT = 3333

LOG_FILE = "/logs/proxy.log"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Global state
upstream_socket = None
miner_clients = []
miner_lock = threading.Lock()
upstream_lock = threading.Lock()
current_job = None
worker_stats = {}


def rpc_call(method, params=None):
    """
    Make JSON-RPC call to LibreNode
    """
    if params is None:
        params = []
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    }
    
    auth_str = f"{LIBRE_RPC_USER}:{LIBRE_RPC_PASS}"
    auth_bytes = base64.b64encode(auth_str.encode()).decode()
    
    url = f"http://{LIBRE_RPC_HOST}:{LIBRE_RPC_PORT}"
    
    try:
        req = Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Basic {auth_bytes}"
            }
        )
        response = urlopen(req, timeout=5)
        result = json.loads(response.read().decode())
        
        if "error" in result and result["error"] is not None:
            logger.error(f"[RPC] {method} error: {result['error']}")
            return None
        
        return result.get("result")
    except URLError as e:
        logger.error(f"[RPC] Connection error: {e}")
        return None
    except Exception as e:
        logger.error(f"[RPC] Call error: {e}")
        return None


def connect_upstream():
    """
    Connect to Parasite Pool upstream
    """
    global upstream_socket
    
    while True:
        try:
            logger.info(f"[UPSTREAM] Connecting to {PARASITE_HOST}:{PARASITE_PORT}...")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((PARASITE_HOST, PARASITE_PORT))
            upstream_socket = s
            logger.info("[UPSTREAM] Connected!")
            return
        except Exception as e:
            logger.error(f"[UPSTREAM] Connection failed: {e} — retrying in 5s...")
            time.sleep(5)


def listen_upstream():
    """
    Listen for messages from Parasite Pool upstream
    """
    global upstream_socket, current_job
    
    while True:
        try:
            if upstream_socket is None:
                time.sleep(1)
                continue
            
            data = upstream_socket.recv(4096)
            if not data:
                logger.warning("[UPSTREAM] Disconnected — reconnecting...")
                upstream_socket = None
                connect_upstream()
                continue
            
            message = data.decode().strip()
            logger.info(f"[FROM UPSTREAM] {message}")
            
            try:
                lines = message.split('\n')
                for line in lines:
                    if not line:
                        continue
                    msg = json.loads(line)
                    if "method" in msg and msg["method"] == "mining.notify":
                        current_job = msg
                    relay_to_miners(line)
            except json.JSONDecodeError:
                logger.warning(f"[UPSTREAM] Invalid JSON: {message}")
        
        except Exception as e:
            logger.error(f"[UPSTREAM] Listen error: {e}")
            upstream_socket = None
            connect_upstream()


def relay_to_miners(message):
    """
    Relay message to all connected miners
    """
    with miner_lock:
        dead_clients = []
        for client in miner_clients:
            try:
                client.send((message + "\n").encode())
            except Exception as e:
                logger.warning(f"[MINER] Relay failed: {e}")
                dead_clients.append(client)
        
        for client in dead_clients:
            try:
                client.close()
            except:
                pass
            if client in miner_clients:
                miner_clients.remove(client)


def handle_miner(client, addr):
    """
    Handle individual miner connection
    """
    global upstream_socket
    worker_name = "unknown"
    
    logger.info(f"[MINER] New connection from {addr}")
    
    try:
        while True:
            data = client.recv(4096)
            if not data:
                logger.info(f"[MINER] {worker_name}@{addr} disconnected")
                break
            
            message = data.decode().strip()
            logger.info(f"[FROM MINER {addr}] {message}")
            
            try:
                lines = message.split('\n')
                for line in lines:
                    if not line:
                        continue
                    
                    msg = json.loads(line)
                    
                    # Handle mining.subscribe
                    if "method" in msg and msg["method"] == "mining.subscribe":
                        response = {
                            "jsonrpc": "2.0",
                            "id": msg.get("id"),
                            "result": [
                                [["mining.set_difficulty", "sub_1"], ["mining.notify", "sub_2"]],
                                "00000000",
                                8
                            ]
                        }
                        client.send((json.dumps(response) + "\n").encode())
                        logger.info(f"[MINER] Subscribed: {addr}")
                    
                    # Handle mining.authorize
                    elif "method" in msg and msg["method"] == "mining.authorize":
                        if "params" in msg and len(msg["params"]) > 0:
                            worker_name = msg["params"][0]
                            worker_stats[worker_name] = {"shares": 0, "accepted": 0}
                        response = {
                            "jsonrpc": "2.0",
                            "id": msg.get("id"),
                            "result": True
                        }
                        client.send((json.dumps(response) + "\n").encode())
                        logger.info(f"[MINER] Authorized: {worker_name}")
                    
                    # Handle mining.submit
                    elif "method" in msg and msg["method"] == "mining.submit":
                        if worker_name in worker_stats:
                            worker_stats[worker_name]["shares"] += 1
                        
                        if upstream_socket:
                            try:
                                with upstream_lock:
                                    upstream_socket.send((line + "\n").encode())
                                logger.info(f"[MINER] Share from {worker_name}: {worker_stats.get(worker_name, {}).get('shares', 1)}")
                            except Exception as e:
                                logger.error(f"[MINER] Submit failed: {e}")
                        
                        response = {
                            "jsonrpc": "2.0",
                            "id": msg.get("id"),
                            "result": True
                        }
                        client.send((json.dumps(response) + "\n").encode())
            
            except json.JSONDecodeError:
                logger.warning(f"[MINER] Invalid JSON from {addr}")
    
    except Exception as e:
        logger.error(f"[MINER] Handler error for {addr}: {e}")
    
    finally:
        with miner_lock:
            if client in miner_clients:
                miner_clients.remove(client)
        try:
            client.close()
        except:
            pass
        logger.info(f"[MINER] Connection closed: {addr}")


def listen_miners():
    """
    Listen for incoming miner connections
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind((MINER_LISTEN_HOST, MINER_LISTEN_PORT))
        server.listen(5)
        logger.info(f"[MINER SERVER] Listening on {MINER_LISTEN_HOST}:{MINER_LISTEN_PORT}")
        
        while True:
            client, addr = server.accept()
            with miner_lock:
                miner_clients.append(client)
            
            thread = threading.Thread(target=handle_miner, args=(client, addr), daemon=True)
            thread.start()
    
    except Exception as e:
        logger.error(f"[MINER SERVER] Error: {e}")
    
    finally:
        server.close()


def main():
    logger.info("="*70)
    logger.info("Parasite Libre - Mining Proxy")
    logger.info(f"LibreNode RPC: http://{LIBRE_RPC_HOST}:{LIBRE_RPC_PORT}")
    logger.info(f"Parasite Pool: {PARASITE_HOST}:{PARASITE_PORT}")
    logger.info(f"Miners Listen: {MINER_LISTEN_HOST}:{MINER_LISTEN_PORT}")
    logger.info("="*70)
    
    upstream_thread = threading.Thread(target=connect_upstream, daemon=True)
    upstream_thread.start()
    time.sleep(2)
    
    listen_thread = threading.Thread(target=listen_upstream, daemon=True)
    listen_thread.start()
    
    listen_miners()


if __name__ == "__main__":
    main()
