"""
Argos Nanite - gestionare noduri live anuntate
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

class DiskInfo(BaseModel):
    name: str
    size_gb: float
    type: str = "unknown"   # ssd, hdd, nvme, usb
    model: str = ""
    rotational: bool = False

class NetworkInterface(BaseModel):
    name: str
    mac: str = ""
    speed: str = ""

class NaniteAnnounce(BaseModel):
    node_id: Optional[str] = None       # generat de nanite sau de server
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
    nanite_version: str = "1.0"
    build_id: str = ""
    extra: dict = {}

class InstallRequest(BaseModel):
    node_id: str
    profile: str                         # desktop, server, minimal
    hostname: str
    username: str
    locale: str = "en_US.UTF-8"
    timezone: str = "Europe/Paris"
    extra_packages: List[str] = []

# ── Helpers ───────────────────────────────────────────────────────────────────

def generate_node_id() -> str:
    chars = string.ascii_lowercase + string.digits
    suffix = ''.join(random.choices(chars, k=8))
    return f"nanite-{suffix}"


def ram_human(mb: int) -> str:
    if mb >= 1024:
        return f"{mb // 1024}GB"
    return f"{mb}MB"


def summarize_hardware(node: dict) -> str:
    parts = []
    if node.get("cpu_model"):
        cores = node.get("cpu_cores", 0)
        parts.append(f"{node['cpu_model']} ({cores}C)")
    if node.get("ram_mb"):
        parts.append(ram_human(node["ram_mb"]))
    disks = node.get("disks") or []
    if disks:
        total_gb = sum(d.get("size_gb", 0) for d in disks)
        parts.append(f"{len(disks)} disk(s) {total_gb:.0f}GB")
    if node.get("gpu"):
        parts.append(node["gpu"])
    return " · ".join(parts) if parts else "Hardware necunoscut"

# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/nanite/announce")
async def nanite_announce(data: NaniteAnnounce):
    """Nanite se anunta la Argos cu datele hardware"""
    from api.main import pool

    # Genereaza node_id daca nu e dat
    node_id = data.node_id or generate_node_id()

    async with pool.acquire() as conn:
        # Upsert — daca exista acelasi node_id sau IP, actualizeaza
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
                   last_seen=NOW(), status=CASE WHEN status='offline' THEN 'announced' ELSE status END
                   WHERE node_id=$17""",
                data.ip, data.hostname, data.arch, data.uefi,
                data.cpu_model, data.cpu_cores, data.cpu_threads, data.ram_mb,
                json.dumps(data.disks), data.gpu,
                json.dumps(data.network_interfaces),
                json.dumps(data.usb_devices), json.dumps(data.pci_devices),
                data.nanite_version, data.build_id, json.dumps(data.extra),
                node_id
            )
        else:
            await conn.execute(
                """INSERT INTO nanite_nodes
                   (node_id, ip, hostname, arch, uefi,
                    cpu_model, cpu_cores, cpu_threads, ram_mb,
                    disks, gpu, network_interfaces, usb_devices, pci_devices,
                    nanite_version, build_id, extra, status)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,'announced')""",
                node_id, data.ip, data.hostname, data.arch, data.uefi,
                data.cpu_model, data.cpu_cores, data.cpu_threads, data.ram_mb,
                json.dumps(data.disks), data.gpu,
                json.dumps(data.network_interfaces),
                json.dumps(data.usb_devices), json.dumps(data.pci_devices),
                data.nanite_version, data.build_id, json.dumps(data.extra)
            )

        # Salveaza si in memories pentru compatibilitate cu vm-list
        summary = summarize_hardware(data.dict())
        await conn.execute(
            """INSERT INTO memories (key, value, updated_at)
               VALUES ($1, $2, NOW())
               ON CONFLICT (key) DO UPDATE SET value=$2, updated_at=NOW()""",
            f"nanite_{data.ip}",
            f"node_id={node_id} ip={data.ip} hostname={data.hostname} hw={summary}"
        )

    print(f"[NANITE] Anuntat: {node_id} @ {data.ip} — {summary}")

    # Log entry pentru UI
    try:
        from api.archives import add_log_entry, LogEntryRequest
        from api.main import pool as p
        await add_log_entry(LogEntryRequest(
            type="ok",
            message=f"Nanite {node_id} @ {data.ip} — {summary}"
        ))
    except Exception as e:
        from api.debug import argos_error as _ae; import asyncio as _aio
        try: _aio.get_event_loop().run_until_complete(_ae("nanite", "ERR001", str(e)[:200], exc=e))
        except: pass
        pass

    return {
        "status": "ok",
        "node_id": node_id,
        "message": f"Bun venit, {node_id}"
    }


