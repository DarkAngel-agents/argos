#!/usr/bin/env python3
"""
ARGOS Smart Skill Importer
Reads .argosdb files from skills/import/, uses Claude API to categorize,
asks for confirmation, then imports into skills_tree DB.
"""
import os
import sys
import asyncio
import asyncpg
import httpx
import json
import random
import glob
from datetime import datetime

IMPORT_DIR = os.path.expanduser("~/.argos/argos-core/skills/import/")
DONE_DIR = os.path.expanduser("~/.argos/argos-core/skills/import/done/")
DB_HOST = os.getenv("DB_HOST", "11.11.11.111")
DB_PORT = int(os.getenv("DB_PORT", 5433))
DB_USER = os.getenv("DB_USER", "claude")
DB_PASS = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "claudedb")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


def parse_argosdb(filepath: str) -> list[dict]:
    """Parse .argosdb file into list of raw skill dicts."""
    with open(filepath, "r") as f:
        content = f.read()
    
    blocks = content.split("---SKILL---")
    skills = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        skill = {}
        lines = block.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("title:"):
                skill["title"] = line[6:].strip()
            elif line.startswith("context:"):
                skill["context"] = line[8:].strip()
            elif line.startswith("content:"):
                # collect multiline content
                content_lines = []
                i += 1
                while i < len(lines):
                    if lines[i].startswith("  ") or lines[i].startswith("\t") or lines[i] == "":
                        content_lines.append(lines[i].lstrip("  ").lstrip("\t"))
                    else:
                        i -= 1
                        break
                    i += 1
                skill["content"] = "\n".join(content_lines).strip()
            i += 1
        if "title" in skill and "content" in skill:
            skills.append(skill)
    return skills


async def categorize_with_claude(skills: list[dict]) -> list[dict]:
    """Use Claude API to assign path, tags, parent_path, emergency to each skill."""
    if not ANTHROPIC_API_KEY:
        print("No ANTHROPIC_API_KEY — using basic categorization")
        return basic_categorize(skills)

    skills_text = json.dumps([
        {"title": s["title"], "context": s.get("context", ""), "content": s["content"][:200]}
        for s in skills
    ], indent=2)

    prompt = f"""You are categorizing technical skills for ARGOS system.
For each skill, provide: path (hierarchical, e.g. docker/postgres/restart), 
parent_path (one level up), tags (array of lowercase keywords), emergency (bool - true only if needed when DB is unavailable).

Skills to categorize:
{skills_text}

Respond ONLY with a JSON array, one object per skill, in the same order:
[
  {{"path": "category/sub/task", "parent_path": "category/sub", "tags": ["tag1","tag2"], "emergency": false}},
  ...
]
No explanation, just the JSON array."""

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            }
        )
        text = resp.json()["content"][0]["text"].strip()
        import re
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            categories = json.loads(match.group())
            for i, skill in enumerate(skills):
                if i < len(categories):
                    skill.update(categories[i])
    return skills


def basic_categorize(skills: list[dict]) -> list[dict]:
    """Basic categorization without API."""
    for skill in skills:
        title_lower = skill["title"].lower()
        if "docker" in title_lower:
            skill["path"] = "docker/general/" + title_lower.replace(" ", "-")[:30]
            skill["tags"] = ["docker"]
        elif "nixos" in title_lower or "nix" in title_lower:
            skill["path"] = "nixos/general/" + title_lower.replace(" ", "-")[:30]
            skill["tags"] = ["nixos"]
        elif "postgres" in title_lower or "db" in title_lower:
            skill["path"] = "database/general/" + title_lower.replace(" ", "-")[:30]
            skill["tags"] = ["database", "postgres"]
        else:
            skill["path"] = "general/" + title_lower.replace(" ", "-")[:30]
            skill["tags"] = ["general"]
        skill["parent_path"] = "/".join(skill["path"].split("/")[:-1])
        skill["emergency"] = False
    return skills


def generate_id() -> int:
    """Generate unique 8-digit ID."""
    return random.randint(10000000, 99999999)


async def check_id_unique(conn, skill_id: int) -> bool:
    row = await conn.fetchrow("SELECT id FROM skills_tree WHERE id = $1", skill_id)
    return row is None


async def import_skills(skills: list[dict], conn) -> int:
    imported = 0
    for skill in skills:
        skill_id = generate_id()
        while not await check_id_unique(conn, skill_id):
            skill_id = generate_id()

        await conn.execute("""
            INSERT INTO skills_tree (id, path, parent_path, name, tags, source, emergency, usage_count, content)
            VALUES ($1, $2, $3, $4, $5, 'manual', $6, 0, $7)
            ON CONFLICT (path) DO UPDATE SET
                content = EXCLUDED.content,
                tags = EXCLUDED.tags,
                name = EXCLUDED.name,
                source = CASE WHEN skills_tree.source = 'manual' THEN 'manual' ELSE 'manual' END
        """,
            skill_id,
            skill["path"],
            skill.get("parent_path"),
            skill["title"],
            skill.get("tags", []),
            skill.get("emergency", False),
            skill["content"]
        )
        print(f"  + [{skill_id}] {skill['path']}")
        imported += 1
    return imported


async def main():
    os.makedirs(DONE_DIR, exist_ok=True)
    files = glob.glob(os.path.join(IMPORT_DIR, "*.argosdb"))
    
    if not files:
        print("No .argosdb files found in import directory.")
        return

    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASS, database=DB_NAME
    )

    total_imported = 0

    for filepath in sorted(files):
        filename = os.path.basename(filepath)
        print(f"\n{'='*50}")
        print(f"File: {filename}")
        
        skills = parse_argosdb(filepath)
        if not skills:
            print("  No valid skills found, skipping.")
            continue

        print(f"  Found {len(skills)} skills:")
        for i, s in enumerate(skills, 1):
            print(f"  {i}. {s['title']}")

        print("\n  Categorizing with Claude API...")
        try:
            skills = await categorize_with_claude(skills)
        except Exception as e:
            print(f"  Claude API failed: {e}, using basic categorization")
            skills = basic_categorize(skills)

        print("\n  Categorized as:")
        for s in skills:
            print(f"  - {s['path']}")
            print(f"    tags: {s.get('tags', [])}")
            print(f"    emergency: {s.get('emergency', False)}")

        confirm = input(f"\n  Import these {len(skills)} skills? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("  Skipped.")
            continue

        imported = await import_skills(skills, conn)
        total_imported += imported
        print(f"  Imported {imported} skills.")

        # Move to done
        done_path = os.path.join(DONE_DIR, filename)
        os.rename(filepath, done_path)
        print(f"  Moved to done/")

    await conn.close()
    print(f"\nTotal imported: {total_imported} skills")


if __name__ == "__main__":
    asyncio.run(main())
