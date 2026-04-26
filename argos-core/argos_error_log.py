#!/usr/bin/env python3
"""
ARGOS Error Pattern Logger v2

Foloseste asyncpg cu queries parametrizate ($1, $2 ...) — niciun string-format
in SQL. Fix audit H1 (SQL injection prin escape() artizanal).

Normalizeaza erori, calculeaza hash, logheaza in error_patterns.
Cod de eroare activ doar la count >= 10.
"""

import os
import re
import sys
import json
import asyncio
import hashlib
from datetime import datetime

import asyncpg

# ─── CONFIG ──────────────────────────────────────────────────────────────────
DB_HOST = os.getenv("DB_HOST", "11.11.11.111")
DB_PORT = int(os.getenv("DB_PORT", "5433"))
DB_USER = os.getenv("DB_USER", "claude")
DB_PASS = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "claudedb")

CATEGORY_PREFIXES = [
    "docker", "db", "ssh", "nixos", "swarm", "python", "bash", "generic"
]


# ─── DB HELPERS ──────────────────────────────────────────────────────────────
async def _connect():
    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASS, database=DB_NAME,
        timeout=10,
    )
    # Auto-encode/decode JSONB so we can pass dicts/lists directly as params
    # and read them back as Python objects instead of raw strings.
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )
    return conn


async def _async_query(sql: str, *params) -> tuple:
    try:
        conn = await _connect()
    except Exception as e:
        return False, f"connect failed: {e}"
    try:
        rows = await conn.fetch(sql, *params)
        return True, rows
    except Exception as e:
        return False, str(e)
    finally:
        await conn.close()


async def _async_exec(sql: str, *params) -> tuple:
    try:
        conn = await _connect()
    except Exception as e:
        return False, f"connect failed: {e}"
    try:
        result = await conn.execute(sql, *params)
        return True, result
    except Exception as e:
        return False, str(e)
    finally:
        await conn.close()


def db_query(sql: str, *params) -> tuple:
    """Sync wrapper for SELECT. Returns (ok, rows | error_string)."""
    return asyncio.run(_async_query(sql, *params))


def db_exec(sql: str, *params) -> tuple:
    """Sync wrapper for INSERT/UPDATE/DELETE. Returns (ok, status | error)."""
    return asyncio.run(_async_exec(sql, *params))


# ─── NORMALIZE ───────────────────────────────────────────────────────────────
def normalize(message: str) -> str:
    msg = message.strip()
    msg = re.sub(r'\b\d{1,3}(\.\d{1,3}){3}\b', '<IP>', msg)
    msg = re.sub(r':\d{2,5}\b', ':<PORT>', msg)
    msg = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', '<TS>', msg)
    msg = re.sub(r'\b[0-9a-f]{7,}\b', '<HEX>', msg)
    msg = re.sub(r'/tmp/[^\s]+', '/tmp/<FILE>', msg)
    msg = re.sub(r'/home/[^\s/]+', '/home/<USER>', msg)
    msg = re.sub(r'\b\d+\b', '<N>', msg)
    return msg


def make_hash(pattern: str) -> str:
    return hashlib.sha256(pattern.encode()).hexdigest()[:8]


