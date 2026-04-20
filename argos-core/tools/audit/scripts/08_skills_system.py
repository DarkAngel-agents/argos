"""
TASK 08 - Skills system deep audit

Read-only. Analyzes:
- skills_tree content quality (stubs, never updated, length distribution)
- Legacy skills table (25 rows from task 04) - what's there?
- Skill content patterns (markdown structure, code blocks, refs)
- Skill loading flow in chat.py (_score_skill, _detect_and_load_skills)
- Skill referenced in code but missing from DB
- Skill creation protocol (#93 meta-skill)
- Skill version drift (referenced features vs actual content)
"""
import asyncio
import os
import re
import sys
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import connect_db, header, section, truncate, ARGOS_CORE


SKILL_REF_PATTERN = re.compile(r"skill[\s_-]?#?(\d{1,3})", re.IGNORECASE)


async def section_01_skills_tree_overview(conn):
    section("8.1 skills_tree overview")
    total = await conn.fetchval("SELECT COUNT(*) FROM skills_tree")
    print("  Total skills: " + str(total))

    # Schema columns
    cols = await conn.fetch(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = $1 ORDER BY ordinal_position",
        "skills_tree"
    )
    print()
    print("  Columns:")
    for c in cols:
        print("    " + c["column_name"].ljust(20) + " " + c["data_type"])

    # Stats
    stats = await conn.fetchrow(
        "SELECT MIN(length(content)) as min_len, MAX(length(content)) as max_len, "
        "AVG(length(content))::int as avg_len, SUM(length(content)) as total_chars "
        "FROM skills_tree"
    )
    print()
    print("  Content stats:")
    print("    min length: " + str(stats["min_len"]))
    print("    max length: " + str(stats["max_len"]))
    print("    avg length: " + str(stats["avg_len"]))
    print("    total chars: " + str(stats["total_chars"]))


async def section_02_length_distribution(conn):
    section("8.2 Length distribution buckets")
    buckets = [
        (0, 100, "tiny <100"),
        (100, 300, "stub 100-300"),
        (300, 500, "short 300-500"),
        (500, 1000, "medium 500-1k"),
        (1000, 3000, "long 1k-3k"),
        (3000, 8000, "large 3k-8k"),
        (8000, 100000, "huge >8k"),
    ]
    for lo, hi, label in buckets:
        n = await conn.fetchval(
            "SELECT COUNT(*) FROM skills_tree WHERE length(content) >= $1 AND length(content) < $2",
            lo, hi
        )
        bar = "#" * min(n, 50)
        print("  " + label.ljust(18) + str(n).rjust(5) + "  " + bar)


async def section_03_stubs_detail(conn):
    section("8.3 Stub skills (<300 chars) detail")
    rows = await conn.fetch(
        "SELECT id, path, length(content) as clen, content "
        "FROM skills_tree WHERE length(content) < 300 ORDER BY clen"
    )
    print("  Total stubs: " + str(len(rows)))
    print()
    for r in rows:
        print("  --- id=" + str(r["id"]) + " len=" + str(r["clen"]) + " path=" + r["path"])
        # Show first 200 chars
        content = r["content"] or ""
        for line in content.split("\n")[:6]:
            print("    " + truncate(line, 100))
        print()


async def section_04_never_updated(conn):
    section("8.4 Skills never updated (updated_at IS NULL)")
    rows = await conn.fetch(
        "SELECT id, path, length(content) as clen, created_at "
        "FROM skills_tree WHERE updated_at IS NULL ORDER BY id"
    )
    print("  Total: " + str(len(rows)))
    print()
    for r in rows:
        print("  id=" + str(r["id"]).rjust(3) + " len=" + str(r["clen"]).rjust(5) + " " + truncate(r["path"], 50) + " created=" + str(r["created_at"])[:19])


