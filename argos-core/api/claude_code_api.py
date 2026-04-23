"""
ARGOS Claude Code API - Faza B Pas 1 (Vikunja #152)

Endpoint-uri pentru aprobari Claude Code (kind: cc_file, cc_bash, cc_sql, cc_tool).
Pattern calcat 1:1 pe api/jobs.py. Toate INSERT/UPDATE in tabela `authorizations`
(extinsa in Faza A #148 cu: kind, session_id, timeout_seconds, intent_json,
 decision_reason + CHECK constraint pe kind + FK session_id -> cc_chat_sessions).

Endpoints:
  POST /api/claude-code/request-approval
  GET  /api/claude-code/approval-status/{id}
  POST /api/claude-code/approval/{id}/decide

Debug codes: [CCAPI NNN]
"""
import json
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Any, Dict

router = APIRouter()


# =============================================================================
# Risk detection - conservative, default medium
# =============================================================================

# cc_bash: read-only whitelist (doar citire, zero side-effects)
BASH_SAFE_CMDS = {
    "ls", "cat", "grep", "ps", "find", "df", "stat", "head", "tail", "wc",
    "pwd", "whoami", "id", "date", "uptime", "hostname", "uname", "free",
    "which", "env", "echo", "printenv", "awk", "sed", "cut", "sort", "uniq",
    "tr", "less", "more", "file", "type", "readlink", "dirname", "basename",
    "history", "du",
}

# cc_bash: critical (destructive, pipe-to-shell, wipe)
BASH_CRITICAL = [
    "qm destroy", "qm stop", "wipefs", "dd if=", "mkfs",
    "parted", "zpool destroy", "zpool create", "rm -rf /",
    "| sh", "| bash", "| python", "| zsh", "| fish",
    "curl | sh", "wget | sh", ":(){ :|:& };:",
]

# cc_bash: high (orice sudo, systemctl stop/restart, reboot, nixos-rebuild)
BASH_HIGH = [
    "nixos-rebuild", "nixos-install", "configuration.nix",
    "systemctl restart", "systemctl stop", "systemctl disable",
    "systemctl mask",
    "reboot", "shutdown", "poweroff", "sudo ",
    "docker service rm", "docker stack rm", "docker swarm leave",
    "docker volume rm", "docker network rm",
    "iptables -F", "iptables -X", "nft flush",
]

# cc_bash: medium (install, docker run/exec, chmod/chown)
BASH_MEDIUM = [
    "qm create", "qm start", "apt install", "apt remove", "apt purge",
    "nix-env", "nix-collect-garbage",
    "chmod 777", "chown root", "docker run", "docker exec",
    "systemctl start",
]

# cc_file: prefixe high (system dirs, secrete)
FILE_HIGH_PREFIXES = [
    "/etc/", "/boot/", "/nix/", "/var/lib/", "/usr/", "/root/",
    "/home/darkangel/.ssh/", "/home/argos/.ssh/",
    "/home/darkangel/.argos/config/",
]

# cc_file: patterns oriunde in path
FILE_HIGH_PATTERNS = [
    "/.ssh/", "/config/.env", "configuration.nix",
    "/docker/swarm-stack.yml", "/docker/Dockerfile",
    "/.argos.env",
]

# cc_file: low (sandbox, /tmp)
FILE_LOW_PREFIXES = [
    "/tmp/", "/var/tmp/", "/dev/shm/",
    "/home/argos/sandbox/", "/home/argos/work/",
]

# cc_sql: patterns critice (DROP TABLE/DB, TRUNCATE, DELETE/UPDATE fara WHERE)
SQL_CRITICAL_PATTERNS = [
    r"\bDROP\s+(TABLE|DATABASE|SCHEMA)\b",
    r"\bTRUNCATE\b",
]

# cc_sql: DDL non-destructiv (CREATE/ALTER)
SQL_DDL_PATTERNS = [
    r"\bCREATE\s+(TABLE|INDEX|SCHEMA|VIEW|FUNCTION|TRIGGER)\b",
    r"\bALTER\s+(TABLE|INDEX|SCHEMA|TYPE)\b",
    r"\bDROP\s+(INDEX|VIEW|FUNCTION|TRIGGER|CONSTRAINT)\b",
]

