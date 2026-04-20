#!/usr/bin/env python3.13
"""
Auto-arhivare conversatii inactive cu rezumat generat de qwen3 local.
Ruleaza zilnic. Arhiveaza conversatii inactive > X zile.
"""
import asyncio
import asyncpg
import httpx
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/.argos/argos-core/config/.env"))

INACTIVE_DAYS = 3       # arhiveaza dupa 3 zile inactivitate
MIN_MESSAGES  = 3       # minim 3 mesaje ca sa merite arhivat
OLLAMA_URL    = "http://172.17.0.1:11435/api/generate"
OLLAMA_MODEL  = "qwen3:14b"

DB_CONF = {
    "host": os.getenv("DB_HOST", "11.11.11.111"),
    "port": int(os.getenv("DB_PORT", 5433)),
    "user": os.getenv("DB_USER", "claude"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME", "claudedb"),
    "ssl": False
}

ARCHIVE_TAGS_MAP = {
    "nixos": ["nixos", "nix-build", "nixos-rebuild", "configuration.nix"],
    "proxmox": ["proxmox", "qm ", "vm ", "lxc", "pct "],
    "unifi": ["unifi", "udm", "switch", "vlan", "dhcp"],
    "nanite": ["nanite", "iso", "boot"],
    "home-assistant": ["home assistant", "ha ", "automatizar"],
    "arduino": ["esp32", "esphome", "arduino", "sensor"],
    "networking": ["firewall", "port forward", "wireguard", "vpn"],
    "argos": ["argos", "chat.py", "main.py", "backup"],
    "database": ["postgresql", "psql", "claudedb", "schema"],
    "programming": ["python", "bash", "javascript", "react"],
}


def detect_tags(text: str) -> list:
    text_lower = text.lower()
    tags = []
    for tag, keywords in ARCHIVE_TAGS_MAP.items():
        if any(kw in text_lower for kw in keywords):
            tags.append(tag)
    return tags[:5]  # max 5 taguri


async def generate_summary(messages: list) -> str:
    """Genereaza rezumat scurt cu qwen3 local"""
    # Construieste textul conversatiei
    conv_text = ""
    for m in messages[:20]:  # max 20 mesaje pentru rezumat
        role = "USER" if m["role"] == "user" else "ARGOS"
        content = str(m["content"])[:300]
        conv_text += f"{role}: {content}\n"

    prompt = f"""Rezuma aceasta conversatie tehnica in maxim 150 cuvinte.
Format: 
PROBLEMA: [ce problema s-a rezolvat sau ce s-a facut]
SOLUTIE: [ce s-a implementat sau cum s-a rezolvat]
COMENZI_CHEIE: [max 3 comenzi importante daca exista]

Conversatie:
{conv_text}

Raspunde DOAR cu rezumatul, fara alte explicatii."""

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                OLLAMA_URL,
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
                timeout=120
            )
            return r.json().get("response", "")[:800]
    except Exception as e:
        return f"[Rezumat indisponibil: {e}]"


async def auto_archive(pool: asyncpg.Pool):
    cutoff = datetime.now() - timedelta(days=INACTIVE_DAYS)

    async with pool.acquire() as conn:
        # Conversatii inactive fara arhivare existenta
        conversations = await conn.fetch(
            """SELECT c.id, c.title, c.updated_at,
                      COUNT(m.id) as msg_count,
                      STRING_AGG(m.content, ' ' ORDER BY m.created_at) as all_content
               FROM conversations c
               JOIN messages m ON m.conversation_id = c.id
               WHERE c.updated_at < $1
               AND m.pending = FALSE
               AND NOT EXISTS (
                   SELECT 1 FROM conversation_archives a
                   WHERE a.conversation_id = c.id
               )
               GROUP BY c.id, c.title, c.updated_at
               HAVING COUNT(m.id) >= $2
               ORDER BY c.updated_at ASC
               LIMIT 20""",
            cutoff, MIN_MESSAGES
        )

    if not conversations:
        print("[AUTOARCHIVE] Nimic de arhivat")
        return

    print(f"[AUTOARCHIVE] {len(conversations)} conversatii de arhivat")

    for conv in conversations:
        conv_id = conv["id"]
        title   = conv["title"] or f"Conversatie #{conv_id}"
        content = conv["all_content"] or ""

        # Detectie taguri
        tags = detect_tags(content)
        if not tags:
            tags = ["argos"]

        # Incarca mesajele pentru rezumat
        async with pool.acquire() as conn:
            messages = await conn.fetch(
                """SELECT role, content FROM messages
                   WHERE conversation_id = $1 AND pending = FALSE
                   ORDER BY created_at ASC""",
                conv_id
            )

        msgs = [{"role": r["role"], "content": r["content"]} for r in messages]

        # Genereaza rezumat
        print(f"[AUTOARCHIVE] Arhivez: {title[:50]} ({len(msgs)} mesaje, taguri: {tags})")
        summary = await generate_summary(msgs)

        # Salveaza arhivarea
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO conversation_archives (conversation_id, title, summary, tags, created_at, updated_at)
                   VALUES ($1, $2, $3, $4, NOW(), NOW())
                   ON CONFLICT DO NOTHING""",
                conv_id, title, summary, tags
            )

            # Sterge mesajele brute (pastreaza primul si ultimul)
            await conn.execute(
                """DELETE FROM messages
                   WHERE conversation_id = $1
                   AND id NOT IN (
                       SELECT id FROM messages WHERE conversation_id = $1
                       ORDER BY created_at ASC LIMIT 1
                   )
                   AND id NOT IN (
                       SELECT id FROM messages WHERE conversation_id = $1
                       ORDER BY created_at DESC LIMIT 1
                   )""",
                conv_id
            )

        print(f"[AUTOARCHIVE] ✓ {title[:50]} → taguri: {tags}")

    print("[AUTOARCHIVE] Gata")


async def vacuum_old_data(pool: asyncpg.Pool):
    """Sterge date vechi din cristin schema"""
    cutoff = datetime.now() - timedelta(days=3)
    async with pool.acquire() as conn:
        dh = await conn.fetchval(
            "SELECT COUNT(*) FROM cristin.device_history WHERE recorded_at < $1", cutoff
        )
        if dh:
            await conn.execute(
                "DELETE FROM cristin.device_history WHERE recorded_at < $1", cutoff
            )
            print(f"[VACUUM] Sterse {dh} randuri vechi din cristin.device_history")

        ev = await conn.fetchval(
            "SELECT COUNT(*) FROM cristin.events WHERE recorded_at < $1 AND severity NOT IN ('bad','critical')",
            cutoff
        )
        if ev:
            await conn.execute(
                "DELETE FROM cristin.events WHERE recorded_at < $1 AND severity NOT IN ('bad','critical')",
                cutoff
            )
            print(f"[VACUUM] Sterse {ev} evenimente vechi din cristin.events")

        # Sterge log entries vechi de 7 zile
        logs = await conn.fetchval(
            "SELECT COUNT(*) FROM log_entries WHERE created_at < NOW() - INTERVAL '7 days'"
        )
        if logs:
            await conn.execute(
                "DELETE FROM log_entries WHERE created_at < NOW() - INTERVAL '7 days'"
            )
            print(f"[VACUUM] Sterse {logs} log entries vechi")


async def main():
    pool = await asyncpg.create_pool(**DB_CONF)
    await auto_archive(pool)
    await vacuum_old_data(pool)
    await pool.close()
    print("[AUTOARCHIVE] Complet")


if __name__ == "__main__":
    asyncio.run(main())
