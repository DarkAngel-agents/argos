#!/usr/bin/env python3
"""
Nanite Honeypot SMB - Port 445
Minimal SMB responder. Accepts connections, logs them, alerts ARGOS.
Does NOT announce via NetBIOS/broadcast. Purely passive.
Not a full SMB implementation - just enough to log who connects.
"""
import socket
import threading
import time
import json
import urllib.request
import os
import struct

PORT = 445
ARGOS_URL = os.getenv("ARGOS_URL", "")
NODE_ID = os.getenv("NANITE_NODE_ID", "unknown")
REACTION = os.getenv("NANITE_REACTION", "QUIET")

def alert_argos(src_ip, src_port, detail=""):
    if not ARGOS_URL:
        return
    try:
        data = json.dumps({
            "node_id": NODE_ID,
            "event": "honeypot_smb",
            "src_ip": src_ip,
            "src_port": src_port,
            "detail": detail[:200],
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

def smb_negotiate_response():
    """Minimal SMB negotiate response - enough to not crash clients"""
    # SMB2 negotiate response header (simplified)
    # Most scanners just check if port is open and get a banner
    resp = b"\x00\x00\x00\x45"  # NetBIOS length
    resp += b"\xfeSMB"  # SMB2 magic
    resp += b"\x40\x00"  # header size
    resp += b"\x00\x00"  # credit charge
    resp += b"\x00\x00\x00\x00"  # status OK
    resp += b"\x00\x00"  # negotiate command
    resp += b"\x01\x00"  # credit response
    resp += b"\x00\x00\x00\x00"  # flags
    resp += b"\x00\x00\x00\x00"  # next command
    resp += b"\x00\x00\x00\x00\x00\x00\x00\x00"  # message id
    resp += b"\x00\x00\x00\x00"  # reserved
    resp += b"\x00\x00\x00\x00"  # tree id
    resp += b"\x00\x00\x00\x00\x00\x00\x00\x00"  # session id
    resp += b"\x00" * 16  # signature
    return resp

def handle_client(conn, addr):
    src_ip, src_port = addr
    print(f"[HONEYPOT:SMB] Connection from {src_ip}:{src_port}", flush=True)

    detail = ""
    try:
        conn.settimeout(10)
        data = conn.recv(4096)
        if data:
            detail = f"received {len(data)} bytes"
            # Try to send minimal SMB response
            try:
                conn.sendall(smb_negotiate_response())
            except:
                pass
            # Read more (capture what client sends)
            try:
                more = conn.recv(4096)
                if more:
                    detail += f", then {len(more)} more bytes"
            except:
                pass
    except:
        pass
    finally:
        conn.close()

    alert_argos(src_ip, src_port, detail)

    if REACTION == "PANIC":
        print("[HONEYPOT:SMB] PANIC triggered!", flush=True)
        os.system("/etc/nanite/playbooks/self/panic.sh &")
    elif REACTION == "DEFENSIVE":
        print("[HONEYPOT:SMB] DEFENSIVE: rotating identity...", flush=True)
        os.system("/etc/nanite/playbooks/boot/02-masquerade.sh &")

def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", PORT))
    srv.listen(5)
    print(f"[HONEYPOT:SMB] Listening on port {PORT} (fake Samba)", flush=True)

    while True:
        conn, addr = srv.accept()
        t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        t.start()

if __name__ == "__main__":
    main()
