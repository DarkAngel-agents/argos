import os
import re
import asyncio
import asyncssh
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter()

KNOWN_HOSTS = {
    "beasty": {"host": "11.11.11.111", "user": "darkangel"},
    "hermes":   {"host": "11.11.11.98",  "user": "root"},
    "master":   {"host": "11.11.11.201", "user": "root"},
    "claw":     {"host": "11.11.11.113", "user": "darkangel"},
    "zeus":     {"host": "11.11.11.11",  "user": "root"},
}

# VM-uri anuntate via ISO - user argos, cheie SSH
AGENT_VMS = {}  # ip -> {"host": ip, "user": "argos"}

LOCAL_MACHINES = []

SSH_KEY = os.path.expanduser("~/.ssh/id_ed25519")
BACKUP_DIR = "/data/files/configs"

# Timeout-uri per tip operatie
TIMEOUT_DEFAULT = 30    # comenzi simple
TIMEOUT_INSTALL = 600   # nixos-install, nix-build
TIMEOUT_REBUILD = 300   # nixos-rebuild


# ─── Input validators (audit C3) ──────────────────────────────────────────────
# Whitelist of characters allowed in a backup filename used by /api/nixos-restore.
# No slashes, no spaces, no shell metacharacters → blocks both shell injection
# and path traversal in the remote `cat {BACKUP_DIR}/{filename}` interpolation.
_FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _validate_filename(name: str) -> None:
    """Reject anything that isn't a simple filename. Raises HTTP 400."""
    if not isinstance(name, str) or not name:
        raise HTTPException(status_code=400, detail="filename is required")
    if len(name) > 255:
        raise HTTPException(status_code=400, detail="filename too long (max 255 chars)")
    if not _FILENAME_RE.match(name):
        raise HTTPException(
            status_code=400,
            detail="filename must match [A-Za-z0-9._-]+ (no slashes, no shell metachars)",
        )


def _get_timeout(command: str) -> int:
    cmd = command.lower()
    if any(x in cmd for x in ["nixos-install", "nix-build", "nix-channel --update"]):
        return TIMEOUT_INSTALL
    if any(x in cmd for x in ["nixos-rebuild", "nixos-generate-config"]):
        return TIMEOUT_REBUILD
    return TIMEOUT_DEFAULT


class ExecRequest(BaseModel):
    machine: str
    command: str
    conversation_id: Optional[int] = None


class NixosRebuildRequest(BaseModel):
    conversation_id: Optional[int] = None
    config_content: Optional[str] = None


class RestoreRequest(BaseModel):
    filename: str


@router.post("/exec")
async def execute_command(req: ExecRequest):
    machine = req.machine.lower()
    is_ip = bool(re.match(r'^\d+\.\d+\.\d+\.\d+$', machine))
    if machine not in KNOWN_HOSTS and machine not in LOCAL_MACHINES and not is_ip:
        raise HTTPException(status_code=400, detail=f"Masina necunoscuta: {machine}")
    try:
        result = await _exec_ssh_by_name(machine, req.command)
        return {"machine": machine, "command": req.command, **result}
    except Exception as e:
        from api.debug import argos_error as _ae; import asyncio as _aio
        try: _aio.get_event_loop().run_until_complete(_ae("executor", "ERR001", str(e)[:200], exc=e))
        except Exception as e2:
            print(f"[IO 002] executor error logging failed: {e2}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/nixos-rebuild")
async def nixos_rebuild(req: NixosRebuildRequest):
    results = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"beasty-{timestamp}.nix"

    read = await _exec_ssh_by_name("beasty", "cat /etc/nixos/configuration.nix")
    if read["returncode"] != 0:
        return {"status": "failed", "step": "read_config", "results": [read]}
    config_content = read["stdout"]

    escaped = config_content.replace("'", "'\\''")
    backup_cmd = f"mkdir -p {BACKUP_DIR} && printf '%s' '{escaped}' > {BACKUP_DIR}/{backup_name}"
    backup = await _exec_ssh_by_name("beasty", backup_cmd)
    results.append({"step": "backup", "file": backup_name, **backup})
    if backup["returncode"] != 0:
        return {"status": "failed", "step": "backup", "results": results}

    if req.config_content:
        escaped_new = req.config_content.replace("'", "'\\''")
        write_cmd = f"printf '%s' '{escaped_new}' | /run/wrappers/bin/sudo tee /etc/nixos/configuration.nix > /dev/null"
        write = await _exec_ssh_by_name("beasty", write_cmd)
        results.append({"step": "write_config", **write})
        if write["returncode"] != 0:
            return {"status": "failed", "step": "write_config", "results": results}

    rebuild = await _exec_ssh_by_name("beasty", "/run/wrappers/bin/sudo nixos-rebuild switch 2>&1")
    results.append({"step": "rebuild", **rebuild})

    status = "ok" if rebuild["returncode"] == 0 else "failed"
    return {"status": status, "backup": backup_name, "results": results}


