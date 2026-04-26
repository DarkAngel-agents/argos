"""
ARGOS Nanite v2 - node management with Tailscale mesh
Endpoints:
  POST /nanite/announce       - nanite announces hardware + tailscale IP
  POST /nanite/heartbeat      - nanite reports alive + metrics
  GET  /nanite/commands/{id}  - nanite polls for pending commands
  POST /nanite/command-result - nanite reports command result
  GET  /nanite/config/{id}    - nanite gets bootstrap config
  GET  /nanite/nodes          - list active nanite nodes
  GET  /nanite/nodes/{id}     - detail one node
  POST /nanite/nodes/{id}/cmd - ARGOS queues command for nanite
  POST /nanite/nodes/{id}/status - update status
  GET  /nanite/systems        - combined system_profiles + nanite_nodes
"""
import os
import json
import random
import string
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta

router = APIRouter()

# ── Models ────────────────────────────────────────────────────────────────────

class NaniteAnnounce(BaseModel):
    node_id: Optional[str] = None
    ip: str
    hostname: str = ""
    arch: str = "x86_64"
    uefi: bool = True
    cpu_model: str = ""
    cpu_cores: int = 0
    cpu_threads: int = 0
    ram_mb: int = 0
    disks: List[dict] = []
    gpu: str = ""
    network_interfaces: List[dict] = []
    usb_devices: List[dict] = []
    pci_devices: List[dict] = []
    nanite_version: str = "2.0"
    build_id: str = ""
    tailscale_ip: str = ""
    tailscale_name: str = ""
    extra: dict = {}

class NaniteHeartbeat(BaseModel):
    node_id: str
    cpu_pct: float = -1
    mem_pct: float = -1
    disk_pct: float = -1
    uptime_s: int = 0
    tailscale_ip: str = ""
    status: str = "online"

class NaniteCommandRequest(BaseModel):
    command: str
    timeout: int = 120

class NaniteCommandResult(BaseModel):
    node_id: str
    command_id: int
    returncode: int
    stdout: str = ""
    stderr: str = ""

# ── Helpers ───────────────────────────────────────────────────────────────────

def generate_node_id():
    chars = string.ascii_lowercase + string.digits
    return "nanite-" + "".join(random.choices(chars, k=8))

def ram_human(mb):
    if mb >= 1024:
        return str(mb // 1024) + "GB"
    return str(mb) + "MB"

def summarize_hardware(node):
    parts = []
    cpu = node.get("cpu_model") or ""
    if cpu:
        cores = node.get("cpu_cores", 0)
        parts.append(cpu + " (" + str(cores) + "C)")
    rmb = node.get("ram_mb", 0)
    if rmb:
        parts.append(ram_human(rmb))
    disks = node.get("disks") or []
    if disks:
        total = sum(d.get("size_gb", 0) for d in disks)
        parts.append(str(len(disks)) + " disk(s) " + str(int(total)) + "GB")
    gpu = node.get("gpu") or ""
    if gpu:
        parts.append(gpu)
    return " · ".join(parts) if parts else "Hardware necunoscut"

# ── Announce ──────────────────────────────────────────────────────────────────

@router.post("/nanite/announce")
async def nanite_announce(data: NaniteAnnounce):
    from api.main import pool

    node_id = data.node_id or generate_node_id()

    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id, node_id FROM nanite_nodes WHERE node_id = $1 OR ip = $2",
            node_id, data.ip
        )

        if existing:
            node_id = existing["node_id"]
            await conn.execute(
                """UPDATE nanite_nodes SET
                   ip=$1, hostname=$2, arch=$3, uefi=$4,
                   cpu_model=$5, cpu_cores=$6, cpu_threads=$7, ram_mb=$8,
                   disks=$9, gpu=$10, network_interfaces=$11,
                   usb_devices=$12, pci_devices=$13,
                   nanite_version=$14, build_id=$15, extra=$16,
                   tailscale_ip=$17, tailscale_name=$18,
                   last_seen=NOW(),
                   status=CASE WHEN status='offline' THEN 'announced' ELSE status END
                   WHERE node_id=$19""",
                data.ip, data.hostname, data.arch, data.uefi,
                data.cpu_model, data.cpu_cores, data.cpu_threads, data.ram_mb,
                json.dumps(data.disks), data.gpu,
                json.dumps(data.network_interfaces),
                json.dumps(data.usb_devices), json.dumps(data.pci_devices),
                data.nanite_version, data.build_id, json.dumps(data.extra),
                data.tailscale_ip, data.tailscale_name,
                node_id
            )
        else:
            await conn.execute(
                """INSERT INTO nanite_nodes
                   (node_id, ip, hostname, arch, uefi,
                    cpu_model, cpu_cores, cpu_threads, ram_mb,
                    disks, gpu, network_interfaces, usb_devices, pci_devices,
                    nanite_version, build_id, extra, tailscale_ip, tailscale_name, status)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,'announced')""",
                node_id, data.ip, data.hostname, data.arch, data.uefi,
                data.cpu_model, data.cpu_cores, data.cpu_threads, data.ram_mb,
                json.dumps(data.disks), data.gpu,
                json.dumps(data.network_interfaces),
                json.dumps(data.usb_devices), json.dumps(data.pci_devices),
                data.nanite_version, data.build_id, json.dumps(data.extra),
                data.tailscale_ip, data.tailscale_name
            )

    summary = summarize_hardware(data.dict())
    print(f"[NANITE] Anuntat: {node_id} @ {data.ip} ts:{data.tailscale_ip} — {summary}", flush=True)

    return {
        "status": "ok",
        "node_id": node_id,
        "message": "Bun venit, " + node_id
    }

