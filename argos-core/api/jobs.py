import json
import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

router = APIRouter()

# Operatii care necesita autorizare obligatorie
RISK_RULES = {
    "critical": [
        "qm destroy", "qm stop", "wipefs", "dd if=", "mkfs",
        "parted", "zpool destroy", "zpool create", "rm -rf /"
    ],
    "high": [
        "nixos-rebuild", "nixos-install", "configuration.nix",
        "systemctl restart", "systemctl stop",
        "reboot", "shutdown", "poweroff"
    ],
    "medium": [
        "qm create", "qm start", "apt install", "nix-env",
        "chmod 777", "chown root"
    ]
}


def detect_risk(command: str) -> str:
    cmd_lower = command.lower()
    for level in ["critical", "high", "medium"]:
        for pattern in RISK_RULES[level]:
            if pattern in cmd_lower:
                return level
    return "low"


class JobCreate(BaseModel):
    conversation_id: int
    title: str
    steps: List[str]        # lista de comenzi
    target: str             # masina tinta
    risk_level: Optional[str] = None  # auto-detectat daca lipseste


class AuthDecision(BaseModel):
    decision: str  # approved / denied


@router.post("/jobs")
async def create_job(req: JobCreate):
    from api.main import pool

    # Auto-detectam risk level daca nu e dat
    risk = req.risk_level or "low"
    if not req.risk_level:
        for step in req.steps:
            detected = detect_risk(step)
            if detected == "critical":
                risk = "critical"
                break
            elif detected == "high" and risk != "critical":
                risk = "high"
            elif detected == "medium" and risk not in ["critical", "high"]:
                risk = "medium"

    segments = [{"step": i, "command": cmd, "target": req.target} for i, cmd in enumerate(req.steps)]

    async with pool.acquire() as conn:
        job_id = await conn.fetchval(
            """INSERT INTO jobs (conversation_id, title, status, segments, created_at, updated_at)
               VALUES ($1, $2, $3, $4, NOW(), NOW()) RETURNING id""",
            req.conversation_id, req.title,
            "waiting_auth" if risk in ["critical", "high"] else "pending",
            json.dumps(segments)
        )

        # Daca e risc mare, cream autorizare
        if risk in ["critical", "high"]:
            await conn.execute(
                """INSERT INTO authorizations (job_id, operation, details, risk_level, status, requested_at)
                   VALUES ($1, $2, $3, $4, 'pending', NOW())""",
                job_id,
                f"Job: {req.title}",
                f"Target: {req.target}\nPasi ({len(req.steps)}):\n" + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(req.steps)),
                risk
            )

    return {
        "job_id": job_id,
        "status": "waiting_auth" if risk in ["critical", "high"] else "pending",
        "risk_level": risk,
        "steps": len(req.steps),
        "message": "Asteapta aprobare in UI" if risk in ["critical", "high"] else "Gata de executie"
    }


