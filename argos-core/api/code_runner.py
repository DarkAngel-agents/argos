"""
Programmatic Tool Calling - ruleaza cod Python generat de Claude
intr-un subprocess izolat cu acces la tool-urile Argos
"""
import asyncio
import os
import sys
import json
import tempfile
import subprocess
from typing import Optional

RUNNER_TIMEOUT = 120  # secunde

RUNNER_PREAMBLE = '''
import sys, os, json, asyncio, asyncssh, asyncpg, httpx
from dotenv import load_dotenv
load_dotenv(os.path.expanduser("~/.argos/argos-core/config/.env"))
os.environ["PATH"] = "/run/current-system/sw/bin:/run/wrappers/bin:" + os.environ.get("PATH", "")

DB_CONF = {
    "host": os.getenv("DB_HOST", "11.11.11.111"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "user": os.getenv("DB_USER", "claude"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME", "claudedb"),
    "ssl": False
}

SSH_KEY = os.path.expanduser("~/.ssh/id_ed25519")
RESULTS = []

async def ssh(host: str, user: str, command: str, timeout: int = 30) -> dict:
    """Executa comanda SSH. Daca host e local (beasty/127.0.0.1/localhost) ruleaza direct."""
    local_hosts = {"11.11.11.111", "127.0.0.1", "localhost", "beasty"}
    if host in local_hosts:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return {"ok": proc.returncode==0, "stdout": stdout.decode().strip(),
                    "stderr": stderr.decode().strip(), "rc": proc.returncode}
        except asyncio.TimeoutError:
            proc.kill()
            return {"ok": False, "error": f"Timeout {timeout}s"}
    try:
        async with asyncssh.connect(
            host, username=user, client_keys=[SSH_KEY],
            known_hosts=None, connect_timeout=10
        ) as conn:
            r = await conn.run(command, timeout=timeout)
            return {"ok": True, "stdout": r.stdout.strip(), "stderr": r.stderr.strip(), "rc": r.exit_status}
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def db_query(sql: str, *args) -> list:
    """Executa query DB read-only si returneaza rezultatele"""
    pool = await asyncpg.create_pool(**DB_CONF)
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *args)
    await pool.close()
    return [dict(r) for r in rows]

async def db_exec(sql: str, *args) -> str:
    """Executa query DB write si returneaza statusul"""
    pool = await asyncpg.create_pool(**DB_CONF)
    async with pool.acquire() as conn:
        result = await conn.execute(sql, *args)
    await pool.close()
    return result

def result(data):
    """Adauga un rezultat la output"""
    RESULTS.append(data)

def report(msg: str):
    """Afiseaza un mesaj de progres"""
    print(f"[RUNNER] {msg}", flush=True)

# Hosts cunoscute
HOSTS = {
    "beasty": ("11.11.11.111", "darkangel"),
    "zeus":   ("11.11.11.11",  "root"),
    "master": ("11.11.11.201", "root"),
}

async def on(host: str, command: str, timeout: int = 30) -> dict:
    """Shortcut: executa pe host cunoscut. beasty = local subprocess."""
    if host == "beasty":
        import asyncio, subprocess
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return {"ok": proc.returncode==0, "stdout": stdout.decode().strip(),
                    "stderr": stderr.decode().strip(), "rc": proc.returncode}
        except asyncio.TimeoutError:
            proc.kill()
            return {"ok": False, "error": f"Timeout {timeout}s"}
    if host not in HOSTS:
        return {"ok": False, "error": f"Host necunoscut: {host}"}
    ip, user = HOSTS[host]
    return await ssh(ip, user, command, timeout)


'''


async def run_code(code: str, timeout: int = RUNNER_TIMEOUT) -> dict:
    """
    Ruleaza cod Python in subprocess izolat.
    Returneaza: {ok, output, results, error}
    """
    full_code = RUNNER_PREAMBLE + "\n" + code + "\n\n" + \
        "asyncio.run(main()) if 'main' in dir() else None\n" + \
        "import json; print('__RESULTS__' + json.dumps(RESULTS))\n"

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py',
                                     delete=False, prefix='/tmp/argos_runner_') as f:
        f.write(full_code)
        tmpfile = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, tmpfile,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ,
                 "PYTHONPATH": os.path.expanduser("~/.argos/argos-core")}
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            return {"ok": False, "error": f"Timeout dupa {timeout}s", "results": []}

        out = stdout.decode()
        err = stderr.decode()

        # Extrage RESULTS din output
        results = []
        output_lines = []
        for line in out.splitlines():
            if line.startswith("__RESULTS__"):
                try:
                    results = json.loads(line[11:])
                except Exception:
                    pass
            else:
                output_lines.append(line)

        return {
            "ok": proc.returncode == 0,
            "output": "\n".join(output_lines),
            "results": results,
            "error": err if err else None,
            "returncode": proc.returncode
        }
    finally:
        os.unlink(tmpfile)
