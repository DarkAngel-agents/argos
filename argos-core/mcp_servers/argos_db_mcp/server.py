"""
argos-db-mcp server.

MCP server custom Postgres pentru argos-db.
Pas 3.9: + execute(sql, confirm) cu gating target-based.
  - cc_*              → pass-through (no approval)
  - system_credentials → hard refuse
  - altele / None      → approval_required (stub pentru Pas 3.10)

Vezi Vikunja #152 Pas 3 pentru ordinea implementare.

Usage:
    python server.py             # default: MCP stdio server (pentru Claude Code)
    python server.py --smoke     # debug: connect, schema, query+execute smoke, exit
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

import asyncpg
import httpx
import sqlparse
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from sqlparse.sql import Function, Identifier, IdentifierList


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DOTENV_PATH = Path(__file__).parent / ".env"
REQUIRED_DB_KEYS = ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME")


def load_config() -> dict[str, Any]:
    """Load .env langa server.py; valideaza prezenta+non-empty pe chei DB."""
    load_dotenv(DOTENV_PATH)
    missing = [k for k in REQUIRED_DB_KEYS if not os.getenv(k)]
    if missing:
        raise RuntimeError(
            f"Missing/empty config keys in {DOTENV_PATH}: {', '.join(missing)}"
        )
    return {
        "db_host": os.environ["DB_HOST"],
        "db_port": int(os.environ["DB_PORT"]),
        "db_user": os.environ["DB_USER"],
        "db_password": os.environ["DB_PASSWORD"],
        "db_name": os.environ["DB_NAME"],
        "argos_api_url": os.getenv("ARGOS_API_URL", "http://127.0.0.1:666"),
        "poll_interval_sec": int(os.getenv("APPROVAL_POLL_INTERVAL_SEC", "2")),
        "approval_timeout_sec": int(os.getenv("APPROVAL_TIMEOUT_SEC", "1800")),
    }


_cfg: Optional[dict[str, Any]] = None


def get_cfg() -> dict[str, Any]:
    global _cfg
    if _cfg is None:
        _cfg = load_config()
    return _cfg


# ---------------------------------------------------------------------------
# Connection pool
# ---------------------------------------------------------------------------

_pool: Optional[asyncpg.Pool] = None


async def get_pool(cfg: Optional[dict[str, Any]] = None) -> asyncpg.Pool:
    global _pool
    if _pool is None:
        cfg = cfg or get_cfg()
        _pool = await asyncpg.create_pool(
            host=cfg["db_host"],
            port=cfg["db_port"],
            user=cfg["db_user"],
            password=cfg["db_password"],
            database=cfg["db_name"],
            min_size=1,
            max_size=5,
            command_timeout=30,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


_http: Optional[httpx.AsyncClient] = None


async def get_http() -> httpx.AsyncClient:
    """Get or create module-level httpx client cu base_url = argos_api_url."""
    global _http
    if _http is None:
        cfg = get_cfg()
        _http = httpx.AsyncClient(
            base_url=cfg["argos_api_url"],
            timeout=10.0,
        )
    return _http


async def close_http() -> None:
    """Close module-level http client, reset."""
    global _http
    if _http is not None:
        await _http.aclose()
        _http = None


async def _request_approval(
    kind: str,
    intent_text: str,
    intent_json: dict,
    timeout_seconds: int = 1800,
) -> dict:
    """POST /api/claude-code/request-approval. Return response dict.

    Raises httpx.HTTPStatusError la 4xx/5xx, httpx.RequestError la network errors.
    """
    client = await get_http()
    resp = await client.post(
        "/api/claude-code/request-approval",
        json={
            "kind": kind,
            "intent_text": intent_text,
            "intent_json": intent_json,
            "session_id": None,
            "timeout_seconds": timeout_seconds,
        },
    )
    resp.raise_for_status()
    return resp.json()


async def _poll_approval(
    approval_id: int,
    poll_interval: float = 2.0,
    max_wait: float = 1800.0,
) -> dict:
    """Poll GET /approval-status/{id} pana status != pending sau max_wait atins.

    Returneaza dict cu final status. Server marcheaza `timeout` atomic idempotent
    pe GET daca s-a depasit requesting, deci nu trebuie sa calculam noi.
    """
    client = await get_http()
    loop = asyncio.get_event_loop()
    deadline = loop.time() + max_wait
    while True:
        resp = await client.get(f"/api/claude-code/approval-status/{approval_id}")
        resp.raise_for_status()
        data = resp.json()
        if data["status"] != "pending":
            return data
        if loop.time() + poll_interval >= deadline:
            # Un ultim poll dupa sleep (serverul va fi marcat timeout)
            await asyncio.sleep(max(0.0, deadline - loop.time()))
            resp = await client.get(f"/api/claude-code/approval-status/{approval_id}")
            resp.raise_for_status()
            return resp.json()
        await asyncio.sleep(poll_interval)


# ---------------------------------------------------------------------------
# SQL parsing helpers (shared)
# ---------------------------------------------------------------------------

FORBIDDEN_KEYWORDS = frozenset({
    "INSERT", "UPDATE", "DELETE", "MERGE", "UPSERT",
    "CREATE", "DROP", "ALTER", "TRUNCATE",
    "GRANT", "REVOKE", "COMMENT",
    "COPY", "VACUUM", "ANALYZE", "REINDEX", "CLUSTER",
    "LOCK", "CALL", "DO", "EXECUTE", "PREPARE", "DEALLOCATE",
    "SET", "RESET", "LISTEN", "NOTIFY", "UNLISTEN",
})

WRITE_VERBS = frozenset({
    "INSERT", "UPDATE", "DELETE", "MERGE",
    "TRUNCATE", "CREATE", "DROP", "ALTER",
})

# Dupa CREATE/DROP/ALTER, obiectele astea nu sunt tabele → return None,
# gating-ul trimite la approval_required (fail-safe).
NON_TABLE_DDL_OBJECTS = frozenset({
    "INDEX", "VIEW", "SEQUENCE", "TRIGGER", "FUNCTION", "PROCEDURE",
    "SCHEMA", "DATABASE", "ROLE", "USER", "POLICY", "EXTENSION",
    "MATERIALIZED", "TYPE", "DOMAIN", "RULE", "OPERATOR",
    "AGGREGATE", "CAST", "CONVERSION", "COLLATION",
})

DEFAULT_ROW_LIMIT = 1000
MAX_ROW_LIMIT = 10000


def _parse_single_statement(sql: str):
    """Parse SQL, assert non-empty si single-statement. Return stmt. Raise ValueError."""
    parsed = sqlparse.parse(sql)
    non_empty = [
        s for s in parsed
        if any(not t.is_whitespace for t in s.flatten())
    ]
    if not non_empty:
        raise ValueError("empty SQL")
    if len(non_empty) > 1:
        raise ValueError(
            f"multiple statements not allowed ({len(non_empty)} found); "
            "send one query at a time"
        )
    return non_empty[0]


def _validate_read_only(sql: str) -> None:
    """Raise ValueError daca SQL nu e SELECT/CTE pur single-statement."""
    stmt = _parse_single_statement(sql)
    for tok in stmt.flatten():
        if tok.ttype is None:
            continue
        ttype_str = str(tok.ttype)
        if "Keyword" not in ttype_str:
            continue
        kw = tok.normalized.upper()
        if kw in FORBIDDEN_KEYWORDS:
            raise ValueError(f"forbidden keyword in read-only query: {kw}")


def _is_write_sql(sql: str) -> bool:
    """True daca SQL contine VREUN write verb (gestioneaza WITH...INSERT CTE)."""
    for stmt in sqlparse.parse(sql):
        for tok in stmt.flatten():
            if tok.ttype is None:
                continue
            ttype_str = str(tok.ttype)
            if "Keyword" not in ttype_str and "DML" not in ttype_str and "DDL" not in ttype_str:
                continue
            if tok.normalized.upper() in WRITE_VERBS:
                return True
    return False


# ---------------------------------------------------------------------------
# Target table extraction (verb-based, 45/45 cases PASS in exploratory)
# ---------------------------------------------------------------------------

def _is_meaningful(t) -> bool:
    if t.is_whitespace:
        return False
    if t.ttype is not None and "Comment" in str(t.ttype):
        return False
    return True


def _tok_is_keyword_eq(t, value: str) -> bool:
    if t.ttype is None:
        return False
    if "Keyword" not in str(t.ttype):
        return False
    return t.normalized.upper() == value.upper()


def _name_from_obj(obj) -> Optional[str]:
    """Extract lowercased real name din Identifier/Function/Name token, fara schema prefix."""
    if isinstance(obj, Identifier):
        name = obj.get_real_name()
        return name.lower() if name else None
    if isinstance(obj, Function):
        for sub in obj.tokens:
            if isinstance(sub, Identifier):
                n = sub.get_real_name()
                if n:
                    return n.lower()
            elif sub.ttype is not None and "Name" in str(sub.ttype):
                return sub.value.strip('"').strip('`').lower()
        return None
    if isinstance(obj, IdentifierList):
        for sub in obj.tokens:
            if isinstance(sub, Identifier):
                return _name_from_obj(sub)
        return None
    if obj.ttype is not None and "Name" in str(obj.ttype):
        return obj.value.strip('"').strip('`').lower()
    return None


def _extract_target_table(sql: str) -> Optional[str]:
    """Extract numele tabelului tinta dintr-un SQL de scriere.

    Returns:
        lowercased name al tabelului (fara schema prefix, fara ghilimele), sau
        None daca SQL-ul nu e write, e DDL pe alt obiect (INDEX/VIEW/etc.), sau
        nu poate fi determinat.

    None → gating trimite la approval_required (fail-safe).

    Acoperit de 45/45 cazuri in explore_target_v2.py.
    """
    parsed = sqlparse.parse(sql)
    if not parsed:
        return None
    stmt = parsed[0]
    toks = [t for t in stmt.tokens if _is_meaningful(t)]
    if not toks:
        return None

    # Primul write verb (gestioneaza WITH-CTE sarind peste WITH block).
    verb_idx = None
    verb: Optional[str] = None
    flat = list(stmt.flatten())
    for t in flat:
        if t.ttype is None:
            continue
        ttype_str = str(t.ttype)
        if "Keyword" not in ttype_str and "DML" not in ttype_str and "DDL" not in ttype_str:
            continue
        kw = t.normalized.upper()
        if kw in WRITE_VERBS:
            verb = kw
            break
    if verb is None:
        return None

    # Gaseste index la nivel top unde apare verb-ul sau un container care il include.
    for i, t in enumerate(toks):
        if _tok_is_keyword_eq(t, verb) or (
            t.ttype is not None and "DML" in str(t.ttype) and t.normalized.upper() == verb
        ):
            verb_idx = i
            break
    if verb_idx is None:
        # Verb e probabil in interiorul unui container (ex CTE body).
        # Pentru INSERT dupa WITH, stmt.tokens are: WITH, Identifier(cte_def), DML(INSERT), ...
        # Daca am ajuns aici, gasesc primul DML token top-level:
        for i, t in enumerate(toks):
            if t.ttype is not None and "DML" in str(t.ttype):
                verb_idx = i
                verb = t.normalized.upper()
                break
        if verb_idx is None:
            return None

    rest = toks[verb_idx + 1:]

    if verb == "UPDATE":
        for t in rest:
            if isinstance(t, (Identifier, Function)):
                return _name_from_obj(t)
            if t.ttype is not None and "Name" in str(t.ttype):
                return t.value.strip('"').strip('`').lower()
            if _tok_is_keyword_eq(t, "SET"):
                return None
        return None

    if verb == "DELETE":
        saw_from = False
        for t in rest:
            if _tok_is_keyword_eq(t, "FROM"):
                saw_from = True
                continue
            if saw_from:
                if isinstance(t, (Identifier, Function)):
                    return _name_from_obj(t)
                if t.ttype is not None and "Name" in str(t.ttype):
                    return t.value.strip('"').strip('`').lower()
        return None

    if verb in ("INSERT", "MERGE"):
        saw_into = False
        for t in rest:
            if _tok_is_keyword_eq(t, "INTO"):
                saw_into = True
                continue
            if saw_into:
                if isinstance(t, (Identifier, Function)):
                    return _name_from_obj(t)
                if t.ttype is not None and "Name" in str(t.ttype):
                    return t.value.strip('"').strip('`').lower()
        return None

    if verb == "TRUNCATE":
        for t in rest:
            if _tok_is_keyword_eq(t, "TABLE") or _tok_is_keyword_eq(t, "ONLY"):
                continue
            if isinstance(t, (Identifier, Function, IdentifierList)):
                return _name_from_obj(t)
            if t.ttype is not None and "Name" in str(t.ttype):
                return t.value.strip('"').strip('`').lower()
        return None

    if verb in ("CREATE", "DROP", "ALTER"):
        saw_table = False
        for t in rest:
            if t.ttype is not None and "Keyword" in str(t.ttype):
                kw = t.normalized.upper()
                if kw == "TABLE":
                    saw_table = True
                    continue
                if kw in NON_TABLE_DDL_OBJECTS:
                    return None
                # Alt modifier (TEMP/UNLOGGED/IF/NOT/EXISTS/OR/REPLACE/GLOBAL/LOCAL) → skip
                continue
            if saw_table:
                if isinstance(t, (Identifier, Function)):
                    return _name_from_obj(t)
                if t.ttype is not None and "Name" in str(t.ttype):
                    return t.value.strip('"').strip('`').lower()
            else:
                # Name token inainte de TABLE (ex UNLOGGED/MATERIALIZED tokenized ca Name)
                if t.ttype is not None and "Name" in str(t.ttype):
                    if t.value.upper() in NON_TABLE_DDL_OBJECTS:
                        return None
                    continue
        return None

    return None


# ---------------------------------------------------------------------------
# Rows-affected parser (asyncpg command tag)
# ---------------------------------------------------------------------------

# asyncpg ret status: "UPDATE 5", "DELETE 2", "INSERT 0 3", "TRUNCATE TABLE",
# "CREATE TABLE", "DROP TABLE", "ALTER TABLE". Ultimul integer = rows affected.
_ROWS_AFFECTED_RE = re.compile(r"\b(\d+)\s*$")


def _parse_rows_affected(status: Optional[str]) -> int:
    """Parse asyncpg command tag → rows affected int. DDL → 0 (no match)."""
    if not status:
        return 0
    m = _ROWS_AFFECTED_RE.search(status.strip())
    return int(m.group(1)) if m else 0


# ---------------------------------------------------------------------------
# Masking — system_credentials
# ---------------------------------------------------------------------------

SYSTEM_CREDENTIALS_WHITELIST = frozenset({
    "id", "system_id", "credential_type", "label", "active", "created_at",
})

MASKED_VALUE = "***"

SENSITIVE_TABLE = "system_credentials"


def _touches_system_credentials(sql: str) -> bool:
    """True daca SQL contine referinta catre `system_credentials`.

    Conservativ, case-insensitive. Skip string literals si comentarii,
    pastreaza quoted identifiers ("system_credentials").
    """
    for stmt in sqlparse.parse(sql):
        for tok in stmt.flatten():
            ttype_str = str(tok.ttype) if tok.ttype is not None else ""
            if "Comment" in ttype_str:
                continue
            if "String" in ttype_str and "Symbol" not in ttype_str:
                continue
            val = tok.value.strip().strip('"').strip("`").lower()
            if val == SENSITIVE_TABLE:
                return True
    return False


def _mask_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        k: (v if k in SYSTEM_CREDENTIALS_WHITELIST else MASKED_VALUE)
        for k, v in row.items()
    }


# ---------------------------------------------------------------------------
# Business logic
# ---------------------------------------------------------------------------

async def list_schema(pool: asyncpg.Pool) -> dict[str, list[dict[str, Any]]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT table_name, column_name, data_type,
                   is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
            """
        )
    grouped: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        grouped.setdefault(r["table_name"], []).append({
            "column": r["column_name"],
            "type": r["data_type"],
            "nullable": r["is_nullable"],
            "default": r["column_default"],
        })
    return grouped


