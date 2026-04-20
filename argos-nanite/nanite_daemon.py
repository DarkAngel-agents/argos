#!/usr/bin/env python3
"""
ARGOS Nanite Daemon v2
Runs on nanite ISO. Connects to ARGOS via Tailscale mesh.
Flow: tailscale up -> announce -> heartbeat loop -> command poll
"""
import os
import sys
import json
import time
import socket
import subprocess
import urllib.request
import urllib.error

# ── Config ────────────────────────────────────────────────────────────────────

ARGOS_URL = os.getenv("ARGOS_URL", "")
NODE_ID = os.getenv("NANITE_NODE_ID", "")
HEARTBEAT_INTERVAL = 30
COMMAND_POLL_INTERVAL = 5
VERSION = "2.0"

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg):
    print(f"[NANITE] {msg}", flush=True)

def api(method, path, data=None):
    url = ARGOS_URL.rstrip("/") + path
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        log(f"API error {e.code}: {e.read().decode()[:200]}")
        return None
    except Exception as e:
        log(f"API unreachable: {e}")
        return None

def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", "timeout", -1
    except Exception as e:
        return "", str(e), -1

# ── Hardware detection ────────────────────────────────────────────────────────

def detect_hardware():
    hw = {
        "hostname": socket.gethostname(),
        "arch": os.uname().machine,
        "uefi": os.path.isdir("/sys/firmware/efi"),
    }

    # CPU
    try:
        with open("/proc/cpuinfo") as f:
            lines = f.readlines()
        for l in lines:
            if l.startswith("model name"):
                hw["cpu_model"] = l.split(":")[1].strip()
                break
        hw["cpu_cores"] = len([l for l in lines if l.startswith("processor")])
        hw["cpu_threads"] = hw["cpu_cores"]
    except:
        pass

    # RAM
    try:
        with open("/proc/meminfo") as f:
            for l in f:
                if l.startswith("MemTotal"):
                    kb = int(l.split()[1])
                    hw["ram_mb"] = kb // 1024
                    break
    except:
        pass

    # Disks
    try:
        out, _, _ = run("lsblk -J -b -o NAME,SIZE,TYPE,MODEL,ROTA 2>/dev/null")
        if out:
            data = json.loads(out)
            disks = []
            for d in data.get("blockdevices", []):
                if d.get("type") == "disk":
                    disks.append({
                        "name": d["name"],
                        "size_gb": round(int(d.get("size", 0)) / 1e9, 1),
                        "model": d.get("model", ""),
                        "rotational": d.get("rota", False),
                    })
            hw["disks"] = disks
    except:
        pass

    # GPU
    try:
        out, _, _ = run("lspci 2>/dev/null | grep -i 'vga\\|3d\\|display'")
        if out:
            hw["gpu"] = out.split(": ")[-1].strip()[:200]
    except:
        pass

    # Network interfaces
    try:
        out, _, _ = run("ip -j link show 2>/dev/null")
        if out:
            ifaces = json.loads(out)
            hw["network_interfaces"] = [
                {"name": i["ifname"], "mac": i.get("address", "")}
                for i in ifaces if i["ifname"] != "lo"
            ]
    except:
        pass

    return hw

# ── Tailscale ─────────────────────────────────────────────────────────────────

def tailscale_up(auth_key):
    """Connect to tailnet with pre-auth key"""
    if not auth_key:
        log("No tailscale auth key, skip tailscale")
        return ""

    log("Tailscale: connecting...")
    _, err, rc = run(f"tailscale up --authkey={auth_key} --hostname={NODE_ID}", timeout=30)
    if rc != 0:
        log(f"Tailscale up failed: {err}")
        return ""

    # Get tailscale IP
    out, _, rc = run("tailscale ip -4", timeout=5)
    if rc == 0 and out:
        log(f"Tailscale: connected as {out}")
        return out.strip()
    return ""

def get_tailscale_ip():
    out, _, rc = run("tailscale ip -4 2>/dev/null", timeout=5)
    if rc == 0 and out:
        return out.strip()
    return ""

# ── CPU/Mem metrics ───────────────────────────────────────────────────────────