async def section_05_emergency_skills(conn):
    section("8.5 Emergency skills (always loaded)")
    rows = await conn.fetch(
        "SELECT id, path, length(content) as clen, updated_at "
        "FROM skills_tree WHERE emergency = true ORDER BY id"
    )
    print("  Total emergency: " + str(len(rows)))
    print()
    for r in rows:
        upd = str(r["updated_at"])[:19] if r["updated_at"] else "NULL"
        print("  id=" + str(r["id"]).rjust(3) + " len=" + str(r["clen"]).rjust(5) + " upd=" + upd + " " + truncate(r["path"], 50))


async def section_06_top_largest(conn):
    section("8.6 Top 15 largest skills by content size")
    rows = await conn.fetch(
        "SELECT id, path, length(content) as clen, emergency, verified "
        "FROM skills_tree ORDER BY clen DESC LIMIT 15"
    )
    for r in rows:
        em = "E" if r["emergency"] else " "
        ve = "V" if r["verified"] else " "
        print("  id=" + str(r["id"]).rjust(3) + " " + em + ve + " " + str(r["clen"]).rjust(6) + " " + truncate(r["path"], 60))


async def section_07_recently_updated(conn):
    section("8.7 Recently updated skills (last 7 days)")
    rows = await conn.fetch(
        "SELECT id, path, length(content) as clen, updated_at "
        "FROM skills_tree WHERE updated_at > NOW() - INTERVAL '7 days' "
        "ORDER BY updated_at DESC"
    )
    print("  Total updated last 7d: " + str(len(rows)))
    print()
    for r in rows[:20]:
        print("  id=" + str(r["id"]).rjust(3) + " " + str(r["updated_at"])[:19] + " len=" + str(r["clen"]).rjust(5) + " " + truncate(r["path"], 50))


async def section_08_legacy_skills_table(conn):
    section("8.8 Legacy 'skills' table (separate from skills_tree)")
    try:
        total = await conn.fetchval("SELECT COUNT(*) FROM skills")
        print("  Total rows: " + str(total))

        cols = await conn.fetch(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'skills' ORDER BY ordinal_position"
        )
        print()
        print("  Columns:")
        for c in cols:
            print("    " + c["column_name"].ljust(20) + " " + c["data_type"])

        # Sample first 25 rows
        rows = await conn.fetch("SELECT * FROM skills ORDER BY 1 LIMIT 25")
        print()
        print("  Rows:")
        for r in rows:
            d = dict(r)
            preview = []
            for k, v in list(d.items())[:5]:
                if isinstance(v, str) and len(v) > 30:
                    v = v[:27] + "..."
                preview.append(k + "=" + str(v))
            print("    " + " | ".join(preview))
    except Exception as e:
        print("  ERR: " + str(e)[:200])


async def section_09_content_patterns(conn):
    section("8.9 Content patterns analysis")
    # Skills with code blocks
    code_blocks = await conn.fetchval(
        "SELECT COUNT(*) FROM skills_tree WHERE content LIKE '%```%'"
    )
    # Skills with markdown headers
    md_headers = await conn.fetchval(
        "SELECT COUNT(*) FROM skills_tree WHERE content ~ '^#'"
    )
    # Skills with bullet points
    bullets = await conn.fetchval(
        "SELECT COUNT(*) FROM skills_tree WHERE content LIKE '%- %' OR content LIKE '%* %'"
    )
    # Skills referencing other skills
    skill_refs = await conn.fetchval(
        "SELECT COUNT(*) FROM skills_tree WHERE content ~* 'skill\\s*#?\\d+'"
    )
    # Skills with bash commands
    bash_cmds = await conn.fetchval(
        "SELECT COUNT(*) FROM skills_tree WHERE content LIKE '%```bash%' OR content LIKE '%```sh%'"
    )
    # Skills mentioning specific files/paths
    paths = await conn.fetchval(
        "SELECT COUNT(*) FROM skills_tree WHERE content LIKE '%/home/%' OR content LIKE '%/etc/%' OR content LIKE '%/var/%'"
    )

    print("  Skills with code blocks (```):     " + str(code_blocks))
    print("  Skills with markdown headers (#):  " + str(md_headers))
    print("  Skills with bullets (- / *):       " + str(bullets))
    print("  Skills referencing other skills:   " + str(skill_refs))
    print("  Skills with bash code blocks:      " + str(bash_cmds))
    print("  Skills mentioning paths:           " + str(paths))


