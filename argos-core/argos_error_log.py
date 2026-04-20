#!/usr/bin/env python3
"""
ARGOS Error Pattern Logger v2
Zero dependente externe — foloseste psql via subprocess.
Normalizeaza erori, calculeaza hash, logheaza in error_patterns.
Cod de eroare activ doar la count >= 10.
"""

import re
import hashlib
import json
import subprocess
import sys
from datetime import datetime

# ─── CONFIG ──────────────────────────────────────────────────────────────────
DB_HOST = "11.11.11.111"
DB_PORT = "5433"
DB_USER = "claude"
DB_PASS = os.getenv("DB_PASSWORD")
DB_NAME = "claudedb"

CATEGORY_PREFIXES = [
    "docker", "db", "ssh", "nixos", "swarm", "python", "bash", "generic"
]

# ─── PSQL HELPER ─────────────────────────────────────────────────────────────
def psql(sql: str) -> tuple:
    import os
    env = {**os.environ, "PGPASSWORD": DB_PASS}
    cmd = [
        "docker", "exec", "argos-db",
        "psql",
        f"--host=127.0.0.1",
        f"--username={DB_USER}", f"--dbname={DB_NAME}",
        "--tuples-only", "--no-align",
        "-c", sql
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=10)
        if result.returncode != 0:
            return False, result.stderr.strip()
        return True, result.stdout.strip()
    except FileNotFoundError:
        return False, "psql not found in PATH"
    except subprocess.TimeoutExpired:
        return False, "psql timeout after 10s"


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


def escape(s: str) -> str:
    return s.replace("'", "''")


# ─── LOG ERROR ───────────────────────────────────────────────────────────────
def log_error(message, category, node_hostname, node_os, context: dict) -> dict:
    prefix = category.split("-")[0].lower()
    if prefix not in CATEGORY_PREFIXES:
        category = "generic-" + category

    pattern = normalize(message)
    err_hash = make_hash(pattern)
    context["timestamp"] = datetime.utcnow().isoformat()

    ok, out = psql(f"SELECT count, contexts FROM error_patterns WHERE hash='{err_hash}';")
    if not ok:
        return {"error": out}

    if out:
        parts = out.split("|")
        new_count = int(parts[0].strip()) + 1
        try:
            existing = json.loads(parts[1].strip()) if len(parts) > 1 else []
        except Exception:
            existing = []
        existing.append(context)
        existing = existing[-20:]
        ctx_json = escape(json.dumps(existing))

        ok, out = psql(f"""
            UPDATE error_patterns
            SET count={new_count}, last_seen=NOW(),
                contexts='{ctx_json}'::jsonb,
                node_hostname='{escape(node_hostname)}',
                node_os='{escape(node_os)}'
            WHERE hash='{err_hash}';
        """)
        if not ok:
            return {"error": out}
    else:
        new_count = 1
        ctx_json = escape(json.dumps([context]))
        ok, out = psql(f"""
            INSERT INTO error_patterns
                (hash, pattern, category, count, node_hostname, node_os, contexts)
            VALUES (
                '{err_hash}', '{escape(pattern)}', '{escape(category)}',
                1, '{escape(node_hostname)}', '{escape(node_os)}',
                '{ctx_json}'::jsonb
            );
        """)
        if not ok:
            return {"error": out}

    return {
        "hash": err_hash,
        "count": new_count,
        "code_active": new_count >= 10,
        "pattern": pattern,
        "category": category
    }


# ─── GET ERROR ───────────────────────────────────────────────────────────────
def get_error(err_hash: str) -> dict:
    ok, out = psql(f"""
        SELECT hash, pattern, category, count, node_hostname,
               node_os, last_seen, client_owned, resolved
        FROM error_patterns WHERE hash='{err_hash}';
    """)
    if not ok:
        return {"error": out}
    if out:
        f = [x.strip() for x in out.split("|")]
        return {
            "source": "active", "hash": f[0], "pattern": f[1],
            "category": f[2], "count": f[3], "node_hostname": f[4],
            "node_os": f[5], "last_seen": f[6], "client_owned": f[7],
            "resolved": f[8]
        }
    ok, out = psql(f"SELECT hash, category, summary, resolved_at FROM error_history WHERE hash='{err_hash}';")
    if ok and out:
        f = [x.strip() for x in out.split("|")]
        return {"source": "history", "hash": f[0], "category": f[1],
                "summary": f[2], "resolved_at": f[3]}
    return {"error": "unknown hash"}


# ─── RESOLVE ERROR ───────────────────────────────────────────────────────────
def resolve_error(err_hash: str, summary: str, node_hostname: str) -> dict:
    ok, out = psql(f"SELECT category FROM error_patterns WHERE hash='{err_hash}';")
    if not ok or not out:
        return {"error": "hash not found"}

    category = out.strip()
    ok, _ = psql(f"""
        INSERT INTO error_history (hash, category, summary, node_hostname)
        VALUES ('{err_hash}', '{escape(category)}',
                '{escape(summary)}', '{escape(node_hostname)}')
        ON CONFLICT (hash) DO UPDATE SET summary=EXCLUDED.summary, resolved_at=NOW();
    """)
    if not ok:
        return {"error": "insert history failed"}

    psql(f"UPDATE error_patterns SET resolved=TRUE WHERE hash='{err_hash}';")
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
