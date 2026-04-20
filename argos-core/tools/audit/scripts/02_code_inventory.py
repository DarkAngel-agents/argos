"""
TASK 02 - Code inventory + anti-patterns static analysis

Read-only. Scan Python code in argos-core subdirs: agent, api, llm, tools.
Output structured text on stdout. Claude Code reads and writes report.
"""
import ast
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import header, section, truncate, ARGOS_CORE

TARGET_DIRS = ["agent", "api", "llm", "tools"]


def find_py_files(base):
    out = []
    for root, dirs, files in os.walk(base):
        if "__pycache__" in root or "/audit/" in root:
            continue
        for f in files:
            if f.endswith(".py"):
                out.append(os.path.join(root, f))
    return sorted(out)


def count_lines(path):
    try:
        with open(path, "r", errors="replace") as f:
            return sum(1 for _ in f)
    except:
        return 0


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


def scan_todos(content):
    findings = []
    for i, line in enumerate(content.splitlines(), 1):
        for marker in ["TODO", "FIXME", "XXX", "HACK", "BUG"]:
            if marker in line:
                stripped = line.strip()
                if stripped.startswith("#") or "# " + marker in line or "#" + marker in line:
                    findings.append((i, marker, truncate(stripped, 100)))
                    break
    return findings


def scan_bare_except(tree):
    findings = []
    if tree is None:
        return findings
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                findings.append((node.lineno, "bare except:"))
            elif isinstance(node.type, ast.Name) and node.type.id == "Exception":
                has_pass = len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
                if has_pass:
                    findings.append((node.lineno, "except Exception: pass"))
    return findings


def scan_prints_without_code(content):
    findings = []
    pattern_good = re.compile(r"""print\(f?["']\[([A-Z_]+(\s+\d+)?|[A-Z]+[\s]?[A-Z]*\s*ERROR)\]""")
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "print(" in stripped and not pattern_good.search(stripped):
            findings.append((i, truncate(stripped, 90)))
    return findings[:20]


def scan_hardcoded_values(content):
    findings = []
    ip_pattern = re.compile(r'"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"')
    port_pattern = re.compile(r"port\s*=\s*(\d{4,5})", re.IGNORECASE)
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for m in ip_pattern.finditer(line):
            findings.append((i, "IP", m.group(1), truncate(stripped, 80)))
        for m in port_pattern.finditer(line):
            if m.group(1) not in ("8000", "5432", "5433"):
                findings.append((i, "port", m.group(1), truncate(stripped, 80)))
    return findings[:15]


def scan_long_functions(tree, min_lines=80):
    findings = []
    if tree is None:
        return findings
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, "end_lineno") and node.end_lineno:
                length = node.end_lineno - node.lineno
                if length >= min_lines:
                    findings.append((node.lineno, node.name, length))
    return findings


def scan_sql_fstrings(content):
    findings = []
    pattern = re.compile(r"""(execute|fetch|fetchval|fetchrow)\s*\(\s*f["']""")
    for i, line in enumerate(content.splitlines(), 1):
        if pattern.search(line):
            findings.append((i, truncate(line.strip(), 100)))
    return findings[:10]


def scan_globals(tree):
    findings = []
    if tree is None:
        return findings
    for node in ast.walk(tree):
        if isinstance(node, ast.Global):
            findings.append((node.lineno, ", ".join(node.names)))
    return findings