async def section_10_categories(conn):
    section("8.10 Skills by parent_path category")
    rows = await conn.fetch(
        "SELECT parent_path, COUNT(*) as n, AVG(length(content))::int as avg_len, "
        "SUM(CASE WHEN updated_at IS NULL THEN 1 ELSE 0 END) as never_updated "
        "FROM skills_tree GROUP BY parent_path ORDER BY n DESC"
    )
    print("  " + "Category".ljust(25) + "Count".rjust(6) + "  " + "Avg Len".rjust(8) + "  " + "Stale".rjust(6))
    print("  " + "-" * 60)
    for r in rows:
        pp = (r["parent_path"] or "<NULL>")[:25]
        print("  " + pp.ljust(25) + str(r["n"]).rjust(6) + "  " + str(r["avg_len"]).rjust(8) + "  " + str(r["never_updated"]).rjust(6))


async def section_11_skill_loading_in_chat():
    section("8.11 Skill loading flow in api/chat.py")
    path = os.path.join(ARGOS_CORE, "api", "chat.py")
    if not os.path.exists(path):
        print("  [MISSING] chat.py")
        return

    with open(path, "r", errors="replace") as f:
        content = f.read()

    # Functions related to skills
    func_pattern = re.compile(r"^\s*(?:async\s+)?def\s+(_?\w*[Ss]kill\w*)\s*\(", re.MULTILINE)
    funcs = func_pattern.findall(content)
    print("  Skill-related functions in chat.py:")
    for f in set(funcs):
        # Find line number
        for i, line in enumerate(content.splitlines(), 1):
            if "def " + f + "(" in line:
                print("    L" + str(i) + " " + f + "()")
                break

    # Skill references (skill #N or skills_tree queries)
    print()
    print("  Direct DB queries on skills_tree:")
    for i, line in enumerate(content.splitlines(), 1):
        if "skills_tree" in line and not line.strip().startswith("#"):
            print("    L" + str(i) + ": " + truncate(line.strip(), 100))

    # Hardcoded skill IDs/paths
    print()
    print("  Hardcoded skill references:")
    refs = SKILL_REF_PATTERN.findall(content)
    if refs:
        cnt = Counter(refs)
        for skill_id, n in cnt.most_common(10):
            print("    skill #" + skill_id + " : " + str(n) + " mentions")


async def section_12_skill_loading_in_prompts():
    section("8.12 Skill loading in agent/prompts.py")
    path = os.path.join(ARGOS_CORE, "agent", "prompts.py")
    if not os.path.exists(path):
        print("  [MISSING]")
        return

    with open(path, "r", errors="replace") as f:
        content = f.read()

    # Find skill-related functions
    func_pattern = re.compile(r"^\s*(?:async\s+)?def\s+(_?\w*[Ss]kill\w*)\s*\(", re.MULTILINE)
    funcs = func_pattern.findall(content)
    print("  Skill-related functions:")
    for f in set(funcs):
        for i, line in enumerate(content.splitlines(), 1):
            if "def " + f + "(" in line:
                print("    L" + str(i) + " " + f + "()")
                break

    # DB queries
    print()
    print("  Direct DB queries on skills_tree / skills:")
    for i, line in enumerate(content.splitlines(), 1):
        if ("skills_tree" in line or "FROM skills" in line) and not line.strip().startswith("#"):
            print("    L" + str(i) + ": " + truncate(line.strip(), 100))


