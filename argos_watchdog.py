#!/usr/bin/env python3.13
"""
Argos Watchdog - serviciu separat care monitorizeaza Argos
si face rollback automat daca cade dupa o modificare.
"""
import asyncio
import asyncpg
import httpx
import os
import subprocess
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/.argos/argos-core/config/.env"))

ARGOS_URL = "http://localhost:8000"
CHECK_INTERVAL = 10       # secunde intre verificari
GRACE_PERIOD = 15         # secunde dupa modificare inainte sa verifice
FAIL_THRESHOLD = 3        # verificari consecutive esuate inainte de rollback

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
    "nixos/configuration.nix": "/etc/nixos/configuration.nix",
}

fail_count = 0
last_modification_time = 0.0


def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WATCHDOG] {msg}", flush=True)


async def get_pool():
    return await asyncpg.create_pool(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 5432)),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        ssl=False
    )


async def check_argos_health() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{ARGOS_URL}/health")
            return r.status_code == 200
    except Exception:
        return False


def get_recent_logs(lines: int = 30) -> str:
    try:
        result = subprocess.run(
            ["journalctl", "-u", "argos", f"-n{lines}", "--no-pager"],
            capture_output=True, text=True
        )
        return result.stdout
    except Exception:
        return ""


def restart_argos():
    subprocess.run(["sudo", "systemctl", "restart", "argos"])
    time.sleep(5)


async def rollback_file(pool, module_name: str, version_type: str = "previous") -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT content, file_path FROM file_versions WHERE module_name = $1 AND version_type = $2 ORDER BY created_at DESC LIMIT 1",
            module_name, version_type
        )
        if not row:
            log(f"Nu exista versiunea {version_type} pentru {module_name}")
            return False
        with open(row["file_path"], "wb") as f:
            f.write(bytes(row["content"]))
        log(f"Restaurat {module_name} din {version_type}")
        return True


async def save_incident(pool, description: str, logs: str):
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO memories (key, value, updated_at)
                   VALUES ($1, $2, NOW())
                   ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()""",
                f"watchdog_incident_{int(time.time())}",
                f"TIME: {datetime.now()}\nDESCRIPTION: {description}\nLOGS:\n{logs[-2000:]}"
            )
    except Exception as e:
        log(f"Nu am putut salva incidentul: {e}")


async def do_rollback(pool):
    log("Incep rollback automat...")
    logs = get_recent_logs(50)
    rolled_back = []

    for module_name in ["api/main.py", "api/chat.py", "api/executor.py", "api/vms.py", "api/jobs.py", "api/backup.py", "api/local_executor.py"]:
        ok = await rollback_file(pool, module_name, "previous")
        if ok:
            rolled_back.append(module_name)

    if rolled_back:
        log(f"Rollback facut pentru: {', '.join(rolled_back)}")
        restart_argos()
        await asyncio.sleep(8)

        if await check_argos_health():
            log("Argos pornit dupa rollback la previous")
            await save_incident(pool, "Rollback la previous reusit", logs)
            return True
        else:
            log("Argos tot nu porneste dupa rollback la previous - incerc LTS")
            for module_name in rolled_back:
                await rollback_file(pool, module_name, "lts")
            restart_argos()
            await asyncio.sleep(8)

            if await check_argos_health():
                log("Argos pornit dupa rollback la LTS")
                await save_incident(pool, "Rollback la LTS reusit", logs)
                return True
            else:
                log("CRITIC: Argos nu porneste nici dupa rollback LTS!")
                await save_incident(pool, "CRITIC: rollback LTS esuat", logs)
                return False
    return False


async def check_file_modifications():
    global last_modification_time
    latest = 0.0
    for path in WATCHED_FILES.values():
        try:
            mtime = os.path.getmtime(path)
            if mtime > latest:
                latest = mtime
        except Exception:
            pass
    if latest > last_modification_time:
        last_modification_time = latest
        return True
    return False


async def main():
    global fail_count, last_modification_time
    log("Watchdog pornit")

    pool = None
    while pool is None:
        try:
            pool = await get_pool()
            log("Conectat la DB")
        except Exception as e:
            log(f"Nu ma pot conecta la DB: {e} - reIncerc in 10s")
            await asyncio.sleep(10)

    # Initializeaza timpul ultimei modificari
    await check_file_modifications()
    recently_modified = False
    last_modify_check = time.time()

    while True:
        await asyncio.sleep(CHECK_INTERVAL)

        # Verifica daca s-a modificat ceva recent
        if await check_file_modifications():
            recently_modified = True
            last_modify_check = time.time()
            log("Modificare detectata - astept grace period")

        # Daca e in grace period dupa modificare, skip verificarea
        if recently_modified and (time.time() - last_modify_check) < GRACE_PERIOD:
            continue

        if recently_modified:
            recently_modified = False

        # Verifica sanatatea Argos
        healthy = await check_argos_health()

        if healthy:
            if fail_count > 0:
                log(f"Argos s-a recuperat dupa {fail_count} esecuri")
            fail_count = 0
        else:
            fail_count += 1
            log(f"Argos nu raspunde ({fail_count}/{FAIL_THRESHOLD})")

            if fail_count >= FAIL_THRESHOLD:
                log("Threshold atins - incerc restart simplu mai intai")
                restart_argos()
                await asyncio.sleep(8)

                if await check_argos_health():
                    log("Argos a pornit dupa restart simplu")
                    fail_count = 0
                else:
                    log("Restart simplu esuat - fac rollback")
                    await do_rollback(pool)
                    fail_count = 0


if __name__ == "__main__":
    asyncio.run(main())
