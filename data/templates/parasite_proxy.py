#!/usr/bin/env python3
"""
Parasite Pool Proxy for LibreNode
Connects to Parasite Pool upstream and relays work to local miners
Shares are validated through LibreNode RPC
"""

import socket
import struct
import json
import sys
import time
import threading
import logging
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError
import hashlib

# Configuration
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
worker_name = "unknown"


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
    import base64
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
            logger.error(f"RPC Error: {result['error']}")
            return None
        
        return result.get("result")
    except URLError as e:
        logger.error(f"RPC Connection Error: {e}")
        return None
    except Exception as e:
        logger.error(f"RPC Call Error: {e}")
        return None


def submit_block(block_hex):
    """
    Submit block to LibreNode
    """
    try:
        result = rpc_call("submitblock", [block_hex])
        if result is None or result == "":
            logger.info("[BLOCK] Successfully submitted!")
            return True
        else:
            logger.warning(f"[BLOCK] Submit failed: {result}")
            return False
    except Exception as e:
        logger.error(f"[BLOCK] Error submitting: {e}")
        return False


def connect_upstream():
    """
    Connect to Parasite Pool upstream
    """
    global upstream_socket
    
    while True:
        try:
            logger.info(f"[UPSTREAM] Connecting to Parasite Pool at {PARASITE_HOST}:{PARASITE_PORT}...")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((PARASITE_HOST, PARASITE_PORT))
            upstream_socket = s
            logger.info("[UPSTREAM] Connected to Parasite Pool!")
            return
        except Exception as e:
            logger.error(f"[UPSTREAM] Connection failed: {e} — retrying in 5 seconds...")
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
            
            # Parse and relay to miners
            try:
                lines = message.split('\n')
                for line in lines:
                    if not line:
                        continue
                    
                    msg = json.loads(line)
                    
                    # Store current job
                    if "method" in msg and msg["method"] == "mining.notify":
                        current_job = msg
                    
                    # Relay to all connected miners
                    relay_to_miners(line)
            except json.JSONDecodeError:
                logger.warning(f"[UPSTREAM] Invalid JSON: {message}")
        
        except Exception as e:
            logger.error(f"[UPSTREAM] Listen error: {e}")
            upstream_socket = None
            connect_upstream()


def relay_to_miners(message):
    """
    Relay upstream message to all connected miners
    """
    with miner_lock:
        dead_clients = []
        for client in miner_clients:
            try:
                client.send((message + "\n").encode())
            except Exception as e:
                logger.warning(f"[MINER] Failed to relay to {client.getpeername()}: {e}")
                dead_clients.append(client)
        
        # Remove dead clients
        for client in dead_clients:
            try:
                client.close()
            except:
                pass
            miner_clients.remove(client)


def handle_miner(client, addr):
    """
    Handle individual miner connection
    """
    global upstream_socket, worker_name
    
    logger.info(f"[MINER] New connection from {addr}")
    
    try:
        while True:
            data = client.recv(4096)
            if not data:
                logger.info(f"[MINER] {addr} disconnected")
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
                                [["mining.set_difficulty", "subscription_id_1"], ["mining.notify", "subscription_id_2"]],
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
                        response = {
                            "jsonrpc": "2.0",
                            "id": msg.get("id"),
                            "result": True
                        }
                        client.send((json.dumps(response) + "\n").encode())
                        logger.info(f"[MINER] Authorized as {worker_name}")
                    
                    # Handle mining.submit
                    elif "method" in msg and msg["method"] == "mining.submit":
                        # Forward to upstream
                        if upstream_socket:
                            try:
                                with upstream_lock:
                                    upstream_socket.send((line + "\n").encode())
                                logger.info(f"[MINER] Share submitted from {worker_name}")
                            except Exception as e:
                                logger.error(f"[MINER] Failed to submit share: {e}")
                        
                        # Send ACK
                        response = {
                            "jsonrpc": "2.0",
                            "id": msg.get("id"),
                            "result": True
                        }
                        client.send((json.dumps(response) + "\n").encode())
            
            except json.JSONDecodeError:
                logger.warning(f"[MINER] Invalid JSON from {addr}: {message}")
    
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
            
            # Handle each miner in a separate thread
            thread = threading.Thread(target=handle_miner, args=(client, addr), daemon=True)
            thread.start()
    
    except Exception as e:
        logger.error(f"[MINER SERVER] Error: {e}")
    
    finally:
        server.close()


def main():
    """
    Main entry point
    """
    logger.info("="*60)
    logger.info("Parasite Pool Proxy for LibreNode")
    logger.info(f"LibreNode RPC: http://{LIBRE_RPC_HOST}:{LIBRE_RPC_PORT}")
    logger.info(f"Parasite Pool: {PARASITE_HOST}:{PARASITE_PORT}")
    logger.info(f"Miner Listen: {MINER_LISTEN_HOST}:{MINER_LISTEN_PORT}")
    logger.info("="*60)
    
    # Start upstream connection thread
    upstream_thread = threading.Thread(target=connect_upstream, daemon=True)
    upstream_thread.start()
    time.sleep(2)  # Give it time to connect
    
    # Start upstream listener thread
    listen_thread = threading.Thread(target=listen_upstream, daemon=True)
    listen_thread.start()
    
    # Start miner server (blocking)
    listen_miners()


if __name__ == "__main__":
    main()