@router.get("/nixos-backups")
async def list_backups():
    result = await _exec_ssh_by_name("beasty", f"ls -lt {BACKUP_DIR}/*.nix 2>/dev/null | awk '{{print $6, $7, $9}}'")
    if result["returncode"] != 0 or not result["stdout"]:
        return {"backups": []}
    backups = []
    for line in result["stdout"].splitlines():
        parts = line.strip().split()
        if len(parts) >= 3:
            path = parts[2]
            filename = path.split("/")[-1]
            backups.append({"filename": filename, "date": f"{parts[0]} {parts[1]}", "path": path})
    return {"backups": backups}


@router.post("/nixos-restore")
async def restore_backup(req: RestoreRequest):
    _validate_filename(req.filename)  # audit C3 — blocks shell injection
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pre_restore_backup = f"beasty-pre-restore-{timestamp}.nix"

    read = await _exec_ssh_by_name("beasty", "cat /etc/nixos/configuration.nix")
    if read["returncode"] == 0:
        escaped = read["stdout"].replace("'", "'\\''")
        await _exec_ssh_by_name("beasty", f"printf '%s' '{escaped}' > {BACKUP_DIR}/{pre_restore_backup}")

    read_backup = await _exec_ssh_by_name("beasty", f"cat {BACKUP_DIR}/{req.filename}")
    if read_backup["returncode"] != 0:
        return {"status": "failed", "step": "read_backup", "detail": read_backup["stderr"]}

    escaped = read_backup["stdout"].replace("'", "'\\''")
    write = await _exec_ssh_by_name("beasty", f"printf '%s' '{escaped}' | /run/wrappers/bin/sudo tee /etc/nixos/configuration.nix > /dev/null")
    if write["returncode"] != 0:
        return {"status": "failed", "step": "write", "detail": write["stderr"]}

    rebuild = await _exec_ssh_by_name("beasty", "/run/wrappers/bin/sudo nixos-rebuild switch 2>&1")
    return {
        "status": "ok" if rebuild["returncode"] == 0 else "failed",
        "restored": req.filename,
        "pre_restore_backup": pre_restore_backup,
        "rebuild_output": rebuild["stdout"][-500:] if rebuild["stdout"] else ""
    }


@router.get("/machines")
async def list_machines():
    return {"machines": list(KNOWN_HOSTS.keys())}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _exec_ssh_by_name(machine: str, command: str) -> dict:
    machine = machine.strip().lower()

    # Beasty - executie locala
    if machine in LOCAL_MACHINES:
        return await _exec_local(command)

    # IP direct - verificam daca e VM agent sau masina cunoscuta
    if re.match(r'^\d+\.\d+\.\d+\.\d+$', machine):
        # Cautam in AGENT_VMS
        if machine in AGENT_VMS:
            info = AGENT_VMS[machine]
            return await _exec_ssh(info["host"], info["user"], command)
        # IP necunoscut - incercam cu user argos (VM agent)
        return await _exec_ssh(machine, "argos", command)

    # Masina cunoscuta din KNOWN_HOSTS
    if machine in KNOWN_HOSTS:
        info = KNOWN_HOSTS[machine]
        return await _exec_ssh(info["host"], info["user"], command)

    return {"stdout": "", "stderr": f"Masina necunoscuta: {machine}", "returncode": 1}


async def _exec_local(command: str) -> dict:
    env = os.environ.copy()
    env["PATH"] = "/run/wrappers/bin:/run/current-system/sw/bin:/nix/var/nix/profiles/default/bin:" + env.get("PATH", "")
    timeout = _get_timeout(command)
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "stdout": stdout.decode().strip(),
            "stderr": stderr.decode().strip(),
            "returncode": proc.returncode
        }
    except asyncio.TimeoutError:
        from api.debug import argos_error
        try:
            import asyncio as _aio; _aio.get_event_loop().run_until_complete(argos_error("executor", "SSH002", f"SSH timeout {timeout}s", context={"host": host, "command": command[:100]}))
        except Exception as e2:
            print(f"[IO 003] exec_local timeout logging failed: {e2}", flush=True)
        return {"stdout": "", "stderr": f"Timeout dupa {timeout}s", "returncode": 124}


