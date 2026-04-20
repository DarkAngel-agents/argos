"""
ARGOS fleet - unified fleet listing.
Pas 3.1 - merge system_profiles (known) + nanite_nodes (announced/installing/installed).
TODO iteration 2: include /api/vm-list (Proxmox) when API connected.
"""
from fastapi import APIRouter
from typing import Optional


router = APIRouter()


@router.delete("/fleet/known/{system_id}")
async def delete_known_system(system_id: int):
    from api.main import pool
    async with pool.acquire() as conn:
        await conn.execute("UPDATE system_profiles SET active = FALSE WHERE id = $1", system_id)
    return {"status": "ok", "deactivated": system_id}


@router.delete("/fleet/nanite/{node_id}")
async def delete_nanite_from_fleet(node_id: str):
    from api.main import pool
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM nanite_commands WHERE node_id = $1", node_id)
        await conn.execute("DELETE FROM nanite_nodes WHERE node_id = $1", node_id)
    return {"status": "ok", "deleted": node_id}


@router.delete("/fleet/known/{system_id}")
async def delete_known_system(system_id: int):
    from api.main import pool
    async with pool.acquire() as conn:
        await conn.execute("UPDATE system_profiles SET active = FALSE WHERE id = $1", system_id)
    return {"status": "ok", "deactivated": system_id}


@router.delete("/fleet/nanite/{node_id}")
async def delete_nanite_from_fleet(node_id: str):
    from api.main import pool
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM nanite_commands WHERE node_id = $1", node_id)
        await conn.execute("DELETE FROM nanite_nodes WHERE node_id = $1", node_id)
    return {"status": "ok", "deleted": node_id}


@router.get("/fleet")
async def list_fleet(include_inactive: bool = False):
    from api.main import pool

    async with pool.acquire() as conn:
        # === KNOWN systems (system_profiles) ===
        where = "" if include_inactive else "WHERE active = TRUE"
        known_rows = await conn.fetch(
            f"""SELECT id, name, display_name, ip, os_type, os_version,
                       hostname, cpu, ram_gb, storage, gpu, location, role,
                       purpose, online, last_seen, nanite_node_id, active
                FROM system_profiles
                {where}
                ORDER BY name"""
        )

        # === NANITE nodes ===
        nanite_rows = await conn.fetch(
            """SELECT id, node_id, ip, status, hostname, cpu_model, cpu_cores,
                      cpu_threads, ram_mb, gpu, arch, uefi, nanite_version,
                      announced_at, last_seen, install_started_at,
                      install_finished_at, install_profile, installed_system_id
               FROM nanite_nodes
               ORDER BY announced_at DESC NULLS LAST"""
        )

    # === Normalize KNOWN systems ===
    known = []
    for r in known_rows:
        ram = f"{r['ram_gb']}GB" if r['ram_gb'] else None
        hw_parts = [p for p in [r['cpu'], ram, r['gpu']] if p]
        known.append({
            "type": "known",
            "id": f"known-{r['id']}",
            "raw_id": r['id'],
            "name": r['name'],
            "display_name": r['display_name'] or r['name'],
            "ip": r['ip'],
            "os_type": r['os_type'],
            "os_version": r['os_version'],
            "role": r['role'],
            "purpose": r['purpose'],
            "location": r['location'],
            "status": "online" if r['online'] else "offline",
            "online": r['online'],
            "last_seen": r['last_seen'].isoformat() if r['last_seen'] else None,
            "hw_summary": " · ".join(hw_parts) if hw_parts else None,
            "active": r['active'],
            "linked_nanite": r['nanite_node_id'],
        })

    # === Normalize NANITE nodes ===
    nanite = []
    for r in nanite_rows:
        ram_gb = round(r['ram_mb'] / 1024, 1) if r['ram_mb'] else None
        hw_parts = []
        if r['cpu_model']:
            hw_parts.append(r['cpu_model'])
        if ram_gb:
            hw_parts.append(f"{ram_gb}GB")
        if r['gpu']:
            hw_parts.append(r['gpu'])

        # Status normalization
        raw_status = (r['status'] or "unknown").lower()
        if raw_status in ("announced", "installing", "installed", "online", "offline"):
            status = raw_status
        else:
            status = "unknown"

        nanite.append({
            "type": "nanite",
            "id": f"nanite-{r['node_id']}",
            "raw_id": r['id'],
            "node_id": r['node_id'],
            "name": r['hostname'] or r['node_id'],
            "display_name": r['hostname'] or r['node_id'],
            "ip": r['ip'],
            "os_type": "linux",
            "arch": r['arch'],
            "uefi": r['uefi'],
            "nanite_version": r['nanite_version'],
            "status": status,
            "online": status == "online",
            "announced_at": r['announced_at'].isoformat() if r['announced_at'] else None,
            "last_seen": r['last_seen'].isoformat() if r['last_seen'] else None,
            "install_started_at": r['install_started_at'].isoformat() if r['install_started_at'] else None,
            "install_finished_at": r['install_finished_at'].isoformat() if r['install_finished_at'] else None,
            "install_profile": r['install_profile'],
            "installed_system_id": r['installed_system_id'],
            "hw_summary": " · ".join(hw_parts) if hw_parts else None,
        })

    # Combined list, nanite-announced/installing first, then known online, then known offline
    def sort_key(item):
        s = item.get("status", "unknown")
        order = {"announced": 0, "installing": 1, "online": 2, "installed": 3,
                 "offline": 4, "unknown": 5}
        return (order.get(s, 99), item.get("name") or "")

    combined = sorted(known + nanite, key=sort_key)

    return {
        "fleet": combined,
        "counts": {
            "total": len(combined),
            "known": len(known),
            "nanite": len(nanite),
            "online": sum(1 for x in combined if x.get("online")),
            "announced": sum(1 for x in combined if x.get("status") == "announced"),
            "installing": sum(1 for x in combined if x.get("status") == "installing"),
            "offline": sum(1 for x in combined if x.get("status") == "offline"),
        },
        "sources": {
            "system_profiles": len(known),
            "nanite_nodes": len(nanite),
            "vm_list": "TODO iter2 - Proxmox API not connected",
        },
    }
