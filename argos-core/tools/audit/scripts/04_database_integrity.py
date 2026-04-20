"""
TASK 04 - Database integrity audit

Read-only. Scan claudedb PostgreSQL for:
- Schema overview (all tables, row counts, sizes)
- skills_tree integrity (duplicates, orphans, content anomalies)
- settings table (NULL values, duplicates, stale entries)
- Agent loop tables (sessions, verification_rules, evidence)
- Messages / conversations (orphans, runaway growth)
- Index coverage on hot tables
- Foreign key orphans
- Recent write activity per table

Zero writes. Only SELECT queries.
NEVER prints credentials from settings.
"""
import asyncio
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import connect_db, header, section, truncate


HOT_TABLES = [
    "skills_tree",
    "settings",
    "messages",
    "conversations",
    "agent_sessions",
    "agent_verification_rules",
    "reasoning_log",
    "heartbeat_log",
    "notes",
    "jobs",
    "authorizations",
]

SENSITIVE_KEY_PATTERNS = ["api_key", "token", "password", "secret", "apikey", "auth"]


async def get_all_tables(conn):
    rows = await conn.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname = $1 ORDER BY tablename",
        "public"
    )
    return [r["tablename"] for r in rows]


async def get_row_count(conn, table):
    try:
        return await conn.fetchval('SELECT COUNT(*) FROM "' + table + '"')
    except Exception as e:
        return -1


async def get_table_size(conn, table):
    try:
        return await conn.fetchval(
            "SELECT pg_total_relation_size($1::regclass)",
            "public." + table
        )
    except Exception:
        return 0


def format_bytes(n):
    if n is None or n < 0:
        return "n/a"
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return str(round(n, 1)) + " " + unit
        n /= 1024
    return str(round(n, 1)) + " TB"


async def section_01_schema_overview(conn):
    section("4.1 Schema overview")
    tables = await get_all_tables(conn)
    print("  Total tables in public schema: " + str(len(tables)))
    print()

    stats = []
    for t in tables:
        count = await get_row_count(conn, t)
        size = await get_table_size(conn, t)
        stats.append((t, count, size))

    # Sort by row count desc
    stats.sort(key=lambda x: -(x[1] if x[1] >= 0 else 0))

    print("  " + "Table".ljust(35) + "Rows".rjust(10) + "  " + "Size".rjust(12))
    print("  " + "-" * 60)
    total_rows = 0
    total_bytes = 0
    for t, count, size in stats:
        if count >= 0:
            total_rows += count
        if size:
            total_bytes += size
        count_str = str(count) if count >= 0 else "ERR"
        print("  " + t.ljust(35) + count_str.rjust(10) + "  " + format_bytes(size).rjust(12))

    print("  " + "-" * 60)
    print("  " + "TOTAL".ljust(35) + str(total_rows).rjust(10) + "  " + format_bytes(total_bytes).rjust(12))


