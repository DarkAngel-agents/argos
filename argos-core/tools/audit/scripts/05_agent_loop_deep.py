"""
TASK 05 - Agent loop deep dive

Read-only. Analyzes:
- agent/loop.py structure (functions, calls, complexity)
- agent/verification.py (verification chain, rule application)
- agent/evidence.py (evidence collection)
- agent/autonomy.py (autonomy gates)
- agent/prompts.py (prompt building)
- agent/tools.py (tool execution)

Plus DB cross-reference:
- recent agent_sessions failure pattern
- verification rules vs code paths
- evidence growth per session
"""
import ast
import asyncio
import os
import re
import sys
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import connect_db, header, section, truncate, ARGOS_CORE

AGENT_DIR = os.path.join(ARGOS_CORE, "agent")
TARGET_FILES = [
    "loop.py",
    "verification.py",
    "evidence.py",
    "autonomy.py",
    "prompts.py",
    "tools.py",
]


def read_file(path):
    try:
        with open(path, "r", errors="replace") as f:
            return f.read()
    except:
        return ""


def parse_ast(content, path):
    try:
        return ast.parse(content, filename=path)
    except Exception:
        return None


def get_functions(tree):
    """Return list of (name, lineno, end_lineno, length, args, is_async)."""
    funcs = []
    if tree is None:
        return funcs
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            length = end - node.lineno + 1
            args = [a.arg for a in node.args.args]
            is_async = isinstance(node, ast.AsyncFunctionDef)
            funcs.append((node.name, node.lineno, end, length, args, is_async))
    return funcs


def get_classes(tree):
    """Return list of (name, lineno, methods)."""
    classes = []
    if tree is None:
        return classes
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = []
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(child.name)
            classes.append((node.name, node.lineno, methods))
    return classes


