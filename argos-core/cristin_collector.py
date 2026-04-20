#!/usr/bin/env python3.13
"""
Argos Cristin Collector - colecteaza date din UniFi la 5 minute
Ruleaza ca serviciu systemd pe Beasty
"""
import asyncio
import asyncpg
import httpx
import json
import os
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/.argos/argos-core/config/.env"))

UNIFI_URL = "https://192.168.1.1"
UNIFI_KEY = os.getenv("UNIFI_KEY")
INTERVAL  = 300  # 5 minute
KEEP_DAYS = 3

DB_CONF = {
    "host": os.getenv("DB_HOST", "11.11.11.111"),
    "port": int(os.getenv("DB_PORT", 5433)),
    "user": os.getenv("DB_USER", "claude"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME", "claudedb"),
    "ssl": False
}


async def unifi_get(client: httpx.AsyncClient, path: str) -> dict:
    try:
        r = await client.get(f"{UNIFI_URL}{path}",
                             headers={"X-API-KEY": UNIFI_KEY},
                             timeout=15)
        return r.json()
    except Exception as e:
        print(f"[CRISTIN] UniFi error {path}: {e}")
        return {}


async def collect(pool: asyncpg.Pool):
    async with httpx.AsyncClient(verify=False) as client:
        # 1. Clienti conectati
        sta = await unifi_get(client, "/proxy/network/api/s/default/stat/sta")
        devices = sta.get("data", [])

        # 2. Evenimente UniFi
        events = await unifi_get(client, "/proxy/network/api/s/default/stat/event?within=1&_limit=200")
        ev_list = events.get("data", [])

        now = datetime.now()

        async with pool.acquire() as conn:
            # Snapshot device history
            for d in devices:
                mac = d.get("mac")
                if not mac:
                    continue
                ip   = d.get("ip") or d.get("last_ip") or ""
                tx   = d.get("wired-tx_bytes") or d.get("tx_bytes") or 0
                rx   = d.get("wired-rx_bytes") or d.get("rx_bytes") or 0
                sat  = d.get("satisfaction") or 0
                sig  = d.get("rssi") or d.get("signal") or 0
                uptime = d.get("uptime") or d.get("_uptime_by_ugw") or 0

                await conn.execute(
                    """INSERT INTO cristin.device_history
                       (mac, ip, status, uptime_seconds, tx_bytes, rx_bytes, signal, satisfaction, recorded_at)
                       VALUES ($1, $2, 'online', $3, $4, $5, $6, $7, NOW())""",
                    mac, ip, uptime, tx, rx, sig, sat
                )

                # Update device last_seen si ip
                await conn.execute(
                    """INSERT INTO cristin.devices (mac, ip, last_seen)
                       VALUES ($1, $2, NOW())
                       ON CONFLICT (mac) DO UPDATE SET ip=$2, last_seen=NOW()""",
                    mac, ip
                )

            # Salveaza evenimente
            for ev in ev_list:
                key      = ev.get("key", "")
                msg      = ev.get("msg", "") or ev.get("message", "")
                mac      = ev.get("client") or ev.get("sta_mac") or ""
                ip       = ev.get("host") or ""
                ts       = ev.get("datetime") or ev.get("timestamp")
                cat      = "info"
                severity = "info"

                # Clasificare
                if any(x in key.lower() for x in ["disconnect", "down", "fail", "error"]):
                    cat = "connectivity"; severity = "bad"
                elif any(x in key.lower() for x in ["dhcp", "lease", "ip"]):
                    cat = "dhcp"
                    severity = "warning" if "conflict" in key.lower() else "good"
                elif any(x in key.lower() for x in ["connect", "up", "assoc"]):
                    cat = "connectivity"; severity = "good"
                elif any(x in key.lower() for x in ["warn", "alert"]):
                    cat = "warning"; severity = "warning"
                elif any(x in key.lower() for x in ["block", "threat", "attack"]):
                    cat = "security"; severity = "critical"

                # Evita duplicate (acelasi msg in ultimul minut)
                exists = await conn.fetchval(
                    """SELECT 1 FROM cristin.events
                       WHERE message=$1 AND recorded_at > NOW() - INTERVAL '1 minute'
                       LIMIT 1""",
                    msg
                )
                if not exists and msg:
                    await conn.execute(
                        """INSERT INTO cristin.events
                           (mac, ip, category, severity, message, raw_data, source)
                           VALUES ($1, $2, $3, $4, $5, $6, 'unifi')""",
                        mac, ip, cat, severity, msg, json.dumps(ev)
                    )

            # Curata date mai vechi de 3 zile
            cutoff = now - timedelta(days=KEEP_DAYS)
            deleted_h = await conn.fetchval(
                "DELETE FROM cristin.device_history WHERE recorded_at < $1", cutoff
            )
            deleted_e = await conn.fetchval(
                "DELETE FROM cristin.events WHERE recorded_at < $1 AND severity NOT IN ('bad','critical')", cutoff
            )

        online = len(devices)
        print(f"[CRISTIN] {now.strftime('%H:%M:%S')} — {online} devices, {len(ev_list)} events")


async def main():
    print("[CRISTIN] Collector pornit")
    pool = await asyncpg.create_pool(**DB_CONF)

    while True:
        try:
            await collect(pool)
        except Exception as e:
            print(f"[CRISTIN] Eroare colectare: {e}")
        await asyncio.sleep(INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
