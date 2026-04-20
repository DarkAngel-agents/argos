#!/usr/bin/env python3
"""
ARGOS Heartbeat Daemon
Runs on every node, reports state every 2 seconds to DB.
On DB failure: writes local emergency log + tries HTTP to Hermes.
"""
import os, time, json, socket, subprocess, asyncio
import asyncpg
import httpx
from datetime import datetime
import shutil as _shutil

def _bin(name):
    """Find binary: NixOS path first, then PATH lookup, then fallback."""
    nix = f"/run/current-system/sw/bin/{name}"
    if os.path.isfile(nix):
        return nix
    found = _shutil.which(name)
    return found or name

NODE = socket.gethostname().lower()
DB_HOST = os.getenv("DB_HOST", "11.11.11.111")
DB_PORT = int(os.getenv("DB_PORT", 5433))
DB_USER = os.getenv("DB_USER", "claude")
DB_PASS = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "claudedb")
ARGOS_URL = "http://11.11.11.111:666"
HERMES_URL = "http://11.11.11.98:666"
EMERGENCY_LOG = "/tmp/heartbeat_emergency.log"
INTERVAL = 2
PING_INTERVAL = 30
_last_ping = 0

async def ping_fleet(pool):
    """Ping all system_profiles IPs, update online status."""
    import subprocess
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, ip FROM system_profiles WHERE active = TRUE AND ip IS NOT NULL"
        )
        for r in rows:
            ip = r['ip']
            name = r['name']
            if name == NODE:
                continue  # skip self, already updated by heartbeat
            try:
                rc = subprocess.run(
                    [_bin("ping"), "-c", "1", "-W", "2", ip],
                    capture_output=True, timeout=5
                ).returncode
                online = (rc == 0)
            except:
                online = False
            await conn.execute(
                "UPDATE system_profiles SET online = $1, last_seen = CASE WHEN $1 THEN NOW() ELSE last_seen END WHERE id = $2",
                online, r['id']
            )

# Error codes catalog
CODES = {
    "DB_TIMEOUT":     "HB001",
    "DB_UNREACHABLE": "HB002",
    "GPU_UNAVAILABLE":"HB003",
    "SWARM_SPLIT":    "HB004",
    "HIGH_CPU":       "HB005",
    "HIGH_MEM":       "HB006",
    "CONTAINER_DOWN": "HB007",
    "ARGOS_DOWN":     "HB008",
}

def get_cpu():
    try:
        with open("/proc/stat") as f:
            line = f.readline()  # cpu  user nice system idle ...
        vals = [int(x) for x in line.split()[1:]]
        idle = vals[3]
        total = sum(vals)
        # Compare with previous reading
        if not hasattr(get_cpu, '_prev'):
            get_cpu._prev = (idle, total)
            return 0.0
        prev_idle, prev_total = get_cpu._prev
        get_cpu._prev = (idle, total)
        d_idle = idle - prev_idle
        d_total = total - prev_total
        if d_total == 0:
            return 0.0
        return round(100.0 * (1.0 - d_idle / d_total), 1)
    except:
        return -1

def get_mem():
    try:
        r = subprocess.run([_bin("free"),"-m"], capture_output=True, text=True, timeout=3)
        for l in r.stdout.splitlines():
            if l.startswith("Mem:"):
                parts = l.split()
                total, used = float(parts[1]), float(parts[2])
                return round(used/total*100, 1)
        return -1
    except: return -1

def get_containers():
    try:
        r = subprocess.run([_bin("docker"),"ps","--format","{{.Names}}"], capture_output=True, text=True, timeout=3)
        return len([l for l in r.stdout.splitlines() if l.strip()])
    except: return -1

async def db_latency(pool):
    try:
        t = time.time()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return int((time.time()-t)*1000)
    except: return -1