# ─── LOG ERROR ───────────────────────────────────────────────────────────────
def log_error(message, category, node_hostname, node_os, context: dict) -> dict:
    prefix = category.split("-")[0].lower()
    if prefix not in CATEGORY_PREFIXES:
        category = "generic-" + category

    pattern = normalize(message)
    err_hash = make_hash(pattern)
    context["timestamp"] = datetime.utcnow().isoformat()

    ok, rows = db_query(
        "SELECT count, contexts FROM error_patterns WHERE hash = $1",
        err_hash,
    )
    if not ok:
        return {"error": rows}

    if rows:
        row = rows[0]
        new_count = row["count"] + 1
        existing = row["contexts"] if isinstance(row["contexts"], list) else []
        existing.append(context)
        existing = existing[-20:]

        ok, out = db_exec(
            """
            UPDATE error_patterns
            SET count = $1,
                last_seen = NOW(),
                contexts = $2,
                node_hostname = $3,
                node_os = $4
            WHERE hash = $5
            """,
            new_count, existing, node_hostname, node_os, err_hash,
        )
        if not ok:
            return {"error": out}
    else:
        new_count = 1
        ok, out = db_exec(
            """
            INSERT INTO error_patterns
                (hash, pattern, category, count, node_hostname, node_os, contexts)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            err_hash, pattern, category, 1, node_hostname, node_os, [context],
        )
        if not ok:
            return {"error": out}

    return {
        "hash": err_hash,
        "count": new_count,
        "code_active": new_count >= 10,
        "pattern": pattern,
        "category": category,
    }


# ─── GET ERROR ───────────────────────────────────────────────────────────────
def get_error(err_hash: str) -> dict:
    ok, rows = db_query(
        """
        SELECT hash, pattern, category, count, node_hostname,
               node_os, last_seen, client_owned, resolved
        FROM error_patterns WHERE hash = $1
        """,
        err_hash,
    )
    if not ok:
        return {"error": rows}
    if rows:
        r = rows[0]
        return {
            "source": "active",
            "hash": r["hash"],
            "pattern": r["pattern"],
            "category": r["category"],
            "count": str(r["count"]),
            "node_hostname": r["node_hostname"],
            "node_os": r["node_os"],
            "last_seen": r["last_seen"].isoformat() if r["last_seen"] else None,
            "client_owned": str(r["client_owned"]),
            "resolved": str(r["resolved"]),
        }

    ok, rows = db_query(
        "SELECT hash, category, summary, resolved_at FROM error_history WHERE hash = $1",
        err_hash,
    )
    if ok and rows:
        r = rows[0]
        return {
            "source": "history",
            "hash": r["hash"],
            "category": r["category"],
            "summary": r["summary"],
            "resolved_at": r["resolved_at"].isoformat() if r["resolved_at"] else None,
        }
    return {"error": "unknown hash"}


# ─── RESOLVE ERROR ───────────────────────────────────────────────────────────
def resolve_error(err_hash: str, summary: str, node_hostname: str) -> dict:
    ok, rows = db_query(
        "SELECT category FROM error_patterns WHERE hash = $1",
        err_hash,
    )
    if not ok or not rows:
        return {"error": "hash not found"}

    category = rows[0]["category"]

    ok, _ = db_exec(
        """
        INSERT INTO error_history (hash, category, summary, node_hostname)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (hash) DO UPDATE SET summary = EXCLUDED.summary, resolved_at = NOW()
        """,
        err_hash, category, summary, node_hostname,
    )
    if not ok:
        return {"error": "insert history failed"}

    db_exec(
        "UPDATE error_patterns SET resolved = TRUE WHERE hash = $1",
        err_hash,
    )
    return {"ok": True, "archived": err_hash}


# ─── MAIN ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  argos_error_log.py log '<msg>' '<category>' '<host>' '<os>' '<script>' ['<command>']")
        print("  argos_error_log.py get <hash>")
        print("  argos_error_log.py resolve <hash> '<summary>' '<host>'")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "log" and len(sys.argv) >= 7:
        result = log_error(
            message=sys.argv[2],
            category=sys.argv[3],
            node_hostname=sys.argv[4],
            node_os=sys.argv[5],
            context={
                "script": sys.argv[6],
                "command": sys.argv[7] if len(sys.argv) > 7 else ""
            }
        )
        print(json.dumps(result, indent=2))
        if result.get("code_active"):
            print(f"\n[ERR:{result['hash']}] — cod activ dupa {result['count']} aparitii")

    elif cmd == "get" and len(sys.argv) == 3:
        print(json.dumps(get_error(sys.argv[2]), indent=2))

    elif cmd == "resolve" and len(sys.argv) == 5:
        print(json.dumps(resolve_error(sys.argv[2], sys.argv[3], sys.argv[4]), indent=2))

    else:
        print("Argumente invalide.")
        sys.exit(1)