async def section_02_skills_tree_integrity(conn):
    section("4.2 skills_tree integrity")

    total = await conn.fetchval("SELECT COUNT(*) FROM skills_tree")
    verified = await conn.fetchval("SELECT COUNT(*) FROM skills_tree WHERE verified = true")
    emergency = await conn.fetchval("SELECT COUNT(*) FROM skills_tree WHERE emergency = true")
    print("  Total skills:       " + str(total))
    print("  Verified:           " + str(verified))
    print("  Emergency:          " + str(emergency))
    print()

    # Duplicate paths
    dupes = await conn.fetch(
        "SELECT path, COUNT(*) as n FROM skills_tree GROUP BY path HAVING COUNT(*) > 1"
    )
    print("  Duplicate paths: " + str(len(dupes)))
    for d in dupes[:10]:
        print("    [DUP] " + d["path"] + " (x" + str(d["n"]) + ")")

    # Duplicate names
    dupe_names = await conn.fetch(
        "SELECT name, COUNT(*) as n FROM skills_tree GROUP BY name HAVING COUNT(*) > 1"
    )
    print()
    print("  Duplicate names: " + str(len(dupe_names)))
    for d in dupe_names[:10]:
        print("    [DUP] " + d["name"] + " (x" + str(d["n"]) + ")")

    # Very short content (likely stubs)
    print()
    short = await conn.fetch(
        "SELECT id, path, length(content) as clen FROM skills_tree WHERE length(content) < 300 ORDER BY clen"
    )
    print("  Skills with content < 300 chars: " + str(len(short)))
    for s in short[:15]:
        print("    id=" + str(s["id"]) + " len=" + str(s["clen"]) + " " + truncate(s["path"], 60))

    # Very long content (suspect)
    long_skills = await conn.fetch(
        "SELECT id, path, length(content) as clen FROM skills_tree WHERE length(content) > 15000 ORDER BY clen DESC"
    )
    print()
    print("  Skills with content > 15000 chars: " + str(len(long_skills)))
    for s in long_skills:
        print("    id=" + str(s["id"]) + " len=" + str(s["clen"]) + " " + truncate(s["path"], 60))

    # NULL content
    null_content = await conn.fetchval(
        "SELECT COUNT(*) FROM skills_tree WHERE content IS NULL OR content = ''"
    )
    print()
    print("  Skills with NULL or empty content: " + str(null_content))

    # NULL updated_at (never updated after insert)
    null_updated = await conn.fetch(
        "SELECT id, path, created_at FROM skills_tree WHERE updated_at IS NULL ORDER BY id"
    )
    print()
    print("  Skills never updated (updated_at IS NULL): " + str(len(null_updated)))
    for s in null_updated[:15]:
        print("    id=" + str(s["id"]) + " " + truncate(s["path"], 60))
    if len(null_updated) > 15:
        print("    ... and " + str(len(null_updated) - 15) + " more")

    # Unverified skills
    unverified = await conn.fetch(
        "SELECT id, path FROM skills_tree WHERE verified = false ORDER BY id"
    )
    print()
    print("  Unverified skills: " + str(len(unverified)))
    for s in unverified[:10]:
        print("    id=" + str(s["id"]) + " " + truncate(s["path"], 60))

    # Skills by parent_path distribution
    by_parent = await conn.fetch(
        "SELECT parent_path, COUNT(*) as n FROM skills_tree GROUP BY parent_path ORDER BY n DESC"
    )
    print()
    print("  Distribution by parent_path:")
    for p in by_parent[:15]:
        pp = p["parent_path"] or "<NULL>"
        print("    " + pp.ljust(30) + " : " + str(p["n"]))

    # Orphan skills (parent_path points to non-existent parent)
    orphans = await conn.fetch(
        "SELECT DISTINCT s1.parent_path FROM skills_tree s1 "
        "WHERE s1.parent_path IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM skills_tree s2 WHERE s2.path = s1.parent_path)"
    )
    print()
    print("  Orphan parent_paths (point to missing skills): " + str(len(orphans)))
    for o in orphans[:10]:
        print("    " + str(o["parent_path"]))


async def section_03_settings_table(conn):
    section("4.3 settings table")

    total = await conn.fetchval("SELECT COUNT(*) FROM settings")
    print("  Total settings entries: " + str(total))
    print()

    # Get columns
    cols = await conn.fetch(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = $1 ORDER BY ordinal_position",
        "settings"
    )
    col_names = [c["column_name"] for c in cols]
    print("  Columns: " + ", ".join(col_names))
    print()

    # Duplicate keys
    dupes = await conn.fetch(
        "SELECT key, COUNT(*) as n FROM settings GROUP BY key HAVING COUNT(*) > 1"
    )
    print("  Duplicate keys: " + str(len(dupes)))
    for d in dupes[:10]:
        print("    [DUP] " + d["key"] + " (x" + str(d["n"]) + ")")

    # NULL values
    null_values = await conn.fetchval(
        "SELECT COUNT(*) FROM settings WHERE value IS NULL OR value = ''"
    )
    print()
    print("  Settings with NULL or empty value: " + str(null_values))

    # List all keys (no values for sensitive ones)
    all_settings = await conn.fetch("SELECT key, value FROM settings ORDER BY key")
    print()
    print("  All settings keys (values masked for sensitive):")
    for s in all_settings:
        k = s["key"]
        v = s["value"] or ""
        is_sensitive = any(pat in k.lower() for pat in SENSITIVE_KEY_PATTERNS)
        if is_sensitive:
            if len(v) > 8:
                display = v[:4] + "..." + v[-4:] + " (len=" + str(len(v)) + ")"
            else:
                display = "***"
        else:
            if len(v) > 60:
                display = v[:57] + "..."
            else:
                display = v
        print("    " + k.ljust(40) + " = " + display)