async def run_query(sql: str, limit: int = DEFAULT_ROW_LIMIT) -> dict[str, Any]:
    """Execute read-only SELECT, fetch up to limit rows, apply masking."""
    _validate_read_only(sql)
    limit = min(max(1, int(limit)), MAX_ROW_LIMIT)

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            cursor = await conn.cursor(sql)
            raw = await cursor.fetch(limit + 1)

    truncated = len(raw) > limit
    rows = [dict(r) for r in raw[:limit]]

    masked = _touches_system_credentials(sql)
    if masked:
        rows = [_mask_row(r) for r in rows]

    return {
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
        "masked": masked,
    }


async def run_execute(sql: str, confirm: bool = False) -> dict[str, Any]:
    """Execute DML/DDL cu gating target-based.

    Gating (prioritate ordine):
        target == system_credentials    → hard_refuse_system_credentials (zero DB hit)
        target.startswith("cc_")        → cc_passthrough (executa direct, no approval)
        target is None sau altfel       → approval_required (Pas 3.10 stub)

    `confirm` param accept acum dar ignored; activat la Pas 3.10 dupa approval flow.

    Returns:
        {
            "success": bool,
            "rows_affected": int,
            "gating": str,
            "target_table": Optional[str],
            "error": Optional[str],
            "status": Optional[str],
        }

    Raises ValueError daca SQL e read-only (use query()) sau multi-statement.
    """
    _parse_single_statement(sql)  # reject empty / multi-statement
    if not _is_write_sql(sql):
        raise ValueError(
            "execute() requires write verb (INSERT/UPDATE/DELETE/CREATE/"
            "DROP/ALTER/TRUNCATE/MERGE); use query() for reads"
        )

    target = _extract_target_table(sql)

    # Gating 1: hard refuse system_credentials (zero DB hit)
    if target == SENSITIVE_TABLE:
        return {
            "success": False,
            "rows_affected": 0,
            "gating": "hard_refuse_system_credentials",
            "target_table": target,
            "error": "writes to system_credentials are hard-refused",
            "status": None,
        }

    # Gating 2: cc_* pass-through
    if target is not None and target.startswith("cc_"):
        pool = await get_pool()
        try:
            async with pool.acquire() as conn:
                status = await conn.execute(sql)
            return {
                "success": True,
                "rows_affected": _parse_rows_affected(status),
                "gating": "cc_passthrough",
                "target_table": target,
                "error": None,
                "status": status,
            }
        except asyncpg.PostgresError as e:
            return {
                "success": False,
                "rows_affected": 0,
                "gating": "cc_passthrough",
                "target_table": target,
                "error": f"db error: {type(e).__name__}: {e}",
                "status": None,
            }

    # Gating 3: approval_required — POST request + poll + execute daca approved
    cfg = get_cfg()
    intent_text = f"SQL on {target}" if target else "SQL (unknown target)"

    try:
        req_resp = await _request_approval(
            kind="cc_sql",
            intent_text=intent_text,
            intent_json={"query": sql},
            timeout_seconds=cfg["approval_timeout_sec"],
        )
    except httpx.HTTPStatusError as e:
        # API hard refuse (403) sau validation error (400) ajung aici
        return {
            "success": False,
            "rows_affected": 0,
            "gating": "approval_required",
            "target_table": target,
            "approval_id": None,
            "risk_level": None,
            "error": (
                f"approval request failed: HTTP {e.response.status_code}: "
                f"{e.response.text[:200]}"
            ),
            "status": None,
        }
    except (httpx.RequestError, httpx.TimeoutException) as e:
        return {
            "success": False,
            "rows_affected": 0,
            "gating": "approval_required",
            "target_table": target,
            "approval_id": None,
            "risk_level": None,
            "error": f"approval request network error: {type(e).__name__}: {e}",
            "status": None,
        }

    approval_id = req_resp["approval_id"]
    risk_level = req_resp.get("risk_level")

    try:
        final = await _poll_approval(
            approval_id,
            poll_interval=float(cfg["poll_interval_sec"]),
            max_wait=float(cfg["approval_timeout_sec"]),
        )
    except (httpx.RequestError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
        return {
            "success": False,
            "rows_affected": 0,
            "gating": "approval_required",
            "target_table": target,
            "approval_id": approval_id,
            "risk_level": risk_level,
            "error": f"approval polling error: {type(e).__name__}: {e}",
            "status": None,
        }

    final_status = final.get("status")
    if final_status != "approved":
        return {
            "success": False,
            "rows_affected": 0,
            "gating": "approval_required",
            "target_table": target,
            "approval_id": approval_id,
            "risk_level": risk_level,
            "error": (
                f"approval {final_status}: "
                f"{final.get('decision_reason') or 'no reason given'}"
            ),
            "status": None,
        }

    # Approved → executa SQL real
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            status = await conn.execute(sql)
        return {
            "success": True,
            "rows_affected": _parse_rows_affected(status),
            "gating": "approval_required",
            "target_table": target,
            "approval_id": approval_id,
            "risk_level": risk_level,
            "error": None,
            "status": status,
        }
    except asyncpg.PostgresError as e:
        return {
            "success": False,
            "rows_affected": 0,
            "gating": "approval_required",
            "target_table": target,
            "approval_id": approval_id,
            "risk_level": risk_level,
            "error": f"db error after approval: {type(e).__name__}: {e}",
            "status": None,
        }


# ---------------------------------------------------------------------------
# MCP server + tools
# ---------------------------------------------------------------------------

mcp = FastMCP("argos-db")


@mcp.tool()
async def schema() -> dict[str, list[dict[str, Any]]]:
    """Return lista tabele publice + coloane din claudedb.

    Read-only. Fara masking. Folosit de Claude Code sa inteleaga structura DB.
    """
    pool = await get_pool()
    return await list_schema(pool)


@mcp.tool()
async def query(sql: str, limit: int = DEFAULT_ROW_LIMIT) -> dict[str, Any]:
    """Execute read-only SELECT/CTE cu masking automat pe system_credentials.

    Args:
        sql: SELECT sau WITH...SELECT. Single statement only.
        limit: max rows (default 1000, cap 10000).

    Returns:
        {"rows": [...], "row_count": N, "truncated": bool, "masked": bool}
    """
    return await run_query(sql, limit)


@mcp.tool()
async def execute(sql: str, confirm: bool = False) -> dict[str, Any]:
    """Execute DML/DDL cu gating automat target-based.

    Gating:
        target = system_credentials → hard refuse (zero DB hit)
        target.startswith("cc_")    → pass-through (no approval)
        target None / altfel        → approval_required (Pas 3.10)

    `confirm` acum ignored, activat la Pas 3.10 cu approval flow complet.

    Returns:
        {"success": bool, "rows_affected": int, "gating": str,
         "target_table": str|null, "error": str|null, "status": str|null}
    """
    return await run_execute(sql, confirm)


# ---------------------------------------------------------------------------
# Entrypoints
# ---------------------------------------------------------------------------

async def _smoke() -> None:
    cfg = get_cfg()
    print(
        f"[argos-db-mcp] connecting "
        f"{cfg['db_user']}@{cfg['db_host']}:{cfg['db_port']}/{cfg['db_name']}",
        file=sys.stderr,
    )
    pool = await get_pool(cfg)
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT current_database() AS db, version() AS ver"
            )
            print(f"[argos-db-mcp] db={row['db']}", file=sys.stderr)
            print(f"[argos-db-mcp] {row['ver']}", file=sys.stderr)
        grouped = await list_schema(pool)
        print(
            f"[argos-db-mcp] schema(): {len(grouped)} tables, "
            f"{sum(len(v) for v in grouped.values())} columns total",
            file=sys.stderr,
        )
        qr = await run_query(
            "SELECT id, label, username FROM system_credentials LIMIT 1"
        )
        print(f"[argos-db-mcp] masking smoke: {qr}", file=sys.stderr)

        # execute gating smoke (zero side effect)
        r1 = await run_execute(
            "UPDATE system_credentials SET active=true WHERE id=-999"
        )
        print(f"[argos-db-mcp] execute hard_refuse: {r1['gating']}", file=sys.stderr)

        # Pas 3.10: approval flow live. Skip din smoke ca sa nu creeze
        # approval pending la fiecare smoke run. Testat separat prin respx.
        print("[argos-db-mcp] approval_required path: tested via respx (skipped in smoke)", file=sys.stderr)
    finally:
        await close_pool()
        await close_http()


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--smoke":
        try:
            asyncio.run(_smoke())
        except Exception as e:
            print(f"[argos-db-mcp] FATAL: {e}", file=sys.stderr)
            sys.exit(1)
        return
    mcp.run()


if __name__ == "__main__":
    main()
