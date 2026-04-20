"""
TASK 01 - Script de sprijin

Face recon pe:
1. Skill-urile cheie de self-knowledge
2. Starea reala a sistemului (disk paths, DB)
3. Diferentele declarate vs reale

Output: text structurat pe stdout. Claude Code citeste si scrie MD report.
Read-only. Ruleaza in container (are asyncpg + acces DB).
Docker checks rulate separat pe host de Claude Code.
"""
import asyncio
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import connect_db, header, section, truncate, ARGOS_CORE

TARGET_SKILLS = [
    "argos-self-knowledge",
    "argos-output-patterns",
    "skill-creation-protocol",
    "argos-agent-loop-architecture",
    "argos-health-check-and-status",
    "argos-service-restart-correct-method",
    "argos-build-and-deploy",
]

EXPECTED_PATHS = [
    "/home/darkangel/.argos/argos-core",
    "/home/darkangel/.argos/argos-core/agent",
    "/home/darkangel/.argos/argos-core/api",
    "/home/darkangel/.argos/argos-core/llm",
    "/home/darkangel/.argos/argos-core/ui",
    "/home/darkangel/.argos/argos-core/tools",
    "/home/darkangel/.argos/argos-core/skills",
    "/home/darkangel/.argos/argos-core/config",
    "/home/darkangel/.argos/argos-core/config/.env",
    "/home/darkangel/.argos/docker/swarm-stack.yml",
    "/home/darkangel/.argos/docker/Dockerfile",
]

async def main():
    header("TASK 01 - Self-knowledge skills + Reality check")

    conn = await connect_db()

    section("1.1 Total skills count")
    total = await conn.fetchval("SELECT COUNT(*) FROM skills_tree")
    emergency = await conn.fetchval("SELECT COUNT(*) FROM skills_tree WHERE emergency = true")
    verified = await conn.fetchval("SELECT COUNT(*) FROM skills_tree WHERE verified = true")
    print("  Total skills:    " + str(total))
    print("  Emergency:       " + str(emergency))
    print("  Verified:        " + str(verified))
    print("  Unverified:      " + str(total - verified))

    section("1.2 Target skills (self-knowledge family)")
    for target in TARGET_SKILLS:
        row = await conn.fetchrow(
            "SELECT id, path, name, length(content) as clen, emergency, verified, updated_at FROM skills_tree WHERE path ILIKE $1 OR name ILIKE $1",
            "%" + target + "%"
        )
        if row:
            print("  [FOUND] id=" + str(row["id"]).ljust(4) + " len=" + str(row["clen"]).ljust(6) + " emerg=" + str(row["emergency"])[0] + " ver=" + str(row["verified"])[0] + " | " + row["path"])
            print("          name: " + truncate(row["name"], 60))
            print("          updated: " + str(row["updated_at"]))
        else:
            print("  [MISSING] " + target)

    section("1.3 Emergency skills list")
    rows = await conn.fetch(
        "SELECT id, path, name, length(content) as clen FROM skills_tree WHERE emergency = true ORDER BY id"
    )
    for r in rows:
        print("  [" + str(r["id"]).rjust(4) + "] " + str(r["clen"]).rjust(6) + " chars | " + truncate(r["path"], 60))

    section("1.4 Recent skills (last 15 updated)")
    rows = await conn.fetch(
        "SELECT id, path, length(content) as clen, updated_at FROM skills_tree ORDER BY updated_at DESC NULLS LAST LIMIT 15"
    )
    for r in rows:
        print("  [" + str(r["id"]).rjust(4) + "] " + str(r["clen"]).rjust(6) + " chars | " + str(r["updated_at"])[:19] + " | " + truncate(r["path"], 50))

    section("1.5 Content preview for argos-self-knowledge")
    row = await conn.fetchrow(
        "SELECT id, path, content FROM skills_tree WHERE path ILIKE $1 OR name ILIKE $1 LIMIT 1",
        "%self-knowledge%"
    )
    if row:
        content = row["content"] or ""
        print("  id=" + str(row["id"]) + " path=" + row["path"])
        print("  === first 3000 chars ===")
        print(content[:3000])
        if len(content) > 3000:
            print("  === [truncated, total " + str(len(content)) + " chars] ===")
    else:
        print("  [MISSING] no argos-self-knowledge skill found")

    await conn.close()

    section("2.1 Expected paths on disk")
    for path in EXPECTED_PATHS:
        exists = os.path.exists(path)
        mark = "[OK]  " if exists else "[MISSING]"
        if exists:
            try:
                st = os.stat(path)
                size = st.st_size
                if os.path.isdir(path):
                    print(mark + " DIR  " + path)
                else:
                    print(mark + " FILE " + path + " (" + str(size) + " bytes)")
            except:
                print(mark + "      " + path)
        else:
            print(mark + " " + path)

    section("2.2 argos-core directory structure (top level)")
    try:
        entries = sorted(os.listdir(ARGOS_CORE))
        for e in entries:
            full = os.path.join(ARGOS_CORE, e)
            if os.path.isdir(full):
                print("  DIR  " + e)
            else:
                size = os.path.getsize(full)
                if size == 0:
                    print("  FILE " + e + " [EMPTY]")
                else:
                    print("  FILE " + e + " (" + str(size) + " bytes)")
    except Exception as e:
        print("  ERR: " + str(e))

    section("2.3 Python files count per subdir")
    subdirs = ["agent", "api", "llm", "ui", "tools", "skills", "reasoning"]
    for sd in subdirs:
        path = os.path.join(ARGOS_CORE, sd)
        if not os.path.exists(path):
            print("  " + sd.ljust(12) + ": [MISSING]")
            continue
        try:
            result = subprocess.run(
                ["find", path, "-name", "*.py", "-type", "f"],
                capture_output=True, text=True, timeout=10
            )
            files = [l for l in result.stdout.split("\n") if l.strip()]
            total_lines = 0
            for f in files:
                try:
                    with open(f) as fh:
                        total_lines += sum(1 for _ in fh)
                except:
                    pass
            print("  " + sd.ljust(12) + ": " + str(len(files)).rjust(3) + " files, " + str(total_lines).rjust(6) + " lines")
        except Exception as e:
            print("  " + sd + ": ERR " + str(e)[:40])

    section("2.4 Env file check (config/.env)")
    env_path = ARGOS_CORE + "/config/.env"
    if os.path.exists(env_path):
        try:
            with open(env_path) as f:
                lines = f.readlines()
            print("  [OK] " + env_path + " (" + str(len(lines)) + " lines)")
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    if any(w in k.upper() for w in ["KEY", "TOKEN", "PASSWORD", "SECRET"]):
                        v_masked = v[:8] + "..." + v[-8:] if len(v) > 20 else "***"
                        print("    " + k + "=" + v_masked)
                    else:
                        print("    " + k + "=" + truncate(v, 60))
        except Exception as e:
            print("  ERR reading: " + str(e))
    else:
        print("  [MISSING] " + env_path)

    section("3.1 Docker check")
    print("  [SKIPPED] Docker client not available in container.")
    print("  Run on host (Beasty): docker ps --filter name=argos")
    print("  Run on Hermes (swarm manager): ssh root@11.11.11.98 docker service ls")

    print()
    print("=" * 70)
    print(" END TASK 01 RECON")
    print("=" * 70)

asyncio.run(main())