async def section_04_agent_sessions(conn):
    section("4.4 agent_sessions table")
    try:
        total = await conn.fetchval("SELECT COUNT(*) FROM agent_sessions")
        print("  Total agent sessions: " + str(total))

        cols = await conn.fetch(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = $1 ORDER BY ordinal_position",
            "agent_sessions"
        )
        print()
        print("  Columns:")
        for c in cols:
            print("    " + c["column_name"] + ": " + c["data_type"])

        # Recent sessions
        recent = await conn.fetch(
            "SELECT * FROM agent_sessions ORDER BY id DESC LIMIT 5"
        )
        print()
        print("  Most recent 5 sessions:")
        for r in recent:
            d = dict(r)
            # Compact preview
            parts = []
            for k, v in list(d.items())[:6]:
                if isinstance(v, str) and len(v) > 30:
                    v = v[:27] + "..."
                parts.append(k + "=" + str(v))
            print("    " + " | ".join(parts))
    except Exception as e:
        print("  ERR: " + str(e)[:150])


async def section_05_verification_rules(conn):
    section("4.5 agent_verification_rules")
    try:
        total = await conn.fetchval("SELECT COUNT(*) FROM agent_verification_rules")
        active = await conn.fetchval("SELECT COUNT(*) FROM agent_verification_rules WHERE active = true")
        print("  Total rules: " + str(total))
        print("  Active rules: " + str(active))
        print("  Inactive rules: " + str(total - active))
        print()

        cols = await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name = $1",
            "agent_verification_rules"
        )
        col_names = [c["column_name"] for c in cols]
        print("  Columns: " + ", ".join(col_names))
        print()

        # Distribution by rule_type
        by_type = await conn.fetch(
            "SELECT rule_type, COUNT(*) as n FROM agent_verification_rules GROUP BY rule_type ORDER BY n DESC"
        )
        print("  By rule_type:")
        for a in by_type:
            print("    " + str(a["rule_type"]).ljust(25) + " : " + str(a["n"]))
        print()

        # Distribution by on_fail
        by_fail = await conn.fetch(
            "SELECT on_fail, COUNT(*) as n FROM agent_verification_rules GROUP BY on_fail ORDER BY n DESC"
        )
        print("  By on_fail action:")
        for a in by_fail:
            print("    " + str(a["on_fail"]).ljust(25) + " : " + str(a["n"]))
        print()

        # All rules with proper columns
        rows = await conn.fetch(
            "SELECT id, pattern, rule_type, on_fail, priority, active, description "
            "FROM agent_verification_rules ORDER BY priority DESC, id"
        )
        print("  All rules (priority order):")
        for r in rows:
            rid = r["id"]
            pattern = r["pattern"] or ""
            rtype = r["rule_type"] or "?"
            onfail = r["on_fail"] or "?"
            prio = r["priority"] if r["priority"] is not None else "?"
            act = "A" if r["active"] else "I"
            desc = r["description"] or ""
            print("    [" + str(rid).rjust(3) + "] " + act + " p" + str(prio).rjust(2) + " " + str(rtype).ljust(12) + " -> " + str(onfail).ljust(12) + " | " + truncate(pattern, 30))
            if desc:
                print("         desc: " + truncate(desc, 80))

        # Check for dead rules (active=false or missing fields)
        null_pattern = await conn.fetchval(
            "SELECT COUNT(*) FROM agent_verification_rules WHERE pattern IS NULL OR pattern = ''"
        )
        print()
        print("  Rules with NULL/empty pattern: " + str(null_pattern))
    except Exception as e:
        print("  ERR: " + str(e)[:150])


