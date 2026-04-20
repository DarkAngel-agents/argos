#!/usr/bin/env python3
"""
ARGOS Skill Importer
Imports YAML skills from ~/.argos/argos-core/skills/manual/ into skills_tree DB table.
- Skips files already imported (checks by id)
- Manual skills have priority over auto skills on same path
- Never deletes existing manual skills
"""
import os
import asyncio
import asyncpg
import yaml
import glob

SKILLS_DIR = os.path.expanduser("~/.argos/argos-core/skills/manual/")
DB_HOST = "11.11.11.111"
DB_PORT = int(os.getenv("DB_PORT", 5433))
DB_USER = "claude"
DB_PASS = os.getenv("DB_PASSWORD")
DB_NAME = "claudedb"

async def import_skills():
    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASS, database=DB_NAME
    )

    files = glob.glob(os.path.join(SKILLS_DIR, "*.yaml"))
    imported = 0
    skipped = 0
    errors = 0

    for filepath in sorted(files):
        filename = os.path.basename(filepath)
        if filename.startswith("SKILL_CREATOR"):
            continue
        try:
            with open(filepath, "r") as f:
                skill = yaml.safe_load(f)

            required = ["id", "path", "name", "tags", "content"]
            missing = [k for k in required if k not in skill]
            if missing:
                print(f"SKIP {filename}: missing fields {missing}")
                skipped += 1
                continue

            existing = await conn.fetchrow(
                "SELECT id, source FROM skills_tree WHERE id = $1", int(skill["id"])
            )
            if existing:
                if existing["source"] == "manual":
                    print(f"SKIP {filename}: already imported (id={skill['id']})")
                    skipped += 1
                    continue
                else:
                    await conn.execute("DELETE FROM skills_tree WHERE id = $1", int(skill["id"]))

            path_conflict = await conn.fetchrow(
                "SELECT id, source FROM skills_tree WHERE path = $1 AND source = 'auto'",
                skill["path"]
            )
            if path_conflict:
                print(f"NOTE {filename}: auto skill exists on path {skill['path']} — manual takes priority")

            await conn.execute("""
                INSERT INTO skills_tree (id, path, parent_path, name, tags, source, emergency, usage_count, content)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (path) DO UPDATE SET
                  content = EXCLUDED.content,
                  tags = EXCLUDED.tags,
                  name = EXCLUDED.name,
                  source = CASE WHEN skills_tree.source = 'manual' THEN 'manual' ELSE EXCLUDED.source END
            """,
                int(skill["id"]),
                skill["path"],
                skill.get("parent_path"),
                skill["name"],
                skill["tags"],
                skill.get("source", "manual"),
                skill.get("emergency", False),
                skill.get("usage_count", 0),
                skill["content"]
            )
            print(f"OK {filename}: {skill['path']}")
            imported += 1

        except Exception as e:
            print(f"ERROR {filename}: {e}")
            errors += 1

    await conn.close()
    print(f"\nDone: {imported} imported, {skipped} skipped, {errors} errors")

if __name__ == "__main__":
    asyncio.run(import_skills())
