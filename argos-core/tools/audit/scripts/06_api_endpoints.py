"""
TASK 06 - API endpoints + middleware deep dive

Read-only. Analyzes:
- All endpoints in api/ (FastAPI decorators, methods, paths)
- Middleware stack
- Error handling per route
- chat.py specific: send_message, _execute_tool dispatch
- main.py lifespan + DB pool init
- Dependencies on agent/loop, llm/providers
- JSON request/response models
- Rate limiting / auth presence
"""
import ast
import asyncio
import os
import re
import sys
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import header, section, truncate, ARGOS_CORE

API_DIR = os.path.join(ARGOS_CORE, "api")


def find_py_files(base):
    out = []
    for root, dirs, files in os.walk(base):
        if "__pycache__" in root:
            continue
        for f in files:
            if f.endswith(".py"):
                out.append(os.path.join(root, f))
    return sorted(out)


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


def find_endpoints(content):
    """Find FastAPI route decorators and the function below them."""
    endpoints = []
    lines = content.splitlines()
    decorator_pattern = re.compile(
        r"@(?:app|router)\.(get|post|put|delete|patch|head|options|websocket)\s*\(\s*[\"']([^\"']+)[\"']"
    )
    func_pattern = re.compile(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(")

    for i, line in enumerate(lines):
        m = decorator_pattern.search(line)
        if m:
            method = m.group(1).upper()
            path = m.group(2)
            # Find the function name on next non-decorator non-empty line
            func_name = None
            for j in range(i + 1, min(i + 10, len(lines))):
                next_line = lines[j].strip()
                if next_line.startswith("@"):
                    continue
                fm = func_pattern.match(lines[j])
                if fm:
                    func_name = fm.group(1)
                    break
                if next_line and not next_line.startswith("#"):
                    break
            endpoints.append({
                "line": i + 1,
                "method": method,
                "path": path,
                "func": func_name or "?",
            })
    return endpoints


def find_middleware(content):
    """Find FastAPI middleware registration."""
    findings = []
    patterns = [
        re.compile(r"@app\.middleware\s*\(\s*[\"'](\w+)[\"']"),
        re.compile(r"app\.add_middleware\s*\(\s*(\w+)"),
    ]
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for pat in patterns:
            m = pat.search(line)
            if m:
                findings.append((i, m.group(1), truncate(stripped, 80)))
                break
    return findings


def find_router_includes(content):
    """Find router includes (app.include_router(...))."""
    findings = []
    pattern = re.compile(r"app\.include_router\s*\(\s*(\w+)")
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        m = pattern.search(line)
        if m:
            findings.append((i, m.group(1), truncate(stripped, 80)))
    return findings


def find_imports(content, target_modules):
    """Find imports from specific modules."""
    findings = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for mod in target_modules:
            if "from " + mod in line or "import " + mod in line:
                findings.append((i, mod, truncate(stripped, 90)))
                break
    return findings


def find_pydantic_models(tree):
    """Find Pydantic BaseModel subclasses."""
    models = []
    if tree is None:
        return models
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                base_name = None
                if isinstance(base, ast.Name):
                    base_name = base.id
                elif isinstance(base, ast.Attribute):
                    base_name = base.attr
                if base_name in ("BaseModel", "Model"):
                    fields = []
                    for child in node.body:
                        if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                            fields.append(child.target.id)
                    models.append((node.name, node.lineno, fields))
                    break
    return models


def find_http_exceptions(content):
    """Find HTTPException raises and status codes."""
    findings = []
    pattern = re.compile(r"HTTPException\s*\(\s*status_code\s*=\s*(\d+)")
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        m = pattern.search(line)
        if m:
            findings.append((i, int(m.group(1)), truncate(stripped, 90)))
    return findings


def find_auth_patterns(content):
    """Find authentication / authorization patterns."""
    findings = []
    keywords = ["Depends", "OAuth2", "APIKey", "HTTPBearer", "current_user", "verify_token", "require_auth"]
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for kw in keywords:
            if kw in line:
                findings.append((i, kw, truncate(stripped, 90)))
                break
    return findings


def find_cors_settings(content):
    """Find CORS middleware configuration."""
    findings = []
    if "CORSMiddleware" in content or "allow_origins" in content:
        for i, line in enumerate(content.splitlines(), 1):
            if "CORSMiddleware" in line or "allow_origins" in line or "allow_methods" in line:
                findings.append((i, truncate(line.strip(), 90)))
    return findings


def find_db_access_patterns(content):
    """Find DB access patterns to identify queries."""
    findings = []
    pattern = re.compile(r"(execute|fetch|fetchval|fetchrow)\s*\(")
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if pattern.search(line):
            findings.append((i, truncate(stripped, 90)))
    return findings


def find_streaming_endpoints(content):
    """Find SSE / streaming patterns."""
    findings = []
    keywords = ["StreamingResponse", "EventSourceResponse", "yield", "AsyncGenerator", "text/event-stream"]
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for kw in keywords:
            if kw in line:
                findings.append((i, kw, truncate(stripped, 80)))
                break
    return findings


def find_anthropic_calls(content):
    """Find Anthropic API client calls."""
    findings = []
    pattern = re.compile(r"(anthropic\.Anthropic|client\.messages\.create|messages\.create)")
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if pattern.search(line):
            findings.append((i, truncate(stripped, 100)))
    return findings


def find_global_state(tree):
    """Find global declarations."""
    findings = []
    if tree is None:
        return findings
    for node in ast.walk(tree):
        if isinstance(node, ast.Global):
            findings.append((node.lineno, ", ".join(node.names)))
    return findings


def section_01_files_overview():
    section("6.1 api/ files overview")
    if not os.path.exists(API_DIR):
        print("  [MISSING] api/ directory")
        return []

    files = find_py_files(API_DIR)
    print("  Total files: " + str(len(files)))
    print()

    stats = []
    total_lines = 0
    for f in files:
        try:
            with open(f) as fh:
                lines = sum(1 for _ in fh)
        except:
            lines = 0
        size = os.path.getsize(f)
        stats.append((f, lines, size))
        total_lines += lines

    stats.sort(key=lambda x: -x[1])
    for f, lines, size in stats:
        rel = f.replace(ARGOS_CORE + "/", "")
        print("  " + str(lines).rjust(5) + " lines  " + str(size).rjust(7) + " bytes  " + rel)
    print()
    print("  TOTAL: " + str(total_lines) + " lines")
    return stats


def section_02_all_endpoints(stats):
    section("6.2 All endpoints inventory")
    all_endpoints = []
    by_file = defaultdict(list)

    for f, _, _ in stats:
        content = read_file(f)
        eps = find_endpoints(content)
        if eps:
            rel = f.replace(ARGOS_CORE + "/", "")
            for ep in eps:
                ep["file"] = rel
                all_endpoints.append(ep)
                by_file[rel].append(ep)

    print("  Total endpoints: " + str(len(all_endpoints)))
    print()

    # Distribution by method
    by_method = Counter()
    for ep in all_endpoints:
        by_method[ep["method"]] += 1
    print("  By HTTP method:")
    for m, n in by_method.most_common():
        print("    " + m.ljust(10) + " : " + str(n))
    print()

    # By file
    print("  Endpoints per file:")
    for f, eps in sorted(by_file.items()):
        print("    " + f + " (" + str(len(eps)) + ")")
        for ep in eps[:50]:
            print("      L" + str(ep["line"]).rjust(4) + " " + ep["method"].ljust(7) + " " + ep["path"].ljust(45) + " -> " + ep["func"])

    return all_endpoints


def section_03_middleware(stats):
    section("6.3 Middleware stack")
    found_any = False
    for f, _, _ in stats:
        content = read_file(f)
        mws = find_middleware(content)
        if mws:
            rel = f.replace(ARGOS_CORE + "/", "")
            print("  " + rel)
            for line_no, name, text in mws:
                print("    L" + str(line_no) + " [" + name + "] " + text)
            found_any = True
    if not found_any:
        print("  [INFO] No middleware registrations found in api/ files")


def section_04_routers(stats):
    section("6.4 Router includes")
    for f, _, _ in stats:
        content = read_file(f)
        routers = find_router_includes(content)
        if routers:
            rel = f.replace(ARGOS_CORE + "/", "")
            print("  " + rel)
            for line_no, name, text in routers:
                print("    L" + str(line_no) + " include_router(" + name + ")")


def section_05_models(stats):
    section("6.5 Pydantic models per file")
    total_models = 0
    for f, _, _ in stats:
        content = read_file(f)
        tree = parse_ast(content, f)
        models = find_pydantic_models(tree)
        if models:
            rel = f.replace(ARGOS_CORE + "/", "")
            print("  " + rel + " (" + str(len(models)) + ")")
            for name, lineno, fields in models[:10]:
                print("    L" + str(lineno) + " " + name + ": " + ", ".join(fields[:8]))
                total_models += 1
    print()
    print("  Total Pydantic models: " + str(total_models))


def section_06_http_exceptions(stats):
    section("6.6 HTTPException usage per file (status codes)")
    by_status = Counter()
    by_file_count = defaultdict(int)
    for f, _, _ in stats:
        content = read_file(f)
        excs = find_http_exceptions(content)
        if excs:
            rel = f.replace(ARGOS_CORE + "/", "")
            for line_no, status, text in excs:
                by_status[status] += 1
                by_file_count[rel] += 1

    print("  Distribution by status code:")
    for code, n in sorted(by_status.items()):
        print("    " + str(code).ljust(5) + ": " + str(n))
    print()
    print("  Per file:")
    for rel, n in sorted(by_file_count.items(), key=lambda x: -x[1]):
        print("    " + rel.ljust(35) + " : " + str(n))


def section_07_auth_presence(stats):
    section("6.7 Auth / Depends usage per file")
    by_file = defaultdict(list)
    for f, _, _ in stats:
        content = read_file(f)
        auth = find_auth_patterns(content)
        if auth:
            rel = f.replace(ARGOS_CORE + "/", "")
            by_file[rel] = auth

    print("  Files using Depends/auth patterns: " + str(len(by_file)))
    print()
    for rel, items in sorted(by_file.items()):
        print("  " + rel + " (" + str(len(items)) + ")")
        for line_no, kw, text in items[:5]:
            print("    L" + str(line_no) + " [" + kw + "] " + text)

    if not by_file:
        print("  [INFO] No auth/Depends patterns found in api/ files")


def section_08_cors(stats):
    section("6.8 CORS configuration")
    found = False
    for f, _, _ in stats:
        content = read_file(f)
        cors = find_cors_settings(content)
        if cors:
            rel = f.replace(ARGOS_CORE + "/", "")
            print("  " + rel)
            for line_no, text in cors[:10]:
                print("    L" + str(line_no) + ": " + text)
            found = True
    if not found:
        print("  [INFO] No CORS configuration found")


def section_09_chat_py_deep():
    section("6.9 chat.py deep analysis")
    path = os.path.join(API_DIR, "chat.py")
    if not os.path.exists(path):
        print("  [MISSING] chat.py")
        return

    content = read_file(path)
    tree = parse_ast(content, path)

    print("  Total lines: " + str(len(content.splitlines())))

    # Top functions by length
    funcs = []
    if tree:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end = getattr(node, "end_lineno", node.lineno)
                length = end - node.lineno + 1
                is_async = isinstance(node, ast.AsyncFunctionDef)
                funcs.append((node.name, node.lineno, end, length, is_async))

    funcs.sort(key=lambda x: -x[3])
    print()
    print("  Top 15 functions by length:")
    for name, lineno, end, length, is_async in funcs[:15]:
        prefix = "async " if is_async else ""
        print("    " + str(length).rjust(5) + " lines  L" + str(lineno).rjust(4) + "-" + str(end).rjust(4) + "  " + prefix + name + "()")

    # Anthropic calls
    print()
    print("  Anthropic API call sites:")
    anth = find_anthropic_calls(content)
    for line_no, text in anth[:10]:
        print("    L" + str(line_no) + ": " + text)

    # DB access patterns
    print()
    db = find_db_access_patterns(content)
    print("  DB access calls: " + str(len(db)))
    for line_no, text in db[:15]:
        print("    L" + str(line_no) + ": " + text)


def section_10_main_py_lifespan():
    section("6.10 main.py lifespan + initialization")
    path = os.path.join(API_DIR, "main.py")
    if not os.path.exists(path):
        print("  [MISSING] main.py")
        return

    content = read_file(path)
    tree = parse_ast(content, path)
    print("  Total lines: " + str(len(content.splitlines())))

    # Find lifespan function
    funcs = []
    if tree:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end = getattr(node, "end_lineno", node.lineno)
                length = end - node.lineno + 1
                if "lifespan" in node.name.lower() or "startup" in node.name.lower() or "shutdown" in node.name.lower():
                    funcs.append((node.name, node.lineno, end, length))

    if funcs:
        print()
        print("  Lifecycle functions:")
        for name, lineno, end, length in funcs:
            print("    L" + str(lineno) + "-" + str(end) + " " + name + "() = " + str(length) + " lines")

    # Look for DB pool init
    print()
    print("  DB pool initialization patterns:")
    pool_pattern = re.compile(r"(create_pool|asyncpg\.connect|asyncpg\.create_pool)")
    for i, line in enumerate(content.splitlines(), 1):
        if pool_pattern.search(line):
            print("    L" + str(i) + ": " + truncate(line.strip(), 100))

    # Globals
    globs = find_global_state(tree)
    print()
    print("  Global declarations: " + str(len(globs)))
    for line_no, names in globs:
        print("    L" + str(line_no) + ": global " + names)


def section_11_streaming(stats):
    section("6.11 Streaming / SSE endpoints")
    by_file = defaultdict(list)
    for f, _, _ in stats:
        content = read_file(f)
        sse = find_streaming_endpoints(content)
        if sse:
            rel = f.replace(ARGOS_CORE + "/", "")
            by_file[rel] = sse

    print("  Files with streaming patterns: " + str(len(by_file)))
    print()
    for rel, items in sorted(by_file.items()):
        print("  " + rel + " (" + str(len(items)) + ")")
        for line_no, kw, text in items[:5]:
            print("    L" + str(line_no) + " [" + kw + "] " + text)


def section_12_imports_from_internal(stats):
    section("6.12 Cross-module imports (api/ depends on)")
    target_modules = ["agent", "llm", "tools", "reasoning"]
    by_file = defaultdict(list)
    for f, _, _ in stats:
        content = read_file(f)
        imps = find_imports(content, target_modules)
        if imps:
            rel = f.replace(ARGOS_CORE + "/", "")
            by_file[rel] = imps

    print("  Files importing from agent/llm/tools/reasoning: " + str(len(by_file)))
    print()
    for rel, items in sorted(by_file.items()):
        print("  " + rel + " (" + str(len(items)) + ")")
        for line_no, mod, text in items[:5]:
            print("    L" + str(line_no) + " [" + mod + "] " + text)


def section_13_executor_backup_check(stats):
    section("6.13 executor.py + backup.py + code_runner.py specific")
    targets = ["executor.py", "backup.py", "code_runner.py"]
    for tgt in targets:
        path = os.path.join(API_DIR, tgt)
        if not os.path.exists(path):
            print("  [MISSING] " + tgt)
            continue
        content = read_file(path)
        tree = parse_ast(content, path)
        funcs = []
        if tree:
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    end = getattr(node, "end_lineno", node.lineno)
                    length = end - node.lineno + 1
                    funcs.append((node.name, node.lineno, length))
        funcs.sort(key=lambda x: -x[2])
        print()
        print("  " + tgt + " (" + str(len(content.splitlines())) + " lines)")
        for name, lineno, length in funcs[:8]:
            print("    " + str(length).rjust(4) + " lines  L" + str(lineno).rjust(4) + "  " + name + "()")


def section_14_endpoint_complexity_summary(all_endpoints):
    section("6.14 Endpoint complexity summary")
    # Group endpoints by file
    by_file = defaultdict(list)
    for ep in all_endpoints:
        by_file[ep["file"]].append(ep)

    print("  File-level summary (top 10 by endpoint count):")
    sorted_files = sorted(by_file.items(), key=lambda x: -len(x[1]))
    for rel, eps in sorted_files[:10]:
        methods = Counter([ep["method"] for ep in eps])
        method_str = " ".join([m + "=" + str(n) for m, n in methods.most_common()])
        print("    " + rel.ljust(35) + " : " + str(len(eps)).rjust(3) + " endpoints (" + method_str + ")")


def main():
    header("TASK 06 - API endpoints + middleware deep dive")

    stats = section_01_files_overview()
    if not stats:
        return

    all_endpoints = section_02_all_endpoints(stats)
    section_03_middleware(stats)
    section_04_routers(stats)
    section_05_models(stats)
    section_06_http_exceptions(stats)
    section_07_auth_presence(stats)
    section_08_cors(stats)
    section_09_chat_py_deep()
    section_10_main_py_lifespan()
    section_11_streaming(stats)
    section_12_imports_from_internal(stats)
    section_13_executor_backup_check(stats)
    section_14_endpoint_complexity_summary(all_endpoints)

    print()
    print("=" * 70)
    print(" END TASK 06 RECON")
    print("=" * 70)


main()