SQL_DML_WRITE_RE = re.compile(r"\b(INSERT|UPDATE|DELETE|MERGE)\b", re.IGNORECASE)
SQL_SELECT_RE = re.compile(r"\bSELECT\b", re.IGNORECASE)
SQL_SYSTEM_CREDS_RE = re.compile(r"\bsystem_credentials\b", re.IGNORECASE)
SQL_HAS_WHERE_RE = re.compile(r"\bWHERE\b", re.IGNORECASE)
SQL_TABLE_REF_RE = re.compile(
    r"\b(?:FROM|INTO|UPDATE|JOIN)\s+([a-zA-Z_]\w*)",
    re.IGNORECASE,
)


def _bash_first_word(cmd: str) -> str:
    """Extract first command word, skip env var prefixes (FOO=bar cmd)."""
    for part in cmd.strip().split():
        if "=" in part and not part.startswith("-") and not part.startswith("/"):
            # looks like env var assignment
            eq_pos = part.find("=")
            if eq_pos > 0 and part[:eq_pos].replace("_", "").isalnum():
                continue
        # strip path, keep basename
        return part.lstrip("/").split("/")[-1]
    return ""


def _sql_is_destructive_no_where(query: str) -> bool:
    """True daca DELETE FROM X sau UPDATE X SET ... fara WHERE."""
    # DELETE FROM table; (fara WHERE)
    m = re.search(
        r"\bDELETE\s+FROM\s+\w+\s*(?:;|\-\-|$)",
        query,
        re.IGNORECASE | re.MULTILINE,
    )
    if m:
        return True
    # UPDATE table SET ... fara WHERE in aceeasi statement
    # Aproximare simpla: orice UPDATE urmat de SET dar fara WHERE undeva
    update_match = re.search(r"\bUPDATE\s+\w+\s+SET\b", query, re.IGNORECASE)
    if update_match:
        # cauta WHERE dupa acest UPDATE, pana la `;` sau final
        tail = query[update_match.end():]
        stmt_end = tail.find(";")
        stmt = tail if stmt_end < 0 else tail[:stmt_end]
        if not re.search(r"\bWHERE\b", stmt, re.IGNORECASE):
            return True
    return False


def detect_cc_risk(kind: str, intent_json: dict) -> str:
    """
    Returneaza nivel risc pentru un intent Claude Code.
    Valori: 'low', 'medium', 'high', 'critical'. Default conservativ: 'medium'.
    """
    ij = intent_json or {}

    if kind == "cc_bash":
        cmd = (ij.get("command") or "").strip()
        if not cmd:
            return "medium"
        cmd_lower = cmd.lower()

        for p in BASH_CRITICAL:
            if p in cmd_lower:
                return "critical"
        for p in BASH_HIGH:
            if p in cmd_lower:
                return "high"
        for p in BASH_MEDIUM:
            if p in cmd_lower:
                return "medium"

        first = _bash_first_word(cmd)
        if first in BASH_SAFE_CMDS:
            return "low"
        return "medium"

    if kind == "cc_file":
        path = (ij.get("path") or "").strip()
        if not path:
            return "medium"
        for pref in FILE_HIGH_PREFIXES:
            if path.startswith(pref):
                return "high"
        for pat in FILE_HIGH_PATTERNS:
            if pat in path:
                return "high"
        for pref in FILE_LOW_PREFIXES:
            if path.startswith(pref):
                return "low"
        return "medium"

    if kind == "cc_sql":
        query = (ij.get("query") or "").strip()
        if not query:
            return "medium"
        # Critical: DROP TABLE/DB, TRUNCATE, DELETE/UPDATE fara WHERE
        for pat in SQL_CRITICAL_PATTERNS:
            if re.search(pat, query, re.IGNORECASE):
                return "critical"
        if _sql_is_destructive_no_where(query):
            return "critical"
        # DDL non-destructiv = high
        for pat in SQL_DDL_PATTERNS:
            if re.search(pat, query, re.IGNORECASE):
                return "high"
        # DML write - check tables
        if SQL_DML_WRITE_RE.search(query):
            tables = SQL_TABLE_REF_RE.findall(query)
            if tables and all(t.lower().startswith("cc_") for t in tables):
                return "low"
            return "high"
        # SELECT pur = low
        if SQL_SELECT_RE.search(query):
            return "low"
        return "medium"

    if kind == "cc_tool":
        return "medium"

    # kind necunoscut - conservativ
    return "high"