@router.get("/nanite/nodes")
async def list_nanite_nodes(status: str = None):
    """Lista noduri Nanite active"""
    from api.main import pool
    async with pool.acquire() as conn:
        query = "SELECT * FROM nanite_nodes"
        args = []
        if status:
            query += " WHERE status = $1"
            args.append(status)
        else:
            # Exclude noduri offline de mai mult de 30 minute
            query += " WHERE last_seen > NOW() - INTERVAL '30 minutes' OR status IN ('installing','installed')"
        query += " ORDER BY last_seen DESC"
        rows = await conn.fetch(query, *args)

    nodes = []
    for r in rows:
        node = dict(r)
        # Parse JSONB
        for field in ["disks", "network_interfaces", "usb_devices", "pci_devices", "extra"]:
            if node.get(field) and isinstance(node[field], str):
                node[field] = json.loads(node[field])
        # Timestamps to string
        for field in ["announced_at", "last_seen", "install_started_at", "install_finished_at"]:
            if node.get(field):
                node[field] = node[field].isoformat()
        node["hw_summary"] = summarize_hardware(node)
        nodes.append(node)

    return {"nodes": nodes}


@router.get("/nanite/nodes/{node_id}")
async def get_nanite_node(node_id: str):
    """Detalii complete nod Nanite"""
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
    """Actualizeaza statusul unui nod"""
    from api.main import pool
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE nanite_nodes SET status=$1, notes=$2, last_seen=NOW() WHERE node_id=$3",
            status, notes, node_id
        )
    return {"status": "ok"}


@router.get("/nanite/systems")
async def list_all_systems():
    """Lista combinata: system_profiles + nanite_nodes + vm-uri Proxmox"""
    from api.main import pool
    async with pool.acquire() as conn:
        # Known system profiles
        profiles = await conn.fetch(
            """SELECT id, name, display_name, os_type, ip, role, purpose,
                      online, last_seen, nanite_node_id
               FROM system_profiles WHERE active = TRUE ORDER BY name"""
        )
        # Nanite noduri active
        nanites = await conn.fetch(
            """SELECT node_id, ip, hostname, status, cpu_model, cpu_cores,
                      ram_mb, arch, last_seen
               FROM nanite_nodes
               WHERE last_seen > NOW() - INTERVAL '30 minutes' OR status IN ('installing','installed')
               ORDER BY last_seen DESC"""
        )

    systems = []

    for p in profiles:
        systems.append({
            "type": "known",
            "id": str(p["id"]),
            "name": p["name"],
            "display_name": p["display_name"],
            "ip": p["ip"],
            "os_type": p["os_type"],
            "role": p["role"],
            "online": p["online"],
            "last_seen": p["last_seen"].isoformat() if p["last_seen"] else None,
            "nanite_node_id": p["nanite_node_id"]
        })

    for n in nanites:
        systems.append({
            "type": "nanite",
            "id": n["node_id"],
            "name": n["node_id"],
            "display_name": n["hostname"] or n["node_id"],
            "ip": n["ip"],
            "os_type": "nanite",
            "role": "nanite",
            "status": n["status"],
            "cpu_model": n["cpu_model"],
            "cpu_cores": n["cpu_cores"],
            "ram_mb": n["ram_mb"],
            "last_seen": n["last_seen"].isoformat() if n["last_seen"] else None
        })

    return {"systems": systems}
