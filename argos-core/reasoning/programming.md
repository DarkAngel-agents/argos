# ARGOS Programming Reasoning
# Domain: Python, bash, API development, DB queries
# NEVER auto-modified. Edit manually only.

## BEFORE WRITING CODE
- Ask before writing anything over 20 lines
- Small functions, one thing at a time
- Verify existing code before modifying: read first, then propose

## PYTHON
- Multiline file edits: always Python, never sed
- File write pattern: read -> modify in memory -> write back
- Use repr() to verify string content before writing
- venv required for pip installs on NixOS
- conda: use conda-shell wrapper, not direct conda

## BASH
- Error handling: set -e or explicit || exit 1
- Error codes [E001]/[E002] in all scripts
- No sleep in commands unless absolutely necessary
- Heredoc forbidden with docker exec (use docker cp + psql -f)
- Quote variables: "$VAR" not $VAR

## API (ARGOS)
- Base: http://11.11.11.111:666
- Health: GET /health
- Chat: POST /chat
- All endpoints documented in api/main.py

## VIKUNJA API (quirk)
- PUT = create (non-standard)
- POST = update (non-standard)
- Token expires ~15min, re-login if 401

## DATABASE
- Always propose schema changes before implementing
- Test on claudedb, never on production without approval
- Use transactions for multi-step changes: BEGIN; ... COMMIT;

## ERROR PATTERN
STATUS: FAIL
CAUSE: SyntaxError / ImportError / ConnectionError
ACTION: check exact line, verify imports, check if service is up before blaming code

## PYTHON FIRST RULE
For ANY file operation, system query, scan, or multi-step task: USE PYTHON, not bash.
Reasons:
- Precise error codes pointing directly to the problem
- No shell escaping issues
- Readable logic, not one-liners
- Error handling built-in, not || and &&
- Fewer tokens total (no retries from ambiguous errors)

Pattern:
```python
import os, sys
try:
    result = do_something()
    print(f"OK: {result}")
except SpecificError as e:
    print(f"[E001] CAUSE: {e}")
    sys.exit(1)
except Exception as e:
    print(f"[E002] UNEXPECTED: {e}")
    sys.exit(2)
```

ONLY use bash for: single-command checks, pipes that are trivial, aliases.
NEVER use bash for: file edits, multi-step logic, anything that could fail silently.