async def _exec_ssh(host: str, user: str, command: str) -> dict:
    timeout = _get_timeout(command)
    try:
        async with asyncssh.connect(
            host, username=user,
            client_keys=[SSH_KEY],
            known_hosts=None,
            connect_timeout=10
        ) as conn:
            result = await conn.run(command, timeout=timeout)
            return {
                "stdout": result.stdout.strip() if result.stdout else "",
                "stderr": result.stderr.strip() if result.stderr else "",
                "returncode": result.exit_status or 0
            }
    except asyncssh.PermissionDenied:
        from api.debug import argos_error; import asyncio as _aio
        try: _aio.get_event_loop().run_until_complete(argos_error("executor", "SSH001", "SSH permission denied", context={"host": str(locals().get('host',''))[:50]}))
        except Exception as e2:
            print(f"[IO 004] SSH PermissionDenied logging failed: {e2}", flush=True)
        return {"stdout": "", "stderr": f"SSH permission denied pentru {user}@{host}", "returncode": 255}
    except asyncssh.ConnectionLost:
        from api.debug import argos_error; import asyncio as _aio
        try: _aio.get_event_loop().run_until_complete(argos_error("executor", "SSH001", "SSH connection lost", context={"host": str(locals().get('host',''))[:50]}))
        except Exception as e2:
            print(f"[IO 005] SSH ConnectionLost logging failed: {e2}", flush=True)
        return {"stdout": "", "stderr": f"Conexiune pierduta cu {host}", "returncode": 255}
    except OSError as e:
        from api.debug import argos_error; import asyncio as _aio
        try: _aio.get_event_loop().run_until_complete(argos_error("executor", "SSH001", "SSH connect fail", context={"host": str(locals().get('host',''))[:50]}))
        except Exception as e2:
            print(f"[IO 006] SSH OSError logging failed: {e2}", flush=True)
        return {"stdout": "", "stderr": f"Nu pot conecta la {host}: {e}", "returncode": 255}
    except Exception as e:
        from api.debug import argos_error as _ae; import asyncio as _aio
        try: _aio.get_event_loop().run_until_complete(_ae("executor", "ERR001", str(e)[:200], exc=e))
        except Exception as e2:
            print(f"[IO 007] SSH generic exception logging failed: {e2}", flush=True)
        return {"stdout": "", "stderr": str(e), "returncode": 1}


async def check_autonomy(pool, category: str, action: str) -> dict:
    """
    Verifica daca Argos poate actiona autonom sau trebuie aprobare.
    Returneaza: {mode: "auto"|"present"|"require", success_rate: float, threshold: float}
    """
    async with pool.acquire() as conn:
        # Citeste config autonomie
        cfg = await conn.fetchrow(
            "SELECT risk_level, auto_threshold, window_size FROM autonomy_config WHERE category = $1",
            category
        )
        if not cfg:
            # Categorie necunoscuta - cere aprobare by default
            return {"mode": "require", "success_rate": 0.0, "threshold": 1.0, "risk": "unknown"}

        # Calculeaza success_rate pe ultimele N actiuni
        rows = await conn.fetch(
            """SELECT outcome FROM knowledge_base
               WHERE category = $1 AND action ILIKE $2
               ORDER BY last_tried_at DESC LIMIT $3""",
            category, f"%{action[:30]}%", cfg["window_size"]
        )

        if not rows:
            # Nu are istoric - pentru high risk cere aprobare, altfel merge
            if cfg["risk_level"] == "high":
                return {"mode": "present", "success_rate": 0.0,
                        "threshold": cfg["auto_threshold"], "risk": cfg["risk_level"]}
            return {"mode": "auto", "success_rate": 1.0,
                    "threshold": cfg["auto_threshold"], "risk": cfg["risk_level"]}

        total = len(rows)
        ok = sum(1 for r in rows if r["outcome"] == "ok")
        rate = ok / total if total > 0 else 0.0

        # Decide modul
        if cfg["risk_level"] == "low":
            mode = "auto"
        elif rate >= cfg["auto_threshold"]:
            mode = "auto"
        elif cfg["risk_level"] == "high":
            mode = "present"  # prezinta scurt, asteapta accept sau "detaliaza"
        else:
            mode = "require"  # cere aprobare explicita

        return {
            "mode": mode,
            "success_rate": round(rate, 2),
            "threshold": cfg["auto_threshold"],
            "risk": cfg["risk_level"],
            "history": f"{ok}/{total} actiuni ok"
        }


async def log_action_outcome(pool, category: str, action: str, outcome: str,
                              reason: str = None, os_type: str = None):
    """Salveaza rezultatul unei actiuni in KB pentru invatare autonomie"""
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id, times_tried FROM knowledge_base WHERE category=$1 AND action=$2 LIMIT 1",
            category, action[:200]
        )
        if existing:
            await conn.execute(
                """UPDATE knowledge_base
                   SET times_tried=times_tried+1, last_tried_at=NOW(),
                       outcome=$1, reason=$2
                   WHERE id=$3""",
                outcome, reason, existing["id"]
            )
        else:
            await conn.execute(
                """INSERT INTO knowledge_base
                   (category, os_type, action, outcome, reason, times_tried)
                   VALUES ($1, $2, $3, $4, $5, 1)""",
                category, os_type, action[:200], outcome, reason
            )