def _check_hard_refuse(kind: str, intent_json: dict) -> Optional[str]:
    """
    Hard refuz inainte de INSERT in authorizations.
    Defense-in-depth peste masking din MCP (Pas 3).
    """
    if kind == "cc_sql":
        query = (intent_json or {}).get("query") or ""
        if SQL_SYSTEM_CREDS_RE.search(query) and SQL_DML_WRITE_RE.search(query):
            return "Write operations on system_credentials are refused unconditionally"
    return None


# =============================================================================
# Human-readable details formatter (pentru UI modal)
# =============================================================================

def _format_cc_details(kind: str, intent_json: dict) -> str:
    """
    Genereaza text scurt human-readable pentru coloana `details`.
    UI existent (stream.py -> auth_pending event) citeste `details`.
    """
    ij = intent_json or {}

    if kind == "cc_file":
        path = ij.get("path", "?")
        op = ij.get("operation", "write")
        size = ij.get("size")
        size_str = f" ({size} bytes)" if isinstance(size, int) else ""
        return f"{op.capitalize()} file: {path}{size_str}"

    if kind == "cc_bash":
        target = ij.get("target", "local")
        cmd = ij.get("command", "?")
        if len(cmd) > 200:
            cmd = cmd[:200] + "..."
        return f"Exec on {target}: {cmd}"

    if kind == "cc_sql":
        query = ij.get("query", "?").strip()
        if len(query) > 300:
            query = query[:300] + "..."
        return f"SQL: {query}"

    if kind == "cc_tool":
        tool = ij.get("tool", "?")
        args = ij.get("args", {})
        args_str = json.dumps(args, default=str)
        if len(args_str) > 200:
            args_str = args_str[:200] + "..."
        return f"Tool {tool}: {args_str}"

    return json.dumps(ij, default=str)[:500]


# =============================================================================
# Pydantic models
# =============================================================================

ALLOWED_KINDS = {"cc_file", "cc_bash", "cc_sql", "cc_tool"}


class ApprovalRequest(BaseModel):
    kind: str
    intent_text: str
    intent_json: Dict[str, Any] = {}
    session_id: Optional[int] = None
    timeout_seconds: Optional[int] = 1800


class ApprovalDecision(BaseModel):
    decision: str
    reason: Optional[str] = None


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/claude-code/request-approval")
async def request_approval(req: ApprovalRequest):
    """
    Creeaza cerere de aprobare pentru operatie Claude Code.
    Returneaza {approval_id, kind, risk_level, status, timeout_seconds}.
    """
    from api.main import pool

    # Validare kind
    if req.kind not in ALLOWED_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"[CCAPI 001] Invalid kind '{req.kind}'. Allowed: {sorted(ALLOWED_KINDS)}",
        )

    # Validare intent_text non-gol
    if not req.intent_text or not req.intent_text.strip():
        raise HTTPException(
            status_code=400,
            detail="[CCAPI 002] intent_text must not be empty",
        )

    # Hard refuz pe system_credentials write (defense-in-depth)
    refuse_reason = _check_hard_refuse(req.kind, req.intent_json)
    if refuse_reason:
        raise HTTPException(status_code=403, detail=f"[CCAPI 003] {refuse_reason}")

    # Validare session_id exista (daca e dat)
    if req.session_id is not None:
        async with pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM cc_chat_sessions WHERE id = $1",
                req.session_id,
            )
            if not exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"[CCAPI 004] session_id {req.session_id} not found in cc_chat_sessions",
                )

    # Clamp timeout
    timeout = req.timeout_seconds if (req.timeout_seconds and req.timeout_seconds > 0) else 1800

    risk = detect_cc_risk(req.kind, req.intent_json)
    details = _format_cc_details(req.kind, req.intent_json)

    try:
        async with pool.acquire() as conn:
            approval_id = await conn.fetchval(
                """INSERT INTO authorizations
                   (kind, operation, details, risk_level, status,
                    session_id, timeout_seconds, intent_json, requested_at)
                   VALUES ($1, $2, $3, $4, 'pending', $5, $6, $7, NOW())
                   RETURNING id""",
                req.kind,
                req.intent_text.strip(),
                details,
                risk,
                req.session_id,
                timeout,
                json.dumps(req.intent_json),
            )
    except Exception as e:
        try:
            from api.debug import argos_error
            await argos_error("claude_code_api", "CCAPI-005", str(e)[:200], exc=e)
        except Exception:
            pass
        raise HTTPException(
            status_code=500,
            detail=f"[CCAPI 005] DB insert failed: {type(e).__name__}: {e}",
        )

    return {
        "approval_id": approval_id,
        "kind": req.kind,
        "risk_level": risk,
        "status": "pending",
        "timeout_seconds": timeout,
    }


