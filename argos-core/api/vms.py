import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter()

announced_vms = {}


class VMAnnounce(BaseModel):
    ip: str
    hostname: Optional[str] = "argos-agent"
    status: Optional[str] = "ready"
    proxmox: Optional[str] = None  # de pe ce proxmox vine


@router.post("/vm-announce")
async def vm_announce(req: VMAnnounce):
    from api.main import pool
    from api.executor import AGENT_VMS
    timestamp = datetime.now().isoformat()

    announced_vms[req.ip] = {
        "ip": req.ip,
        "hostname": req.hostname,
        "status": req.status,
        "proxmox": req.proxmox,
        "announced_at": timestamp
    }

    AGENT_VMS[req.ip] = {"host": req.ip, "user": "argos"}

    # Salvam in DB - persista si dupa restart
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO memories (key, value, updated_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()
                """,
                f"vm_{req.ip}",
                f"ip={req.ip} hostname={req.hostname} status={req.status} proxmox={req.proxmox or 'zeus'} time={timestamp}"
            )
    except Exception:
        pass

    print(f"[ARGOS] VM announced: {req.ip} ({req.hostname})")
    return {"status": "ok", "ip": req.ip}


class VMProgress(BaseModel):
    ip: str
    status: str  # "info", "ok", "error", "installing"
    message: str


@router.post("/vm-progress")
async def vm_progress(req: VMProgress):
    from api.main import pool
    timestamp = datetime.now().strftime("%H:%M:%S")
    msg = f"[{req.ip}] {req.message}"
    print(f"[VM:{req.ip}] {req.status}: {req.message}")

    # Salvam in memories ca sa apara in log
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO memories (key, value, updated_at)
                   VALUES ($1, $2, NOW())
                   ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()""",
                f"vm_progress_{req.ip}",
                f"[{timestamp}] {req.status}: {req.message}"
            )
    except Exception:
        pass

    return {"status": "ok"}


@router.get("/vm-progress/{ip}")
async def get_vm_progress(ip: str):
    from api.main import pool
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT value, updated_at FROM memories WHERE key LIKE $1 ORDER BY updated_at DESC LIMIT 20",
                f"vm_progress_{ip}%"
            )
        return {"progress": [dict(r) for r in rows]}
    except Exception:
        return {"progress": []}
@router.get("/vm-list")
async def vm_list():
    from api.main import pool
    # Merge in-memory cu ce e in DB (pentru dupa restart)
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT key, value, updated_at FROM memories WHERE key LIKE 'vm_%' ORDER BY updated_at DESC"
            )
            for r in rows:
                ip = r['key'].replace('vm_', '')
                if ip not in announced_vms:
                    # Reconstituim din DB
                    parts = dict(p.split('=', 1) for p in r['value'].split(' ') if '=' in p)
                    announced_vms[ip] = {
                        "ip": ip,
                        "hostname": parts.get('hostname', 'unknown'),
                        "status": parts.get('status', 'unknown'),
                        "proxmox": parts.get('proxmox', 'zeus'),
                        "announced_at": str(r['updated_at']),
                        "from_db": True
                    }
                    from api.executor import AGENT_VMS
                    AGENT_VMS[ip] = {"host": ip, "user": "argos"}
    except Exception:
        pass

    return {"vms": list(announced_vms.values())}


@router.delete("/vm/{ip}")
async def remove_vm(ip: str):
    from api.main import pool
    announced_vms.pop(ip, None)
    from api.executor import AGENT_VMS
    AGENT_VMS.pop(ip, None)
    try:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM memories WHERE key = $1", f"vm_{ip}")
    except Exception:
        pass
    return {"status": "ok"}