async def section_06_messages_conversations(conn):
    section("4.6 messages + conversations")
    try:
        msg_count = await conn.fetchval("SELECT COUNT(*) FROM messages")
        conv_count = await conn.fetchval("SELECT COUNT(*) FROM conversations")
        print("  Total messages:      " + str(msg_count))
        print("  Total conversations: " + str(conv_count))
        if conv_count > 0:
            avg = msg_count / conv_count
            print("  Avg messages per conv: " + str(round(avg, 1)))

        # Messages per conversation distribution
        top_convs = await conn.fetch(
            "SELECT conversation_id, COUNT(*) as n FROM messages "
            "GROUP BY conversation_id ORDER BY n DESC LIMIT 10"
        )
        print()
        print("  Top 10 conversations by message count:")
        for c in top_convs:
            print("    conv " + str(c["conversation_id"]).rjust(6) + " : " + str(c["n"]) + " messages")

        # Orphan messages (conversation_id not in conversations)
        orphan_msgs = await conn.fetchval(
            "SELECT COUNT(*) FROM messages m "
            "WHERE NOT EXISTS (SELECT 1 FROM conversations c WHERE c.id = m.conversation_id)"
        )
        print()
        print("  Orphan messages (no matching conversation): " + str(orphan_msgs))

        # Pending messages
        pending = await conn.fetchval(
            "SELECT COUNT(*) FROM messages WHERE pending = true"
        )
        print("  Pending messages (not yet completed): " + str(pending))

        # Recent activity
        recent_msgs = await conn.fetchval(
            "SELECT COUNT(*) FROM messages WHERE created_at > NOW() - INTERVAL '24 hours'"
        )
        recent_week = await conn.fetchval(
            "SELECT COUNT(*) FROM messages WHERE created_at > NOW() - INTERVAL '7 days'"
        )
        print()
        print("  Messages last 24h: " + str(recent_msgs))
        print("  Messages last 7d:  " + str(recent_week))

        # Conversations without any messages (empty conversations)
        empty_convs = await conn.fetchval(
            "SELECT COUNT(*) FROM conversations c "
            "WHERE NOT EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id = c.id)"
        )
        print()
        print("  Empty conversations (zero messages): " + str(empty_convs))
    except Exception as e:
        print("  ERR: " + str(e)[:150])


async def section_07_heartbeat(conn):
    section("4.7 heartbeat_log freshness")
    try:
        # Detect correct timestamp column
        cols = await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name = $1",
            "heartbeat_log"
        )
        col_names = [c["column_name"] for c in cols]
        print("  Columns: " + ", ".join(col_names))

        ts_col = None
        for candidate in ["ts", "timestamp", "created_at", "at"]:
            if candidate in col_names:
                ts_col = candidate
                break

        if not ts_col:
            print("  [ERR] No timestamp column found")
            return

        print("  Using timestamp column: " + ts_col)
        print()

        total = await conn.fetchval("SELECT COUNT(*) FROM heartbeat_log")
        print("  Total heartbeat entries: " + str(total))

        recent = await conn.fetchval(
            "SELECT COUNT(*) FROM heartbeat_log WHERE " + ts_col + " > NOW() - INTERVAL '5 minutes'"
        )
        hourly = await conn.fetchval(
            "SELECT COUNT(*) FROM heartbeat_log WHERE " + ts_col + " > NOW() - INTERVAL '1 hour'"
        )
        daily = await conn.fetchval(
            "SELECT COUNT(*) FROM heartbeat_log WHERE " + ts_col + " > NOW() - INTERVAL '24 hours'"
        )
        print("  Last 5 min:  " + str(recent))
        print("  Last 1h:     " + str(hourly))
        print("  Last 24h:    " + str(daily))

        # Latest entry
        latest = await conn.fetchrow(
            "SELECT " + ts_col + " as ts FROM heartbeat_log ORDER BY " + ts_col + " DESC LIMIT 1"
        )
        if latest:
            print("  Latest entry: " + str(latest["ts"]))

        # By node if available
        if "node" in col_names:
            by_node = await conn.fetch(
                "SELECT node, COUNT(*) as n, MAX(" + ts_col + ") as last_seen "
                "FROM heartbeat_log GROUP BY node ORDER BY last_seen DESC"
            )
            print()
            print("  By node:")
            for n in by_node:
                print("    " + str(n["node"]).ljust(15) + " count=" + str(n["n"]).rjust(4) + "  last=" + str(n["last_seen"]))
    except Exception as e:
        print("  ERR: " + str(e)[:150])