# ── Heartbeat ─────────────────────────────────────────────────────────────────

@router.post("/nanite/heartbeat")
async def nanite_heartbeat(data: NaniteHeartbeat):
    from api.main import pool

    async with pool.acquire() as conn:
        result = await conn.execute(
            """UPDATE nanite_nodes SET
               last_seen = NOW(),
               status = $1,
               tailscale_ip = CASE WHEN $2 != '' THEN $2 ELSE tailscale_ip END
               WHERE node_id = $3""",
            data.status, data.tailscale_ip, data.node_id
        )

        if "UPDATE 0" in result:
            raise HTTPException(status_code=404, detail="Unknown node_id: " + data.node_id)

        # Store metrics in heartbeat_log for consistency with fleet health
        await conn.execute(
            """INSERT INTO heartbeat_log
               (node, service, status, cpu_pct, mem_pct, db_latency_ms, containers_up)
               VALUES ($1, 'nanite', $2, $3, $4, -1, -1)""",
            data.node_id, "ok" if data.status == "online" else data.status,
            data.cpu_pct, data.mem_pct
        )

    return {"status": "ok", "node_id": data.node_id}

# ── Config bootstrap ─────────────────────────────────────────────────────────

@router.get("/nanite/config/{node_id}")
async def nanite_config(node_id: str):
    """Nanite gets bootstrap config from ARGOS (tailscale key, argos URL, etc)"""
    from api.main import pool

    async with pool.acquire() as conn:
        node = await conn.fetchrow(
            "SELECT id, node_id, status FROM nanite_nodes WHERE node_id = $1", node_id
        )
        if not node:
            raise HTTPException(status_code=404, detail="Unknown node_id")

        ts_key = await conn.fetchval(
            "SELECT value FROM settings WHERE key = 'tailscale_auth_key'"
        ) or ""
        ts_net = await conn.fetchval(
            "SELECT value FROM settings WHERE key = 'tailscale_tailnet'"
        ) or ""

    return {
        "node_id": node_id,
        "tailscale_auth_key": ts_key,
        "tailscale_tailnet": ts_net,
        "argos_url": os.getenv("ARGOS_URL", "http://localhost:666"),
        "heartbeat_interval": 30,
        "nanite_listen_port": 8666,
    }

# ── Command queue ─────────────────────────────────────────────────────────────

@router.post("/nanite/nodes/{node_id}/cmd")
async def send_command_to_nanite(node_id: str, req: NaniteCommandRequest):
    """ARGOS queues a command for nanite to execute"""
    from api.main import pool

    async with pool.acquire() as conn:
        node = await conn.fetchrow(
            "SELECT id FROM nanite_nodes WHERE node_id = $1", node_id
        )
        if not node:
            raise HTTPException(status_code=404, detail="Unknown node_id")

        cmd_id = await conn.fetchval(
            """INSERT INTO nanite_commands
               (node_id, command, timeout, status, created_at)
               VALUES ($1, $2, $3, 'pending', NOW()) RETURNING id""",
            node_id, req.command, req.timeout
        )

    return {"command_id": cmd_id, "status": "pending", "node_id": node_id}