async def section_13_referenced_in_code_check(conn):
    section("8.13 Cross-ref: skills referenced in code vs DB existence")
    # Read all .py files and find skill references
    code_dirs = ["agent", "api", "llm", "tools"]
    referenced_ids = set()
    file_refs = defaultdict(list)

    for d in code_dirs:
        dir_path = os.path.join(ARGOS_CORE, d)
        if not os.path.exists(dir_path):
            continue
        for root, dirs, files in os.walk(dir_path):
            if "__pycache__" in root:
                continue
            for f in files:
                if not f.endswith(".py"):
                    continue
                fpath = os.path.join(root, f)
                try:
                    with open(fpath, "r", errors="replace") as fh:
                        content = fh.read()
                except:
                    continue
                # Look in comments for skill #N
                for i, line in enumerate(content.splitlines(), 1):
                    matches = SKILL_REF_PATTERN.findall(line)
                    for m in matches:
                        sid = int(m)
                        if 1 <= sid <= 200:  # sane range
                            referenced_ids.add(sid)
                            rel = fpath.replace(ARGOS_CORE + "/", "")
                            file_refs[sid].append((rel, i))

    print("  Total unique skill IDs referenced in code: " + str(len(referenced_ids)))

    # Get all existing skill IDs from DB
    rows = await conn.fetch("SELECT id, path FROM skills_tree ORDER BY id")
    existing_ids = {r["id"]: r["path"] for r in rows}

    print()
    print("  Referenced in code | Exists in DB?")
    for sid in sorted(referenced_ids):
        if sid in existing_ids:
            mark = "OK"
            path = existing_ids[sid]
        else:
            mark = "MISSING"
            path = "?"
        print("  skill #" + str(sid).rjust(3) + " " + mark.ljust(8) + " " + truncate(path, 50))
        # Show first 2 references
        for rel, lineno in file_refs[sid][:2]:
            print("    -> " + rel + ":L" + str(lineno))


async def section_14_skill_creation_protocol(conn):
    section("8.14 Skill creation protocol (#93 meta-skill)")
    row = await conn.fetchrow(
        "SELECT id, path, length(content) as clen, content, updated_at "
        "FROM skills_tree WHERE id = 93 OR path LIKE '%skill-creation%'"
    )
    if row:
        print("  id=" + str(row["id"]) + " path=" + row["path"])
        print("  length=" + str(row["clen"]))
        print("  updated_at=" + str(row["updated_at"]))
        print()
        print("  Content preview (first 30 lines):")
        content = row["content"] or ""
        for line in content.split("\n")[:30]:
            print("    " + truncate(line, 110))
    else:
        print("  [NOT FOUND] skill #93 missing")


async def section_15_settings_skill_flags(conn):
    section("8.15 Skill-related settings flags")
    rows = await conn.fetch(
        "SELECT key, value FROM settings WHERE key LIKE '%skill%' ORDER BY key"
    )
    for r in rows:
        print("  " + r["key"].ljust(40) + " = " + str(r["value"]))


async def main():
    header("TASK 08 - Skills system deep audit")

    conn = await connect_db()

    await section_01_skills_tree_overview(conn)
    await section_02_length_distribution(conn)
    await section_03_stubs_detail(conn)
    await section_04_never_updated(conn)
    await section_05_emergency_skills(conn)
    await section_06_top_largest(conn)
    await section_07_recently_updated(conn)
    await section_08_legacy_skills_table(conn)
    await section_09_content_patterns(conn)
    await section_10_categories(conn)
    await section_11_skill_loading_in_chat()
    await section_12_skill_loading_in_prompts()
    await section_13_referenced_in_code_check(conn)
    await section_14_skill_creation_protocol(conn)
    await section_15_settings_skill_flags(conn)

    await conn.close()

    print()
    print("=" * 70)
    print(" END TASK 08 RECON")
    print("=" * 70)


asyncio.run(main())