async def section_08_index_coverage(conn):
    section("4.8 Index coverage on hot tables")
    try:
        for table in HOT_TABLES[:8]:
            rows = await conn.fetch(
                "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = $1",
                table
            )
            print("  " + table + " (" + str(len(rows)) + " indexes):")
            for r in rows:
                idx_def = r["indexdef"]
                # Extract the column list from def
                if "(" in idx_def:
                    cols_part = idx_def[idx_def.index("(") + 1:idx_def.rindex(")")]
                else:
                    cols_part = "?"
                print("    " + r["indexname"].ljust(40) + " on (" + cols_part + ")")
            print()
    except Exception as e:
        print("  ERR: " + str(e)[:150])


async def section_09_database_stats(conn):
    section("4.9 Database-level stats")
    try:
        version = await conn.fetchval("SELECT version()")
        print("  PostgreSQL: " + version[:100])

        db_size = await conn.fetchval("SELECT pg_database_size('claudedb')")
        print("  claudedb total size: " + format_bytes(db_size))

        # Active connections
        conn_count = await conn.fetchval(
            "SELECT COUNT(*) FROM pg_stat_activity WHERE datname = 'claudedb'"
        )
        print("  Active connections: " + str(conn_count))

        # Replication status
        repl = await conn.fetch("SELECT * FROM pg_stat_replication")
        print("  Replication slots active: " + str(len(repl)))
        for r in repl:
            d = dict(r)
            app = d.get("application_name", "?")
            state = d.get("state", "?")
            print("    " + str(app) + " state=" + str(state))
    except Exception as e:
        print("  ERR: " + str(e)[:150])


async def section_10_orphaned_data(conn):
    section("4.10 Cross-table orphan detection")
    try:
        # agent_sessions orphans - session with no messages or conversations referenced
        orphan_check = await conn.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' "
            "AND (table_name LIKE '%_log' OR table_name LIKE '%_history')"
        )
        print("  Log/history tables: " + ", ".join([r["table_name"] for r in orphan_check]))
        print()

        # Check log tables growth
        for t in [r["table_name"] for r in orphan_check][:5]:
            try:
                count = await conn.fetchval('SELECT COUNT(*) FROM "' + t + '"')
                size = await get_table_size(conn, t)
                print("    " + t.ljust(30) + " rows=" + str(count).rjust(8) + " size=" + format_bytes(size))
            except:
                pass
    except Exception as e:
        print("  ERR: " + str(e)[:150])


async def main():
    header("TASK 04 - Database integrity audit")

    conn = await connect_db()

    await section_01_schema_overview(conn)
    await section_02_skills_tree_integrity(conn)
    await section_03_settings_table(conn)
    await section_04_agent_sessions(conn)
    await section_05_verification_rules(conn)
    await section_06_messages_conversations(conn)
    await section_07_heartbeat(conn)
    await section_08_index_coverage(conn)
    await section_09_database_stats(conn)
    await section_10_orphaned_data(conn)

    await conn.close()

    print()
    print("=" * 70)
    print(" END TASK 04 RECON")
    print("=" * 70)


asyncio.run(main())
