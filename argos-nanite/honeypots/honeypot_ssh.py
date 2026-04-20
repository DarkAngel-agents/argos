#!/usr/bin/env python3
"""
Nanite Honeypot SSH - Port 22
Fake OpenSSH banner (Debian 12). Logs + alerts ARGOS on any connection.
Real SSH runs only via Tailscale or port 2222.
"""
import socket
import threading
import time
import json
import urllib.request
import os

PORT = 22
BANNER = b"SSH-2.0-OpenSSH_9.2p1 Debian-2+deb12u3\r\n"
ARGOS_URL = os.getenv("ARGOS_URL", "")
NODE_ID = os.getenv("NANITE_NODE_ID", "unknown")
REACTION = os.getenv("NANITE_REACTION", "QUIET")  # QUIET, DEFENSIVE, PANIC

def alert_argos(src_ip, src_port):
    if not ARGOS_URL:
        return
    try:
        data = json.dumps({
            "node_id": NODE_ID,
            "event": "honeypot_ssh",
            "src_ip": src_ip,
            "src_port": src_port,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "reaction": REACTION,
        }).encode()
        req = urllib.request.Request(
            ARGOS_URL.rstrip("/") + "/api/nanite/heartbeat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=5)
    except:
        pass

def handle_client(conn, addr):
    src_ip, src_port = addr
    print(f"[HONEYPOT:SSH] Connection from {src_ip}:{src_port}", flush=True)
    alert_argos(src_ip, src_port)

    try:
        conn.sendall(BANNER)
        # Read client banner (max 1KB, 5s timeout)
        conn.settimeout(5)
        try:
            client_banner = conn.recv(1024)
            print(f"[HONEYPOT:SSH] Client banner: {client_banner[:100]}", flush=True)
        except:
            pass
        # Hang for a bit then close (waste attacker time)
        time.sleep(3)
    except:
        pass
    finally:
        conn.close()

    # React based on level
    if REACTION == "PANIC":
        print("[HONEYPOT:SSH] PANIC triggered!", flush=True)
        os.system("/etc/nanite/playbooks/self/panic.sh &")
    elif REACTION == "DEFENSIVE":
        print("[HONEYPOT:SSH] DEFENSIVE: rotating MAC...", flush=True)
        os.system("/etc/nanite/playbooks/boot/02-masquerade.sh &")

def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", PORT))
    srv.listen(5)
    print(f"[HONEYPOT:SSH] Listening on port {PORT} (fake Debian SSH)", flush=True)

    while True:
        conn, addr = srv.accept()
        t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        t.start()

if __name__ == "__main__":
    main()
