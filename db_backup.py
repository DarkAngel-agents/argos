#!/usr/bin/env python3.13
"""
Daily PostgreSQL claudedb backup + cleanup older than 7 days
"""
import asyncio, asyncpg, os, subprocess, gzip, shutil
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/.argos/argos-core/config/.env"))

BACKUP_DIR = os.path.expanduser("~/.argos/backups/db")
KEEP_DAYS  = 7

async def main():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    now  = datetime.now()
    name = f"claudedb_{now.strftime('%Y%m%d_%H%M%S')}.sql.gz"
    path = os.path.join(BACKUP_DIR, name)

    env = os.environ.copy()
    env["PGPASSWORD"] = os.getenv("DB_PASSWORD", "")

    print(f"[DB_BACKUP] Dump → {path}")
    with gzip.open(path, 'wb') as f:
        proc = subprocess.run(
            ["pg_dump", "-h", os.getenv("DB_HOST","11.11.11.111"),
             "-U", os.getenv("DB_USER","claude"),
             "-d", os.getenv("DB_NAME","claudedb")],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
        )
        if proc.returncode != 0:
            print(f"[DB_BACKUP] EROARE: {proc.stderr.decode()}")
            return
        f.write(proc.stdout)

    size = os.path.getsize(path) / 1024 / 1024
    print(f"[DB_BACKUP] OK — {size:.1f}MB")

    # Delete old backups
    cutoff = now - timedelta(days=KEEP_DAYS)
    for f in os.listdir(BACKUP_DIR):
        fp = os.path.join(BACKUP_DIR, f)
        if os.path.getmtime(fp) < cutoff.timestamp():
            os.remove(fp)
            print(f"[DB_BACKUP] Deleted old: {f}")

if __name__ == "__main__":
    asyncio.run(main())
