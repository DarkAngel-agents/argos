#!/usr/bin/env python3.13
"""
Parser configuration.nix - indexeaza zonele in DB
Ruleaza dupa orice modificare a configuration.nix
"""
import asyncio
import asyncpg
import os
import re
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/.argos/argos-core/config/.env"))

NIXOS_CONFIG = "/etc/nixos/configuration.nix"


def parse_config(content: str) -> list:
    """Parcurge fisierul si extrage zonele cu tagurile lor"""
    zones = []
    lines = content.splitlines()
    current_zone = None
    zone_start = None

    for i, line in enumerate(lines, start=1):
        # Detecteaza linie cu @zone
        if "@zone:" in line:
            # Inchide zona anterioara
            if current_zone:
                current_zone["line_end"] = i - 1
                zones.append(current_zone)

            # Extrage toate tagurile din linie
            tags = {}
            for match in re.finditer(r'@(\w[\w-]*):([\w:/.-]+)', line):
                tags[match.group(1)] = match.group(2)

            zone_name = tags.get("zone", "unknown")
            managed = tags.get("managed", "human")
            critical = tags.get("critical", "false").lower() == "true"
            restart = tags.get("restart", None)

            current_zone = {
                "zone": zone_name,
                "managed_by": managed,
                "critical": critical,
                "restart_required": restart,
                "line_start": i,
                "line_end": None,
                "tags": tags,
                "description": line.strip().lstrip("#").strip()
            }
            zone_start = i

    # Inchide ultima zona
    if current_zone:
        current_zone["line_end"] = len(lines)
        zones.append(current_zone)

    return zones


async def update_index(pool, zones: list):
    """Sterge indexul vechi si insereaza cel nou"""
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM config_index")
        for z in zones:
            await conn.execute(
                """INSERT INTO config_index
                   (zone, managed_by, critical, restart_required, line_start, line_end, tags, description, updated_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())""",
                z["zone"], z["managed_by"], z["critical"],
                z["restart_required"], z["line_start"], z["line_end"],
                json.dumps(z["tags"]), z["description"]
            )
        count = await conn.fetchval("SELECT COUNT(*) FROM config_index")
    return count


async def main():
    if not os.path.exists(NIXOS_CONFIG):
        print(f"Nu gasesc {NIXOS_CONFIG}")
        return

    with open(NIXOS_CONFIG, "r") as f:
        content = f.read()

    zones = parse_config(content)
    print(f"Gasit {len(zones)} zone in configuration.nix")

    pool = await asyncpg.create_pool(
        host=os.getenv("DB_HOST"), port=int(os.getenv("DB_PORT", 5432)),
        user=os.getenv("DB_USER"), password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"), ssl=False
    )

    count = await update_index(pool, zones)
    print(f"Index actualizat: {count} inregistrari")

    # Afiseaza rezumat
    for z in sorted(zones, key=lambda x: x["line_start"]):
        managed = z["managed_by"]
        critical = "⚠" if z["critical"] else " "
        restart = f"→{z['restart_required']}" if z["restart_required"] else ""
        print(f"  {critical} L{z['line_start']:3}-{z['line_end']:3} [{managed:12}] @zone:{z['zone']} {restart}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
