"""
Backup și rollback pentru fișiere critice.
3 versiuni: lts (marcată manual), previous, current.
Rollback automat dacă serviciul cade după modificare.
"""
import hashlib
import asyncio
import asyncssh
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from api.ssh_util import known_hosts as _ssh_known_hosts

router = APIRouter()

SSH_KEY = os.path.expanduser("~/.ssh/id_ed25519")

# Fișiere monitorizate automat
WATCHED_FILES = {
    "api/chat.py":       "/home/darkangel/.argos/argos-core/api/chat.py",
    "api/executor.py":   "/home/darkangel/.argos/argos-core/api/executor.py",
    "api/main.py":       "/home/darkangel/.argos/argos-core/api/main.py",
    "api/vms.py":        "/home/darkangel/.argos/argos-core/api/vms.py",
    "api/jobs.py":       "/home/darkangel/.argos/argos-core/api/jobs.py",
    "api/backup.py":     "/home/darkangel/.argos/argos-core/api/backup.py",
    "api/compress.py":   "/home/darkangel/.argos/argos-core/api/compress.py",
    "api/local_executor.py": "/home/darkangel/.argos/argos-core/api/local_executor.py",
    "ui/index.html":     "/home/darkangel/.argos/argos-core/ui/index.html",
    "config/system_prompt.txt": "/home/darkangel/.argos/argos-core/config/system_prompt.txt",
    "api/iso_builder.py":    "/home/darkangel/.argos/argos-core/api/iso_builder.py",
    "api/nanite.py":         "/home/darkangel/.argos/argos-core/api/nanite.py",
    "api/archives.py":       "/home/darkangel/.argos/argos-core/api/archives.py",
    "api/code_runner.py":       "/home/darkangel/.argos/argos-core/api/code_runner.py",
}

# Servicii de verificat dupa modificare
SERVICE_CHECKS = {
    "default": ("beasty", "systemctl is-active argos"),
}


class MarkLTSRequest(BaseModel):
    module_name: str


class RollbackRequest(BaseModel):
    module_name: str
    version_type: str  # lts, previous


async def _read_file_local(path: str) -> bytes:
    """Citeste un fisier local (Argos ruleaza pe Beasty)"""
    try:
        with open(path, "rb") as f:
            return f.read()
    except Exception as e:
        from api.debug import argos_error as _ae; import asyncio as _aio
        try: _aio.get_event_loop().run_until_complete(_ae("backup", "ERR001", str(e)[:200], exc=e))
        except: pass
        raise Exception(f"Nu pot citi {path}: {e}")


async def _write_file_local(path: str, content: bytes):
    """Scrie un fisier local cu sudo daca e nevoie"""
    import subprocess
    try:
        # Incearca direct
        with open(path, "wb") as f:
            f.write(content)
    except PermissionError:
        # Foloseste sudo tee
        proc = subprocess.run(
            ["sudo", "tee", path],
            input=content,
            capture_output=True
        )
        if proc.returncode != 0:
            raise Exception(f"Scriere esuata: {proc.stderr.decode()}")


async def backup_file(pool, module_name: str, created_by: str = "argos"):
    """
    Backup fisier inainte de modificare.
    Roteste versiunile: current -> previous, noua -> current.
    LTS ramane neatins.
    """
    if module_name not in WATCHED_FILES:
        return False

    file_path = WATCHED_FILES[module_name]

    try:
        content = await _read_file_local(file_path)
        file_hash = hashlib.sha256(content).hexdigest()

        async with pool.acquire() as conn:
            # Verifica daca exista deja acelasi hash ca current (fara modificare reala)
            existing = await conn.fetchval(
                "SELECT hash FROM file_versions WHERE module_name = $1 AND version_type = 'current'",
                module_name
            )
            if existing == file_hash:
                return True  # Nimic de schimbat

            # current -> previous
            await conn.execute(
                """UPDATE file_versions SET version_type = 'previous'
                   WHERE module_name = $1 AND version_type = 'current'""",
                module_name
            )

            # Sterge previous vechi (pastreaza doar unul)
            await conn.execute(
                """DELETE FROM file_versions WHERE id IN (
                   SELECT id FROM file_versions
                   WHERE module_name = $1 AND version_type = 'previous'
                   ORDER BY created_at DESC OFFSET 1)""",
                module_name
            )

            # Salveaza noua versiune current
            await conn.execute(
                """INSERT INTO file_versions (module_name, version_type, content, file_path, hash, created_by)
                   VALUES ($1, 'current', $2, $3, $4, $5)""",
                module_name, content, file_path, file_hash, created_by
            )

        return True
    except Exception as e:
        from api.debug import argos_error as _ae; import asyncio as _aio
        try: _aio.get_event_loop().run_until_complete(_ae("backup", "ERR001", str(e)[:200], exc=e))
        except: pass
        print(f"[BACKUP] Eroare backup {module_name}: {e}")
        return False