@router.get("/jobs")
async def list_jobs(conversation_id: Optional[int] = None):
    from api.main import pool
    async with pool.acquire() as conn:
        if conversation_id:
            rows = await conn.fetch(
                "SELECT id, title, status, current_segment, error, created_at, updated_at FROM jobs WHERE conversation_id = $1 ORDER BY created_at DESC",
                conversation_id
            )
        else:
            rows = await conn.fetch(
                "SELECT id, title, status, current_segment, error, created_at, updated_at FROM jobs ORDER BY created_at DESC LIMIT 20"
            )
    return {"jobs": [dict(r) for r in rows]}


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: int):
    from api.main import pool
    async with pool.acquire() as conn:
        job = await conn.fetchrow("SELECT id FROM jobs WHERE id = $1", job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job negasit")
        await conn.execute("DELETE FROM authorizations WHERE job_id = $1", job_id)
        await conn.execute("DELETE FROM jobs WHERE id = $1", job_id)
    return {"status": "ok", "deleted": job_id}

@router.get("/jobs/{job_id}")
async def get_job(job_id: int):
    from api.main import pool
    async with pool.acquire() as conn:
        job = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job negasit")
        auths = await conn.fetch("SELECT * FROM authorizations WHERE job_id = $1", job_id)
    return {"job": dict(job), "authorizations": [dict(a) for a in auths]}


@router.get("/authorizations/pending")
async def list_pending_auth():
    from api.main import pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT a.*, j.title as job_title, j.conversation_id
               FROM authorizations a
               JOIN jobs j ON a.job_id = j.id
               WHERE a.status = 'pending'
               ORDER BY a.requested_at DESC"""
        )
    return {"authorizations": [dict(r) for r in rows]}


@router.post("/authorizations/{auth_id}/decide")
async def decide_auth(auth_id: int, req: AuthDecision):
    from api.main import pool

    if req.decision not in ["approved", "denied"]:
        raise HTTPException(status_code=400, detail="Decision trebuie sa fie 'approved' sau 'denied'")

    async with pool.acquire() as conn:
        auth = await conn.fetchrow("SELECT * FROM authorizations WHERE id = $1", auth_id)
        if not auth:
            raise HTTPException(status_code=404, detail="Autorizare negasita")
        if auth["status"] != "pending":
            raise HTTPException(status_code=400, detail=f"Autorizarea are deja status: {auth['status']}")

        await conn.execute(
            "UPDATE authorizations SET status = $1, decided_at = NOW() WHERE id = $2",
            req.decision, auth_id
        )

        # Actualizam job-ul
        new_status = "pending" if req.decision == "approved" else "failed"
        error = None if req.decision == "approved" else "Refuzat de utilizator"
        await conn.execute(
            "UPDATE jobs SET status = $1, error = $2, updated_at = NOW() WHERE id = $3",
            new_status, error, auth["job_id"]
        )

    return {
        "status": "ok",
        "auth_id": auth_id,
        "decision": req.decision,
        "job_status": "pending" if req.decision == "approved" else "failed"
    }


@router.post("/jobs/{job_id}/execute")
async def execute_job(job_id: int):
    """Executa un job aprobat pas cu pas"""
    from api.main import pool
    from api.executor import _exec_ssh_by_name

    async with pool.acquire() as conn:
        job = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job negasit")
        if job["status"] not in ["pending"]:
            raise HTTPException(status_code=400, detail=f"Job nu poate fi executat: status={job['status']}")

        await conn.execute(
            "UPDATE jobs SET status = 'running', updated_at = NOW() WHERE id = $1", job_id
        )

    segments = json.loads(job["segments"])
    results = []
    start_from = job["current_segment"] or 0

    try:
        for i, seg in enumerate(segments[start_from:], start=start_from):
            # Update current segment
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE jobs SET current_segment = $1, updated_at = NOW() WHERE id = $2",
                    i, job_id
                )

            # Executa
            result = await _exec_ssh_by_name(seg["target"], seg["command"])
            results.append({"step": i, "command": seg["command"], **result})

            # Salveaza rezultatele
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE jobs SET results = $1, updated_at = NOW() WHERE id = $2",
                    json.dumps(results), job_id
                )

            if result["returncode"] != 0:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE jobs SET status = 'failed', error = $1, updated_at = NOW() WHERE id = $2",
                        f"Pas {i} esuat: rc={result['returncode']} {result['stderr'][:200]}", job_id
                    )
                return {"status": "failed", "step": i, "results": results}

        # Succes
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE jobs SET status = 'ok', updated_at = NOW() WHERE id = $1", job_id
            )
        return {"status": "ok", "steps_executed": len(segments), "results": results}

    except Exception as e:
        from api.debug import argos_error as _ae; import asyncio as _aio
        try: _aio.get_event_loop().run_until_complete(_ae("jobs", "ERR001", str(e)[:200], exc=e))
        except: pass
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE jobs SET status = 'failed', error = $1, updated_at = NOW() WHERE id = $2",
                str(e), job_id
            )
        raise HTTPException(status_code=500, detail=str(e))
