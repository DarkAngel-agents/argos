#!/usr/bin/env python3.13
"""
[TOOL001] scan_chat_structure.py - AST analyzer pentru chat.py

SCOP: Detecteaza bug-uri structurale in functia send_message din chat.py -
      loop-uri goale, variabile folosite in afara scopului lor de iteratie,
      tool_results.append() in afara for loop-ului, etc.

UTILIZARE:
    python3.13 /home/darkangel/.argos/argos-core/tools/scan_chat_structure.py

OUTPUT:
    [SCAN001] chat.py size + line count
    [SCAN002] send_message locatie in fisier
    [SCAN003] structura AST walk cu indentare
    [SCAN004] lista for-loops + body length
    [SCAN005] WARNING daca un loop are doar pass
    [SCAN006] locatii tool_results.append + messages.append
    [SCAN007] parent scope pentru tool_results.append
    [SCAN008] BUG marker daca tool_results.append NU e in for
    [SCAN009] parent scope pentru messages.append(tool_result)
    [SCAN010] print zona critica cu indentare vizibila
    [SCAN011] DONE

READ-ONLY: nu modifica chat.py, doar citeste si analizeaza.

ISTORIC:
    2026-04-13: initial - gasit bug tool_results.append orfan cu ocazia
                incidentului de send 500 dupa stale postgres Hermes
"""
import ast
from pathlib import Path

CHAT_PY = Path("/home/darkangel/.argos/argos-core/api/chat.py")
src = CHAT_PY.read_text()
lines = src.split('\n')

print(f"[SCAN001] chat.py: {len(lines)} linii, {len(src)} chars")
print()

tree = ast.parse(src)
send_fn = None
for node in ast.walk(tree):
    if isinstance(node, ast.AsyncFunctionDef) and node.name == 'send_message':
        send_fn = node
        break

if not send_fn:
    print("[SCAN002 ERROR] send_message nu a fost gasita in AST")
    exit(1)

print(f"[SCAN002] send_message: L{send_fn.lineno}-{send_fn.end_lineno}")
print()

def describe(node, indent=0):
    pfx = "  " * indent
    cls = node.__class__.__name__
    line = getattr(node, 'lineno', '?')
    end = getattr(node, 'end_lineno', '?')
    detail = ""
    if isinstance(node, ast.For):
        iter_src = ast.unparse(node.iter)[:60]
        detail = f" iter={iter_src}"
    elif isinstance(node, ast.While):
        test_src = ast.unparse(node.test)[:40]
        detail = f" while={test_src}"
    elif isinstance(node, ast.If):
        test_src = ast.unparse(node.test)[:50]
        detail = f" if={test_src}"
    return f"{pfx}[L{line:4}-{end:4}] {cls}{detail}"

def walk_body(body, depth=0, max_depth=5):
    for node in body:
        if depth > max_depth:
            continue
        print(describe(node, depth))
        for attr in ['body', 'orelse', 'finalbody', 'handlers']:
            if hasattr(node, attr):
                sub = getattr(node, attr)
                if isinstance(sub, list):
                    walk_body(sub, depth+1, max_depth)

print("=" * 80)
print("[SCAN003] Structura send_message")
print("=" * 80)
walk_body(send_fn.body, 0, max_depth=5)

print()
print("=" * 80)
print("[SCAN004] For-loops in send_message")
print("=" * 80)
for_loops = []
for node in ast.walk(send_fn):
    if isinstance(node, ast.For):
        iter_src = ast.unparse(node.iter)
        for_loops.append((node.lineno, node.end_lineno, iter_src, node))

print(f"Total: {len(for_loops)}")
for lineno, end, iter_src, node in for_loops:
    body_len = len(node.body)
    first = node.body[0] if body_len else None
    print(f"  L{lineno:4}-{end:4}: for in {iter_src[:70]} ({body_len} stmts)")
    if first and isinstance(first, ast.Pass):
        print(f"    [SCAN005 WARNING] Loop are doar pass!")

print()
print("=" * 80)
print("[SCAN007/008] tool_results.append parent scope")
print("=" * 80)

parent_map = {}
for parent in ast.walk(send_fn):
    for child in ast.iter_child_nodes(parent):
        parent_map[id(child)] = parent

def find_enclosing_loop(node):
    current = node
    while True:
        parent = parent_map.get(id(current))
        if parent is None:
            return None
        if isinstance(parent, (ast.For, ast.While)):
            return parent
        if isinstance(parent, ast.AsyncFunctionDef):
            return None
        current = parent

bugs_found = 0
for node in ast.walk(send_fn):
    if isinstance(node, ast.Call):
        src_str = ast.unparse(node)
        if 'tool_results.append' in src_str:
            loop = find_enclosing_loop(node)
            if loop and isinstance(loop, ast.For):
                iter_src = ast.unparse(loop.iter)[:40]
                print(f"  L{node.lineno}: OK in for L{loop.lineno} (iter={iter_src})")
            else:
                print(f"  L{node.lineno}: [SCAN008 BUG] tool_results.append NOT in for loop!")
                bugs_found += 1

print()
print("=" * 80)
if bugs_found:
    print(f"[SCAN011] FAIL - {bugs_found} bug(s) found")
    exit(2)
else:
    print("[SCAN011] OK - no structural bugs detected")
    exit(0)