async def write_to_db(pool, state):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO heartbeat_log 
            (node, service, status, cpu_pct, mem_pct, db_latency_ms, containers_up, error_code, error_msg)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        """, state['node'], state['service'], state['status'],
            state['cpu'], state['mem'], state['db_latency'],
            state['containers'], state.get('error_code'), state.get('error_msg'))
        # Update system_profiles online status
        await conn.execute(
            """UPDATE system_profiles SET online = TRUE, last_seen = NOW()
               WHERE LOWER(name) = $1 AND active = TRUE""",
            state['node']
        )

def write_emergency(state):
    with open(EMERGENCY_LOG, 'a') as f:
        f.write(json.dumps(state) + "\n")
    # Keep only last 30 lines
    try:
        with open(EMERGENCY_LOG) as f: lines = f.readlines()
        if len(lines) > 30:
            with open(EMERGENCY_LOG, 'w') as f: f.writelines(lines[-30:])
    except: pass

async def notify_hermes(state):
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            await c.post(f"{HERMES_URL}/api/heartbeat", json=state)
    except: pass

async def main():
    print(f"[HEARTBEAT] Starting on {NODE}", flush=True)
    pool = None
    consecutive_db_fails = 0

    while True:
        try:
            # Connect/reconnect pool
            if pool is None:
                try:
                    pool = await asyncpg.create_pool(
                        host=DB_HOST, port=DB_PORT,
                        user=DB_USER, password=DB_PASS, database=DB_NAME,
                        min_size=1, max_size=2,
                        max_inactive_connection_lifetime=20,
                        command_timeout=3
                    )
                    consecutive_db_fails = 0
                    print(f"[HEARTBEAT] DB connected", flush=True)
                except Exception as e:
                    pool = None
                    consecutive_db_fails += 1

            cpu = get_cpu()
            mem = get_mem()
            containers = get_containers()
            db_lat = await db_latency(pool) if pool else -1

            # Determine status and error codes
            status = "ok"
            error_code = None
            error_msg = None

            if cpu > 90:
                status = "warning"
                error_code = CODES["HIGH_CPU"]
                error_msg = f"CPU {cpu}%"
            if mem > 90:
                status = "warning"
                error_code = CODES["HIGH_MEM"]
                error_msg = f"MEM {mem}%"
            if db_lat == -1:
                status = "error"
                error_code = CODES["DB_UNREACHABLE"]
                error_msg = "DB unreachable"
            elif db_lat > 500:
                status = "warning"
                error_code = CODES["DB_TIMEOUT"]
                error_msg = f"DB latency {db_lat}ms"
            if containers == 0 and NODE != "hermes":
                status = "critical"
                error_code = CODES["CONTAINER_DOWN"]
                error_msg = "No containers running"

            state = {
                "node": NODE, "service": "argos-node",
                "status": status, "cpu": cpu, "mem": mem,
                "db_latency": db_lat, "containers": containers,
                "error_code": error_code, "error_msg": error_msg,
                "ts": datetime.now().isoformat()
            }

            # Write to DB
            if pool:
                try:
                    await write_to_db(pool, state)
                    consecutive_db_fails = 0
                except Exception as e:
                    consecutive_db_fails += 1
                    pool = None
                    write_emergency(state)
                    await notify_hermes(state)
                    print(f"[HEARTBEAT] DB write failed: {e}", flush=True)
            else:
                write_emergency(state)
                await notify_hermes(state)

            # Ping fleet (doar pe beasty, la fiecare 30s)
            import time as _t
            global _last_ping
            if NODE == 'beasty' and _t.time() - _last_ping > PING_INTERVAL:
                try:
                    if pool:
                        await ping_fleet(pool)
                except Exception as e:
                    print(f"[HEARTBEAT] ping_fleet error: {e}", flush=True)
                _last_ping = _t.time()

            # Alert on critical
            if status in ("error", "critical"):
                print(f"[HEARTBEAT] {error_code} {error_msg}", flush=True)

        except Exception as e:
            print(f"[HEARTBEAT] Loop error: {e}", flush=True)

        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