def get_imports(tree):
    """Return list of imported names."""
    imports = []
    if tree is None:
        return imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                imports.append(n.asname or n.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for n in node.names:
                imports.append(mod + "." + n.name)
    return imports


def find_function_calls(tree, target_funcs):
    """Find calls to functions in target_funcs list. Returns Counter."""
    calls = Counter()
    if tree is None:
        return calls
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name and name in target_funcs:
                calls[name] += 1
    return calls


def count_complexity_indicators(content, tree):
    """Count various complexity indicators."""
    counts = {
        "if_statements": 0,
        "for_loops": 0,
        "while_loops": 0,
        "try_blocks": 0,
        "nested_depth_max": 0,
        "await_calls": 0,
        "raise_statements": 0,
        "return_statements": 0,
        "continue_statements": 0,
        "break_statements": 0,
    }
    if tree is None:
        return counts

    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            counts["if_statements"] += 1
        elif isinstance(node, ast.For):
            counts["for_loops"] += 1
        elif isinstance(node, ast.While):
            counts["while_loops"] += 1
        elif isinstance(node, ast.Try):
            counts["try_blocks"] += 1
        elif isinstance(node, ast.Await):
            counts["await_calls"] += 1
        elif isinstance(node, ast.Raise):
            counts["raise_statements"] += 1
        elif isinstance(node, ast.Return):
            counts["return_statements"] += 1
        elif isinstance(node, ast.Continue):
            counts["continue_statements"] += 1
        elif isinstance(node, ast.Break):
            counts["break_statements"] += 1

    # Max nested depth - count indentation levels in source
    max_indent = 0
    for line in content.splitlines():
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = (len(line) - len(stripped)) // 4
        if indent > max_indent:
            max_indent = indent
    counts["nested_depth_max"] = max_indent

    return counts


def find_phase_strings(content):
    """Find phase string literals (executing, verifying, fixing, etc)."""
    phase_keywords = ["executing", "verifying", "fixing", "thinking", "planning", "complete", "failed", "active", "paused", "blocked"]
    findings = defaultdict(list)
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for phase in phase_keywords:
            if '"' + phase + '"' in line.lower() or "'" + phase + "'" in line.lower():
                findings[phase].append((i, truncate(stripped, 80)))
    return findings


def find_db_writes(content):
    """Find DB write operations."""
    findings = []
    write_pattern = re.compile(r"(execute|fetchval)\s*\(\s*[\"']\s*(INSERT|UPDATE|DELETE)", re.IGNORECASE)
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        m = write_pattern.search(line)
        if m:
            findings.append((i, m.group(2).upper(), truncate(stripped, 90)))
    return findings


def find_subprocess_or_ssh(content):
    """Find subprocess / ssh / asyncssh calls (potential side effects)."""
    findings = []
    patterns = [
        ("subprocess", re.compile(r"subprocess\.(run|Popen|call|check_output)")),
        ("asyncssh", re.compile(r"asyncssh\.(connect|run)")),
        ("os.system", re.compile(r"os\.system\(")),
        ("os.popen", re.compile(r"os\.popen\(")),
    ]
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for kind, pat in patterns:
            if pat.search(line):
                findings.append((i, kind, truncate(stripped, 80)))
                break
    return findings


def find_critical_branches(content):
    """Find critical branches: error handling, retry loops, escalation."""
    findings = defaultdict(list)
    keywords = {
        "retry": re.compile(r"\bretry|\battempt", re.IGNORECASE),
        "escalate": re.compile(r"\bescalate", re.IGNORECASE),
        "abort": re.compile(r"\babort|\bsys\.exit|\braise SystemExit", re.IGNORECASE),
        "fix_loop": re.compile(r"fix_loop|fix_count|max_fix"),
        "iteration": re.compile(r"iteration\s*[+]=|iteration\s*=\s*\d|max_iterations"),
        "phase_change": re.compile(r"phase\s*=\s*[\"']"),
    }
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for kind, pat in keywords.items():
            if pat.search(line):
                findings[kind].append((i, truncate(stripped, 80)))
                break
    return findings


async def section_01_files_overview():
    section("5.1 Agent dir files overview")
    print("  Path: " + AGENT_DIR)
    if not os.path.exists(AGENT_DIR):
        print("  [MISSING] agent/ directory not found")
        return []

    found = []
    for fname in TARGET_FILES:
        path = os.path.join(AGENT_DIR, fname)
        if not os.path.exists(path):
            print("  [MISSING] " + fname)
            continue
        size = os.path.getsize(path)
        with open(path) as f:
            lines = sum(1 for _ in f)
        found.append((fname, path, lines, size))
        print("  " + fname.ljust(20) + " " + str(lines).rjust(5) + " lines  " + str(size).rjust(7) + " bytes")
    return found


async def section_02_loop_py_structure():
    section("5.2 agent/loop.py structure analysis")
    path = os.path.join(AGENT_DIR, "loop.py")
    if not os.path.exists(path):
        print("  [MISSING] loop.py")
        return

    content = read_file(path)
    tree = parse_ast(content, path)

    print("  Total lines: " + str(len(content.splitlines())))
    print()

    # Functions
    funcs = get_functions(tree)
    funcs.sort(key=lambda x: -x[3])
    print("  Functions defined: " + str(len(funcs)))
    print()
    print("  All functions sorted by length:")
    for name, lineno, end, length, args, is_async in funcs:
        prefix = "async " if is_async else ""
        args_str = ", ".join(args[:3]) + ("..." if len(args) > 3 else "")
        print("    " + str(length).rjust(5) + " lines  L" + str(lineno).rjust(4) + "-" + str(end).rjust(4) + "  " + prefix + name + "(" + args_str + ")")

    # Classes if any
    classes = get_classes(tree)
    if classes:
        print()
        print("  Classes: " + str(len(classes)))
        for name, lineno, methods in classes:
            print("    " + name + " (L" + str(lineno) + ") - " + str(len(methods)) + " methods: " + ", ".join(methods[:5]))


async def section_03_loop_py_complexity():
    section("5.3 agent/loop.py complexity indicators")
    path = os.path.join(AGENT_DIR, "loop.py")
    if not os.path.exists(path):
        return

    content = read_file(path)
    tree = parse_ast(content, path)

    counts = count_complexity_indicators(content, tree)
    print("  if_statements:       " + str(counts["if_statements"]))
    print("  for_loops:           " + str(counts["for_loops"]))
    print("  while_loops:         " + str(counts["while_loops"]))
    print("  try_blocks:          " + str(counts["try_blocks"]))
    print("  await_calls:         " + str(counts["await_calls"]))
    print("  raise_statements:    " + str(counts["raise_statements"]))
    print("  return_statements:   " + str(counts["return_statements"]))
    print("  continue_statements: " + str(counts["continue_statements"]))
    print("  break_statements:    " + str(counts["break_statements"]))
    print("  nested_depth_max:    " + str(counts["nested_depth_max"]))


async def section_04_loop_py_phases():
    section("5.4 Phase transitions in loop.py")
    path = os.path.join(AGENT_DIR, "loop.py")
    if not os.path.exists(path):
        return

    content = read_file(path)
    phases = find_phase_strings(content)

    print("  Phase keywords found:")
    for phase in sorted(phases.keys()):
        instances = phases[phase]
        print("    " + phase.ljust(15) + " : " + str(len(instances)) + " occurrences")

    print()
    print("  Phase change statements (phase = ...):")
    branches = find_critical_branches(content)
    for line_no, text in branches.get("phase_change", [])[:15]:
        print("    L" + str(line_no) + ": " + text)


async def section_05_loop_py_critical_branches():
    section("5.5 Critical branches in loop.py (retry, escalate, abort, fix_loop)")
    path = os.path.join(AGENT_DIR, "loop.py")
    if not os.path.exists(path):
        return

    content = read_file(path)
    branches = find_critical_branches(content)

    for kind in ["retry", "escalate", "abort", "fix_loop", "iteration"]:
        items = branches.get(kind, [])
        print()
        print("  [" + kind + "] - " + str(len(items)) + " occurrences")
        for line_no, text in items[:10]:
            print("    L" + str(line_no) + ": " + text)


async def section_06_loop_db_writes():
    section("5.6 DB writes in agent/loop.py")
    path = os.path.join(AGENT_DIR, "loop.py")
    if not os.path.exists(path):
        return

    content = read_file(path)
    writes = find_db_writes(content)

    by_op = Counter()
    for line_no, op, text in writes:
        by_op[op] += 1

    print("  Total writes: " + str(len(writes)))
    print("  By operation: " + ", ".join(k + "=" + str(v) for k, v in by_op.items()))
    print()
    for line_no, op, text in writes[:20]:
        print("  L" + str(line_no) + " [" + op + "] " + text)


async def section_07_loop_subprocess():
    section("5.7 Subprocess / SSH calls in agent/loop.py")
    path = os.path.join(AGENT_DIR, "loop.py")
    if not os.path.exists(path):
        return

    content = read_file(path)
    findings = find_subprocess_or_ssh(content)

    print("  Total: " + str(len(findings)))
    for line_no, kind, text in findings[:15]:
        print("  L" + str(line_no) + " [" + kind + "] " + text)


async def section_08_verification_py():
    section("5.8 agent/verification.py analysis")
    path = os.path.join(AGENT_DIR, "verification.py")
    if not os.path.exists(path):
        print("  [MISSING]")
        return

    content = read_file(path)
    tree = parse_ast(content, path)

    print("  Total lines: " + str(len(content.splitlines())))

    funcs = get_functions(tree)
    print("  Functions: " + str(len(funcs)))
    for name, lineno, end, length, args, is_async in funcs:
        prefix = "async " if is_async else ""
        print("    " + str(length).rjust(4) + " lines  L" + str(lineno).rjust(4) + "  " + prefix + name + "()")

    # Look for ILIKE / regex / pattern matching code
    print()
    print("  Pattern matching operators (ILIKE / ~* / re.search):")
    pat = re.compile(r"(ILIKE|~\*|re\.search|re\.match|regex)")
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if pat.search(line):
            print("    L" + str(i) + ": " + truncate(stripped, 90))


async def section_09_evidence_py():
    section("5.9 agent/evidence.py analysis")
    path = os.path.join(AGENT_DIR, "evidence.py")
    if not os.path.exists(path):
        print("  [MISSING]")
        return

    content = read_file(path)
    tree = parse_ast(content, path)

    print("  Total lines: " + str(len(content.splitlines())))

    funcs = get_functions(tree)
    print("  Functions: " + str(len(funcs)))
    for name, lineno, end, length, args, is_async in funcs:
        prefix = "async " if is_async else ""
        print("    " + str(length).rjust(4) + " lines  L" + str(lineno).rjust(4) + "  " + prefix + name + "()")


async def section_10_autonomy_py():
    section("5.10 agent/autonomy.py analysis")
    path = os.path.join(AGENT_DIR, "autonomy.py")
    if not os.path.exists(path):
        print("  [MISSING]")
        return

    content = read_file(path)
    tree = parse_ast(content, path)

    print("  Total lines: " + str(len(content.splitlines())))

    funcs = get_functions(tree)
    print("  Functions: " + str(len(funcs)))
    for name, lineno, end, length, args, is_async in funcs:
        prefix = "async " if is_async else ""
        print("    " + str(length).rjust(4) + " lines  L" + str(lineno).rjust(4) + "  " + prefix + name + "()")


async def section_11_tools_py():
    section("5.11 agent/tools.py analysis")
    path = os.path.join(AGENT_DIR, "tools.py")
    if not os.path.exists(path):
        print("  [MISSING]")
        return

    content = read_file(path)
    tree = parse_ast(content, path)

    print("  Total lines: " + str(len(content.splitlines())))

    funcs = get_functions(tree)
    print("  Functions: " + str(len(funcs)))
    for name, lineno, end, length, args, is_async in funcs[:15]:
        prefix = "async " if is_async else ""
        print("    " + str(length).rjust(4) + " lines  L" + str(lineno).rjust(4) + "  " + prefix + name + "()")

    # Look for tool registration / dispatch
    print()
    print("  Tool dispatch patterns:")
    pat = re.compile(r"(TOOLS\s*=|tool_name|dispatch|register_tool)")
    count = 0
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if pat.search(line):
            print("    L" + str(i) + ": " + truncate(stripped, 90))
            count += 1
            if count >= 10:
                break


async def section_12_prompts_py():
    section("5.12 agent/prompts.py analysis (top level only)")
    path = os.path.join(AGENT_DIR, "prompts.py")
    if not os.path.exists(path):
        print("  [MISSING]")
        return

    content = read_file(path)
    tree = parse_ast(content, path)

    print("  Total lines: " + str(len(content.splitlines())))

    funcs = get_functions(tree)
    print("  Functions: " + str(len(funcs)))
    funcs.sort(key=lambda x: -x[3])
    for name, lineno, end, length, args, is_async in funcs[:10]:
        prefix = "async " if is_async else ""
        print("    " + str(length).rjust(4) + " lines  L" + str(lineno).rjust(4) + "  " + prefix + name + "()")


async def section_13_db_session_pattern(conn):
    section("5.13 DB cross-reference: agent_sessions failure pattern")

    # Failure rate by phase
    by_phase = await conn.fetch(
        "SELECT phase, COUNT(*) as n FROM agent_sessions GROUP BY phase ORDER BY n DESC"
    )
    print("  Sessions by phase:")
    for r in by_phase:
        print("    " + str(r["phase"]).ljust(15) + " : " + str(r["n"]))

    # Iterations distribution for failed sessions
    iter_stats = await conn.fetchrow(
        "SELECT MIN(iteration) as min_i, MAX(iteration) as max_i, AVG(iteration)::int as avg_i, COUNT(*) as n "
        "FROM agent_sessions WHERE phase = 'failed'"
    )
    print()
    print("  Failed sessions iteration stats:")
    print("    count: " + str(iter_stats["n"] if iter_stats else 0))
    if iter_stats and iter_stats["n"]:
        print("    min iterations: " + str(iter_stats["min_i"]))
        print("    max iterations: " + str(iter_stats["max_i"]))
        print("    avg iterations: " + str(iter_stats["avg_i"]))

    # Recent sessions detail
    recent = await conn.fetch(
        "SELECT id, phase, iteration, max_iterations, llm_provider, total_tokens, "
        "EXTRACT(EPOCH FROM (last_active_at - started_at))::int as duration_sec "
        "FROM agent_sessions ORDER BY id DESC LIMIT 10"
    )
    print()
    print("  Last 10 sessions detail:")
    print("  " + "id".rjust(4) + " " + "phase".ljust(12) + " " + "iter".rjust(8) + " " + "tokens".rjust(8) + " " + "dur(s)".rjust(8) + " provider")
    for r in recent:
        sid = str(r["id"]).rjust(4)
        phase = str(r["phase"] or "?").ljust(12)
        it = (str(r["iteration"]) + "/" + str(r["max_iterations"])).rjust(8)
        tokens = str(r["total_tokens"] or 0).rjust(8)
        dur = str(r["duration_sec"] or 0).rjust(8)
        prov = str(r["llm_provider"] or "?")
        print("  " + sid + " " + phase + " " + it + " " + tokens + " " + dur + " " + prov)


async def section_14_evidence_growth(conn):
    section("5.14 DB cross-reference: evidence size per session")
    try:
        rows = await conn.fetch(
            "SELECT id, phase, iteration, "
            "octet_length(evidence::text) as evidence_bytes "
            "FROM agent_sessions ORDER BY id DESC LIMIT 10"
        )
        print("  " + "id".rjust(4) + " " + "phase".ljust(12) + " " + "iter".rjust(6) + " " + "evidence".rjust(10))
        for r in rows:
            sid = str(r["id"]).rjust(4)
            phase = str(r["phase"] or "?").ljust(12)
            it = str(r["iteration"]).rjust(6)
            eb = r["evidence_bytes"] or 0
            if eb < 1024:
                size_str = str(eb) + "B"
            elif eb < 1024*1024:
                size_str = str(round(eb/1024, 1)) + "KB"
            else:
                size_str = str(round(eb/1024/1024, 1)) + "MB"
            print("  " + sid + " " + phase + " " + it + " " + size_str.rjust(10))
    except Exception as e:
        print("  ERR: " + str(e)[:150])


async def section_15_verification_rules_referenced(conn):
    section("5.15 Verification rules referenced by code (cross-check)")
    try:
        rules = await conn.fetch(
            "SELECT id, pattern, rule_type, on_fail, priority FROM agent_verification_rules ORDER BY priority DESC, id"
        )

        # Read verification.py and look for hints about rule application
        path = os.path.join(AGENT_DIR, "verification.py")
        ver_content = read_file(path) if os.path.exists(path) else ""

        print("  Total rules: " + str(len(rules)))
        print("  verification.py refers to:")
        # Look for "agent_verification_rules" mentions
        for i, line in enumerate(ver_content.splitlines(), 1):
            stripped = line.strip()
            if "agent_verification_rules" in line or "rule_type" in line or "on_fail" in line or "priority" in line:
                if not stripped.startswith("#"):
                    print("    L" + str(i) + ": " + truncate(stripped, 90))
    except Exception as e:
        print("  ERR: " + str(e)[:150])


async def main():
    header("TASK 05 - Agent loop deep dive")

    files = await section_01_files_overview()
    await section_02_loop_py_structure()
    await section_03_loop_py_complexity()
    await section_04_loop_py_phases()
    await section_05_loop_py_critical_branches()
    await section_06_loop_db_writes()
    await section_07_loop_subprocess()
    await section_08_verification_py()
    await section_09_evidence_py()
    await section_10_autonomy_py()
    await section_11_tools_py()
    await section_12_prompts_py()

    conn = await connect_db()
    await section_13_db_session_pattern(conn)
    await section_14_evidence_growth(conn)
    await section_15_verification_rules_referenced(conn)
    await conn.close()

    print()
    print("=" * 70)
    print(" END TASK 05 RECON")
    print("=" * 70)


asyncio.run(main())