def get_cpu():
    try:
        with open("/proc/stat") as f:
            line = f.readline()
        vals = [int(x) for x in line.split()[1:]]
        idle, total = vals[3], sum(vals)
        if not hasattr(get_cpu, "_prev"):
            get_cpu._prev = (idle, total)
            return 0.0
        pi, pt = get_cpu._prev
        get_cpu._prev = (idle, total)
        di, dt = idle - pi, total - pt
        return round(100.0 * (1.0 - di / dt), 1) if dt > 0 else 0.0
    except:
        return -1

def get_mem():
    try:
        with open("/proc/meminfo") as f:
            info = {}
            for l in f:
                parts = l.split()
                info[parts[0].rstrip(":")] = int(parts[1])
        total = info.get("MemTotal", 1)
        avail = info.get("MemAvailable", total)
        return round(100.0 * (1.0 - avail / total), 1)
    except:
        return -1

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    global ARGOS_URL, NODE_ID

    # Generate node_id if not set
    if not NODE_ID:
        NODE_ID = "nanite-" + socket.gethostname().lower()[:12]

    log(f"Starting nanite daemon {VERSION} as {NODE_ID}")

    # Try to get config from ARGOS (if URL known)
    ts_ip = ""
    if ARGOS_URL:
        config = api("GET", f"/api/nanite/config/{NODE_ID}")
        if config and config.get("tailscale_auth_key"):
            ts_ip = tailscale_up(config["tailscale_auth_key"])
    else:
        # Try tailscale first, then discover ARGOS
        ts_ip = get_tailscale_ip()
        log(f"Tailscale IP: {ts_ip or 'not connected'}")

    if not ARGOS_URL:
        log("ERROR: ARGOS_URL not set. Set env ARGOS_URL or configure tailscale.")
        sys.exit(1)

    # Detect hardware
    hw = detect_hardware()
    hw["tailscale_ip"] = ts_ip
    hw["tailscale_name"] = NODE_ID
    hw["nanite_version"] = VERSION
    hw["node_id"] = NODE_ID
    hw["ip"] = ts_ip or hw.get("ip", "0.0.0.0")

    # Get local IP if no tailscale
    if not hw["ip"] or hw["ip"] == "0.0.0.0":
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            hw["ip"] = s.getsockname()[0]
            s.close()
        except:
            pass

    # Announce
    log(f"Announcing to {ARGOS_URL}...")
    result = api("POST", "/api/nanite/announce", hw)
    if result:
        NODE_ID = result.get("node_id", NODE_ID)
        log(f"Announced OK as {NODE_ID}")
    else:
        log("Announce failed, will retry in heartbeat loop")

    # Main loop: heartbeat + command poll
    last_heartbeat = 0
    last_cmd_poll = 0

    while True:
        now = time.time()

        # Heartbeat
        if now - last_heartbeat >= HEARTBEAT_INTERVAL:
            hb = {
                "node_id": NODE_ID,
                "cpu_pct": get_cpu(),
                "mem_pct": get_mem(),
                "tailscale_ip": get_tailscale_ip() or ts_ip,
                "status": "online",
            }
            result = api("POST", "/api/nanite/heartbeat", hb)
            if result:
                last_heartbeat = now
            else:
                log("Heartbeat failed, retry next cycle")

        # Command poll
        if now - last_cmd_poll >= COMMAND_POLL_INTERVAL:
            cmds = api("GET", f"/api/nanite/commands/{NODE_ID}")
            if cmds and cmds.get("commands"):
                for cmd in cmds["commands"]:
                    log(f"Executing command #{cmd['id']}: {cmd['command'][:80]}")
                    stdout, stderr, rc = run(cmd["command"], timeout=cmd.get("timeout", 120))
                    api("POST", "/api/nanite/command-result", {
                        "node_id": NODE_ID,
                        "command_id": cmd["id"],
                        "returncode": rc,
                        "stdout": stdout[:10000],
                        "stderr": stderr[:5000],
                    })
                    log(f"Command #{cmd['id']} done: rc={rc}")
            last_cmd_poll = now

        time.sleep(2)

if __name__ == "__main__":
    main()