@router.get("/nanite/commands/{node_id}")
async def get_pending_commands(node_id: str):
    """Nanite polls for pending commands"""
    from api.main import pool

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, command, timeout FROM nanite_commands
               WHERE node_id = $1 AND status = 'pending'
               ORDER BY created_at ASC""",
            node_id
        )
        # Mark as sent
        for r in rows:
            await conn.execute(
                "UPDATE nanite_commands SET status = 'sent', sent_at = NOW() WHERE id = $1",
                r["id"]
            )

    return {
        "commands": [
            {"id": r["id"], "command": r["command"], "timeout": r["timeout"]}
            for r in rows
        ]
    }

@router.post("/nanite/command-result")
async def report_command_result(data: NaniteCommandResult):
    """Nanite reports result of executed command"""
    from api.main import pool

    async with pool.acquire() as conn:
        cmd = await conn.fetchrow(
            "SELECT id FROM nanite_commands WHERE id = $1 AND node_id = $2",
            data.command_id, data.node_id
        )
        if not cmd:
            raise HTTPException(status_code=404, detail="Unknown command")

        status = "ok" if data.returncode == 0 else "failed"
        await conn.execute(
            """UPDATE nanite_commands SET
               status = $1, returncode = $2, stdout = $3, stderr = $4, finished_at = NOW()
               WHERE id = $5""",
            status, data.returncode, data.stdout[:10000], data.stderr[:5000],
            data.command_id
        )

    return {"status": status, "command_id": data.command_id}

# ── Node CRUD ─────────────────────────────────────────────────────────────────

@router.get("/nanite/nodes")
async def list_nanite_nodes(status: str = None):
    from api.main import pool
    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                "SELECT * FROM nanite_nodes WHERE status = $1 ORDER BY last_seen DESC",
                status
            )
        else:
            rows = await conn.fetch(
                """SELECT * FROM nanite_nodes
                   WHERE last_seen > NOW() - INTERVAL '30 minutes'
                   OR status IN ('installing','installed','announced')
                   ORDER BY last_seen DESC"""
            )

    nodes = []
    for r in rows:
        node = dict(r)
        for field in ["disks", "network_interfaces", "usb_devices", "pci_devices", "extra"]:
            if node.get(field) and isinstance(node[field], str):
                node[field] = json.loads(node[field])
        for field in ["announced_at", "last_seen", "install_started_at", "install_finished_at"]:
            if node.get(field):
                node[field] = node[field].isoformat()
        node["hw_summary"] = summarize_hardware(node)
        nodes.append(node)

    return {"nodes": nodes}

@router.get("/nanite/nodes/{node_id}")
async def get_nanite_node(node_id: str):
    from api.main import pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM nanite_nodes WHERE node_id = $1", node_id
        )
    if not row:
        raise HTTPException(status_code=404, detail="Nod negasit")
    node = dict(row)
    for field in ["disks", "network_interfaces", "usb_devices", "pci_devices", "extra"]:
        if node.get(field) and isinstance(node[field], str):
            node[field] = json.loads(node[field])
    for field in ["announced_at", "last_seen", "install_started_at", "install_finished_at"]:
        if node.get(field):
            node[field] = node[field].isoformat()
    node["hw_summary"] = summarize_hardware(node)
    return node

@router.post("/nanite/nodes/{node_id}/status")
async def update_nanite_status(node_id: str, status: str, notes: str = ""):
    from api.main import pool
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE nanite_nodes SET status=$1, notes=$2, last_seen=NOW() WHERE node_id=$3",
            status, notes, node_id
        )
    return {"status": "ok"}

@router.delete("/nanite/nodes/{node_id}")
async def decommission_nanite(node_id: str):
    """Remove nanite from fleet"""
    from api.main import pool
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM nanite_commands WHERE node_id = $1", node_id)
        await conn.execute("DELETE FROM nanite_nodes WHERE node_id = $1", node_id)
    return {"status": "ok", "decommissioned": node_id}

# ── Combined systems list ─────────────────────────────────────────────────────

@router.get("/nanite/systems")
async def list_all_systems():
    from api.main import pool
    async with pool.acquire() as conn:
        profiles = await conn.fetch(
            """SELECT id, name, display_name, os_type, ip, role, purpose,
                      online, last_seen, nanite_node_id
               FROM system_profiles WHERE active = TRUE ORDER BY name"""
        )
        nanites = await conn.fetch(
            """SELECT node_id, ip, hostname, status, cpu_model, cpu_cores,
                      ram_mb, arch, last_seen, tailscale_ip
               FROM nanite_nodes
               WHERE last_seen > NOW() - INTERVAL '30 minutes'
               OR status IN ('installing','installed')
               ORDER BY last_seen DESC"""
        )

    systems = []
    for p in profiles:
        systems.append({
            "type": "known", "id": str(p["id"]),
            "name": p["name"], "display_name": p["display_name"],
            "ip": p["ip"], "os_type": p["os_type"],
            "role": p["role"], "online": p["online"],
            "last_seen": p["last_seen"].isoformat() if p["last_seen"] else None,
        })
    for n in nanites:
        systems.append({
            "type": "nanite", "id": n["node_id"],
            "name": n["node_id"], "display_name": n["hostname"] or n["node_id"],
            "ip": n["tailscale_ip"] or n["ip"], "os_type": "nanite",
            "role": "nanite", "status": n["status"],
            "last_seen": n["last_seen"].isoformat() if n["last_seen"] else None,
        })

    return {"systems": systems}