async def rollback_file(pool, module_name: str, version_type: str = "previous") -> dict:
    """Restaureaza o versiune anterioara"""
    # v4 este sacra - nu se suprascrie si nu se sterge niciodata
    if version_type == "v4":
        return {"status": "failed", "error": "v4 este versiunea sacra - nu se poate modifica"}
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT content, file_path, hash, created_at FROM file_versions WHERE module_name = $1 AND version_type = $2",
            module_name, version_type
        )
        if not row:
            return {"status": "failed", "error": f"Nu exista versiunea {version_type} pentru {module_name}"}

    # Backup versiunii curente inainte de rollback
    await backup_file(pool, module_name, created_by="rollback")

    # Restaureaza
    try:
        await _write_file_local(row["file_path"], bytes(row["content"]))

        # Restart serviciu daca e nevoie
        restart_result = ""
        async with asyncssh.connect("11.11.11.111", username="darkangel", client_keys=[SSH_KEY], known_hosts=_ssh_known_hosts()) as conn:
            r = await conn.run("sudo systemctl restart argos", timeout=30)
            restart_result = f"rc={r.exit_status}"

        return {
            "status": "ok",
            "module": module_name,
            "restored_version": version_type,
            "restored_from": str(row["created_at"]),
            "service_restart": restart_result
        }
    except Exception as e:
        from api.debug import argos_error as _ae; import asyncio as _aio
        try: _aio.get_event_loop().run_until_complete(_ae("backup", "ERR001", str(e)[:200], exc=e))
        except: pass
        return {"status": "failed", "error": str(e)}


async def auto_rollback_if_broken(pool, module_name: str) -> dict:
    """
    Verifica daca serviciul merge dupa modificare.
    Daca nu, face rollback automat la previous.
    """
    await asyncio.sleep(5)  # Asteapta sa porneasca

    # Verifica serviciul
    check_target, check_cmd = SERVICE_CHECKS.get(module_name, SERVICE_CHECKS["default"])
    try:
        async with asyncssh.connect("11.11.11.111", username="darkangel", client_keys=[SSH_KEY], known_hosts=_ssh_known_hosts()) as conn:
            r = await conn.run(check_cmd, timeout=30)
            if r.exit_status == 0 and "active" in (r.stdout or ""):
                return {"status": "ok", "service": "running"}

        # Serviciul nu merge - rollback automat
        print(f"[BACKUP] Serviciu cazut dupa modificare {module_name} - rollback automat")
        result = await rollback_file(pool, module_name, "previous")
        result["auto_rollback"] = True
        return result
    except Exception as e:
        from api.debug import argos_error as _ae; import asyncio as _aio
        try: _aio.get_event_loop().run_until_complete(_ae("backup", "ERR001", str(e)[:200], exc=e))
        except: pass
        return {"status": "error", "error": str(e)}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/backup/{module_name:path}")
async def create_backup(module_name: str):
    from api.main import pool
    ok = await backup_file(pool, module_name, created_by="manual")
    if ok:
        return {"status": "ok", "module": module_name}
    raise HTTPException(status_code=500, detail="Backup esuat")


@router.post("/rollback")
async def do_rollback(req: RollbackRequest):
    from api.main import pool
    return await rollback_file(pool, req.module_name, req.version_type)


@router.post("/backup-mark-lts")
async def mark_lts(req: MarkLTSRequest):
    from api.main import pool
    async with pool.acquire() as conn:
        # Sterge LTS vechi
        await conn.execute(
            "DELETE FROM file_versions WHERE module_name = $1 AND version_type = 'lts'",
            req.module_name
        )
        # Copiaza current ca LTS
        row = await conn.fetchrow(
            "SELECT content, file_path, hash FROM file_versions WHERE module_name = $1 AND version_type = 'current'",
            req.module_name
        )
        if not row:
            raise HTTPException(status_code=404, detail="Nu exista versiune current")
        await conn.execute(
            "INSERT INTO file_versions (module_name, version_type, content, file_path, hash, created_by) VALUES ($1, 'lts', $2, $3, $4, 'manual')",
            req.module_name, row["content"], row["file_path"], row["hash"]
        )
    return {"status": "ok", "module": req.module_name, "marked": "lts"}


@router.get("/backup/versions/{module_name:path}")
async def list_versions(module_name: str):
    from api.main import pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT version_type, hash, created_at, created_by FROM file_versions WHERE module_name = $1 ORDER BY created_at DESC",
            module_name
        )
    return {"module": module_name, "versions": [dict(r) for r in rows]}


@router.get("/backup/modules")
async def list_modules():
    return {"modules": list(WATCHED_FILES.keys())}


@router.get("/config-index")
async def get_config_index(zone: str = None, managed_by: str = None):
    from api.main import pool
    async with pool.acquire() as conn:
        if zone:
            rows = await conn.fetch("SELECT * FROM config_index WHERE zone ILIKE $1", f"%{zone}%")
        elif managed_by:
            rows = await conn.fetch("SELECT * FROM config_index WHERE managed_by = $1", managed_by)
        else:
            rows = await conn.fetch("SELECT * FROM config_index ORDER BY line_start")
    return {"zones": [dict(r) for r in rows]}


@router.get("/log")
async def get_backup_logs(limit: int = 50):
    """Returneaza logurile recente ale sistemului de backup"""
    from api.main import pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT module_name, version_type, created_at, created_by, hash
               FROM file_versions
               ORDER BY created_at DESC
               LIMIT $1""",
            limit
        )
    return {"logs": [dict(r) for r in rows], "count": len(rows)}