def main():
    header("TASK 02 - Code inventory + anti-patterns")

    all_files = []
    per_dir = {}
    for d in TARGET_DIRS:
        base = os.path.join(ARGOS_CORE, d)
        if not os.path.exists(base):
            per_dir[d] = []
            continue
        files = find_py_files(base)
        per_dir[d] = files
        all_files.extend(files)

    total_lines = 0
    total_bytes = 0
    file_stats = []
    for f in all_files:
        lines = count_lines(f)
        try:
            size = os.path.getsize(f)
        except:
            size = 0
        total_lines += lines
        total_bytes += size
        file_stats.append((f, lines, size))

    section("2.1 Summary")
    print("  Total Python files (in scope): " + str(len(all_files)))
    print("  Total lines:                   " + str(total_lines))
    print("  Total bytes:                   " + str(total_bytes))
    for d in TARGET_DIRS:
        files = per_dir[d]
        lines = sum(count_lines(f) for f in files)
        print("  " + d.ljust(8) + ": " + str(len(files)).rjust(3) + " files, " + str(lines).rjust(6) + " lines")

    section("2.2 Largest files (top 15)")
    file_stats.sort(key=lambda x: -x[1])
    for f, lines, size in file_stats[:15]:
        rel = f.replace(ARGOS_CORE + "/", "")
        print("  " + str(lines).rjust(5) + " lines  " + str(size).rjust(7) + " bytes  " + rel)

    section("2.3 Smallest files (likely stubs or dead code)")
    small = [x for x in file_stats if x[1] < 20 and not x[0].endswith("__init__.py")]
    if small:
        for f, lines, size in small:
            rel = f.replace(ARGOS_CORE + "/", "")
            print("  " + str(lines).rjust(5) + " lines  " + rel)
    else:
        print("  [none below 20 lines]")

    section("2.4 TODOs / FIXMEs / HACKs / BUGs")
    todo_count = 0
    by_file = defaultdict(list)
    for f, _, _ in file_stats:
        content = read_file(f)
        todos = scan_todos(content)
        if todos:
            by_file[f] = todos
            todo_count += len(todos)
    print("  Total found: " + str(todo_count) + " in " + str(len(by_file)) + " files")
    print()
    for f, todos in sorted(by_file.items()):
        rel = f.replace(ARGOS_CORE + "/", "")
        print("  " + rel + " (" + str(len(todos)) + ")")
        for line_no, marker, text in todos[:5]:
            print("    L" + str(line_no) + " [" + marker + "] " + text)
        if len(todos) > 5:
            print("    ... and " + str(len(todos) - 5) + " more")

    section("2.5 Bare except / except Exception: pass")
    bare_count = 0
    for f, _, _ in file_stats:
        content = read_file(f)
        tree = parse_ast(content, f)
        findings = scan_bare_except(tree)
        if findings:
            rel = f.replace(ARGOS_CORE + "/", "")
            for line_no, what in findings:
                print("  " + rel + " L" + str(line_no) + ": " + what)
                bare_count += 1
    if bare_count == 0:
        print("  [none found]")
    else:
        print()
        print("  Total: " + str(bare_count))

    section("2.6 Prints without [CATEG NNN] marker (first 20 per file)")
    total_bad_prints = 0
    by_file_prints = defaultdict(list)
    for f, _, _ in file_stats:
        content = read_file(f)
        findings = scan_prints_without_code(content)
        if findings:
            by_file_prints[f] = findings
            total_bad_prints += len(findings)
    print("  Total prints without marker: " + str(total_bad_prints))
    print()
    for f, findings in sorted(by_file_prints.items())[:10]:
        rel = f.replace(ARGOS_CORE + "/", "")
        print("  " + rel + " (" + str(len(findings)) + ")")
        for line_no, text in findings[:5]:
            print("    L" + str(line_no) + ": " + text)

    section("2.7 Hardcoded IPs / ports in code")
    for f, _, _ in file_stats:
        content = read_file(f)
        findings = scan_hardcoded_values(content)
        if findings:
            rel = f.replace(ARGOS_CORE + "/", "")
            print("  " + rel)
            for line_no, kind, val, text in findings:
                print("    L" + str(line_no) + " [" + kind + "=" + val + "] " + text)

    section("2.8 Long functions (>= 80 lines)")
    long_count = 0
    for f, _, _ in file_stats:
        content = read_file(f)
        tree = parse_ast(content, f)
        findings = scan_long_functions(tree, min_lines=80)
        if findings:
            rel = f.replace(ARGOS_CORE + "/", "")
            for line_no, name, length in findings:
                print("  " + rel + " L" + str(line_no) + " " + name + "() = " + str(length) + " lines")
                long_count += 1
    if long_count == 0:
        print("  [none found]")
    else:
        print()
        print("  Total: " + str(long_count))

    section("2.9 SQL f-strings (injection risk)")
    sql_count = 0
    for f, _, _ in file_stats:
        content = read_file(f)
        findings = scan_sql_fstrings(content)
        if findings:
            rel = f.replace(ARGOS_CORE + "/", "")
            for line_no, text in findings:
                print("  " + rel + " L" + str(line_no) + ": " + text)
                sql_count += 1
    if sql_count == 0:
        print("  [none found]")
    else:
        print()
        print("  Total: " + str(sql_count))

    section("2.10 global statements")
    global_count = 0
    for f, _, _ in file_stats:
        content = read_file(f)
        tree = parse_ast(content, f)
        findings = scan_globals(tree)
        if findings:
            rel = f.replace(ARGOS_CORE + "/", "")
            for line_no, names in findings:
                print("  " + rel + " L" + str(line_no) + ": global " + names)
                global_count += 1
    if global_count == 0:
        print("  [none found]")

    section("2.11 Parse errors (syntax issues)")
    parse_errors = 0
    for f, _, _ in file_stats:
        content = read_file(f)
        try:
            ast.parse(content, filename=f)
        except SyntaxError as e:
            rel = f.replace(ARGOS_CORE + "/", "")
            print("  " + rel + " L" + str(e.lineno) + ": " + str(e.msg))
            parse_errors += 1
    if parse_errors == 0:
        print("  [none]")

    section("2.12 Files without docstring")
    no_doc = []
    for f, _, _ in file_stats:
        content = read_file(f)
        tree = parse_ast(content, f)
        if tree is None:
            continue
        doc = ast.get_docstring(tree)
        if not doc and not f.endswith("__init__.py"):
            rel = f.replace(ARGOS_CORE + "/", "")
            no_doc.append(rel)
    print("  Files without module docstring: " + str(len(no_doc)))
    for rel in no_doc[:15]:
        print("    " + rel)
    if len(no_doc) > 15:
        print("    ... and " + str(len(no_doc) - 15) + " more")

    print()
    print("=" * 70)
    print(" END TASK 02 RECON")
    print("=" * 70)


main()