@router.get("/claude-code/approval-status/{approval_id}")
async def get_approval_status(approval_id: int):
    """
    Returneaza statusul unei aprobari + marcheaza timeout daca a expirat.
    UPDATE e atomic idempotent (a doua oara nu schimba nimic).
    """
    from api.main import pool

    async with pool.acquire() as conn:
        # Marcheaza timeout daca e pending si a expirat
        await conn.execute(
            """UPDATE authorizations
               SET status = 'timeout'
               WHERE id = $1
                 AND status = 'pending'
                 AND timeout_seconds IS NOT NULL
                 AND EXTRACT(EPOCH FROM (NOW() - requested_at)) > timeout_seconds""",
            approval_id,
        )

        row = await conn.fetchrow(
            """SELECT id, kind, operation, details, risk_level, status,
                      session_id, timeout_seconds, intent_json, decision_reason,
                      requested_at, decided_at
               FROM authorizations WHERE id = $1""",
            approval_id,
        )

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"[CCAPI 010] Approval {approval_id} not found",
        )

    # intent_json poate veni string (jsonb) sau dict, normalizeaza
    ij = row["intent_json"]
    if isinstance(ij, str):
        try:
            ij = json.loads(ij)
        except Exception:
            pass

    return {
        "approval_id": row["id"],
        "kind": row["kind"],
        "intent_text": row["operation"],
        "details": row["details"],
        "risk_level": row["risk_level"],
        "status": row["status"],
        "session_id": row["session_id"],
        "timeout_seconds": row["timeout_seconds"],
        "intent_json": ij,
        "decision_reason": row["decision_reason"],
        "requested_at": row["requested_at"].isoformat() if row["requested_at"] else None,
        "decided_at": row["decided_at"].isoformat() if row["decided_at"] else None,
    }


@router.post("/claude-code/approval/{approval_id}/decide")
async def decide_approval(approval_id: int, req: ApprovalDecision):
    """Decide o aprobare pending: approved sau denied (+ reason opt)."""
    from api.main import pool

    if req.decision not in ("approved", "denied"):
        raise HTTPException(
            status_code=400,
            detail=f"[CCAPI 020] Invalid decision '{req.decision}'. Must be 'approved' or 'denied'",
        )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, status FROM authorizations WHERE id = $1",
            approval_id,
        )
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"[CCAPI 021] Approval {approval_id} not found",
            )
        if row["status"] != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"[CCAPI 022] Approval {approval_id} already decided (status='{row['status']}')",
            )

        await conn.execute(
            """UPDATE authorizations
               SET status = $1, decision_reason = $2, decided_at = NOW()
               WHERE id = $3""",
            req.decision,
            req.reason,
            approval_id,
        )

    return {
        "approval_id": approval_id,
        "decision": req.decision,
        "reason": req.reason,
        "status": req.decision,
    }
