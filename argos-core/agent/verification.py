"""
ARGOS-Commander verification chain module.

Pure verification logic for the agent loop. Two responsibilities:

1. check_safety_guards(pool, cmd) - PRE-execution safety check.
   Called by loop.py BEFORE autonomy check, BEFORE exec_tool.
   Queries agent_verification_rules for rule_type='custom' AND expected='BLOCK'
   AND priority=1. If any matches the command (via PostgreSQL POSIX ERE regex ~*), the command is
   blocked and the session must be marked failed by the caller.

2. run_verification_chain(pool, cmd, result, exec_fn) - POST-execution verification.
   Called by loop.py after exec_tool returns. Queries all matching non-safety
   rules for the command, dispatches per rule_type, aggregates results, computes
   the effective on_fail action via precedence (abort > escalate > fix > retry),
   and returns a VerificationResult dataclass.

DESIGN PRINCIPLES (do not violate):
- This module is PURE: it returns dataclasses, never writes to agent_sessions
  or evidence. The caller (loop.py) is responsible for persisting state.
- This module has zero coupling with prompts.py, providers.py, tools.py, or
  loop.py. Only asyncpg + stdlib.
- This module is testable in isolation: build a result dict by hand, pass a
  pool, get a VerificationResult back. No need to spin up a full session.

result dict shape (as returned by agent.tools.exec_tool):
    {
        "cmd": str,
        "machine": str,
        "exit_code": int,
        "stdout": str,
        "stderr": str,
        "duration_ms": int,
    }

Deferred to Session 5+ (see Vikunja proposal #222):
- file_exists rule_type: stub returns passed=True
- http_200 rule_type: stub returns passed=True
Both require target argument extraction from the executed command, which is
an architectural decision out of scope for Session 4. exec_fn is reserved in
the public signature so adding the implementation later does not break callers.

References:
- Vikunja #219 - Session 4 design (full Faza E)
- Vikunja #222 - file_exists/http_200 path extraction proposal
- Skill #92 - argos-agent/argos-agent-loop-architecture
"""

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, List, Optional

import asyncpg


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# on_fail precedence: higher value = stricter, wins when multiple rules fail.
# See task #219 "on_fail conflict resolution".
ON_FAIL_PRECEDENCE = {
    "abort": 4,
    "escalate": 3,
    "fix": 2,
    "retry": 1,
}

# Stub note shared by file_exists and http_200 deferred handlers.
DEFERRED_NOTE = "deferred to Session 5+, see Vikunja proposal #222"


# ---------------------------------------------------------------------------
# Dataclasses (public)
# ---------------------------------------------------------------------------


@dataclass
class SafetyResult:
    """Result of pre-execution safety guard check.

    blocked=True means the command MUST NOT be executed. The caller (loop.py)
    should mark the session failed with reason 'safety_guard_blocked' and
    write E_SAFETY_BLOCK to evidence.errors plus a 'safety_block' decision
    to evidence.decisions.
    """

    blocked: bool
    rule_id: Optional[int] = None
    rule_pattern: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class MatchedRule:
    """One rule that matched a command, with its check result.

    Both passing and failing matched rules are returned in
    VerificationResult.matched_rules so loop.py can write the full picture
    to evidence.verifications, not just failures.
    """

    rule_id: int
    pattern: str
    rule_type: str
    expected: str
    on_fail: str
    priority: int
    passed: bool
    note: str


@dataclass
class VerificationResult:
    """Aggregate result of a verification chain run.

    passed=True iff every matched rule passed (or zero rules matched).
    effective_on_fail is None when passed=True, otherwise the strictest
    on_fail value across failed_rules per ON_FAIL_PRECEDENCE.
    """

    passed: bool
    matched_rules: List[MatchedRule] = field(default_factory=list)
    failed_rules: List[MatchedRule] = field(default_factory=list)
    effective_on_fail: Optional[str] = None
    note: str = ""


# ---------------------------------------------------------------------------
# Public function 1: pre-execution safety check
# ---------------------------------------------------------------------------


async def check_safety_guards(
    pool: asyncpg.Pool,
    cmd: str,
) -> SafetyResult:
    """Check command against priority=1 custom safety guard rules.

    Called PRE-execution by loop.py. Returns blocked=True if any safety guard
    matches. POSIX ERE regex matching (~* case-insensitive) is done SQL-side using the rule's pattern column.

    Raises asyncpg.PostgresError on DB failure - the caller must catch it
    and mark the session failed (E_SAFETY_DB). We never silently allow
    execution when safety verification cannot run.
    """
    query = """
        SELECT id, pattern, description
        FROM agent_verification_rules
        WHERE active = TRUE
          AND rule_type = 'custom'
          AND expected = 'BLOCK'
          AND priority = 1
          AND $1 ~* pattern
        LIMIT 1
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, cmd)

    if row is None:
        return SafetyResult(blocked=False)

    return SafetyResult(
        blocked=True,
        rule_id=row["id"],
        rule_pattern=row["pattern"],
        reason=f"safety guard rule {row['id']} matched: {row['description'] or row['pattern']}",
    )


# ---------------------------------------------------------------------------
# Public function 2: post-execution verification chain
# ---------------------------------------------------------------------------


async def run_verification_chain(
    pool: asyncpg.Pool,
    cmd: str,
    result: dict,
    exec_fn: Optional[Callable[[str], Awaitable[dict]]] = None,
) -> VerificationResult:
    """Run all matching verification rules against an executed command.

    Excludes safety guards (priority=1, rule_type='custom') because those are
    pre-execution gates and have already been checked by check_safety_guards
    before this function runs.

    For each matching rule, dispatches per rule_type:
    - exit_code: compare result['exit_code'] to int(expected)
    - grep: substring check for expected in result['stdout']
    - grep_not: substring NOT-in check
    - file_exists: STUB, returns passed=True (deferred S5+)
    - http_200: STUB, returns passed=True (deferred S5+)

    exec_fn is reserved for the future file_exists/http_200 implementation
    in Session 5+. It is not invoked in Session 4. Pass None.

    Raises asyncpg.PostgresError on DB query failure. The caller must catch
    and mark the session failed (E_VERIFY_DB). Verification chain never
    silently passes when DB is unreachable.
    """
    query = """
        SELECT id, pattern, rule_type, expected, on_fail, priority
        FROM agent_verification_rules
        WHERE active = TRUE
          AND priority > 1
          AND rule_type IN ('exit_code', 'grep', 'grep_not', 'file_exists', 'http_200')
          AND $1 ~* pattern
        ORDER BY priority ASC, id ASC
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, cmd)

    # Zero matches - default to pass (no strict_verification mode in S4).
    if not rows:
        return VerificationResult(
            passed=True,
            matched_rules=[],
            failed_rules=[],
            effective_on_fail=None,
            note="no rules matched, treating as pass",
        )

    matched: List[MatchedRule] = []
    for row in rows:
        rule_id = row["id"]
        pattern = row["pattern"]
        rule_type = row["rule_type"]
        expected = row["expected"]
        on_fail = row["on_fail"]
        priority = row["priority"]

        if rule_type == "exit_code":
            passed, note = _check_exit_code(result, expected)
        elif rule_type == "grep":
            passed, note = _check_grep(result, expected)
        elif rule_type == "grep_not":
            passed, note = _check_grep_not(result, expected)
        elif rule_type == "file_exists":
            passed, note = _check_deferred("file_exists")
        elif rule_type == "http_200":
            passed, note = _check_deferred("http_200")
        else:
            # Defensive: unknown rule_type. Mark failed but do not crash.
            passed = False
            note = f"unknown rule_type '{rule_type}'"

        matched.append(
            MatchedRule(
                rule_id=rule_id,
                pattern=pattern,
                rule_type=rule_type,
                expected=expected,
                on_fail=on_fail,
                priority=priority,
                passed=passed,
                note=note,
            )
        )

    failed = [mr for mr in matched if not mr.passed]

    if not failed:
        return VerificationResult(
            passed=True,
            matched_rules=matched,
            failed_rules=[],
            effective_on_fail=None,
            note=f"{len(matched)} rule(s) matched, all passed",
        )

    effective = _compute_effective_on_fail(failed)
    return VerificationResult(
        passed=False,
        matched_rules=matched,
        failed_rules=failed,
        effective_on_fail=effective,
        note=f"{len(failed)}/{len(matched)} rule(s) failed, effective on_fail={effective}",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_exit_code(result: dict, expected: str) -> tuple:
    """Compare result['exit_code'] to int(expected). Return (passed, note)."""
    actual = result.get("exit_code")
    if actual is None:
        return (False, "result missing exit_code field")

    try:
        expected_int = int(expected)
    except (TypeError, ValueError):
        return (False, f"invalid expected value '{expected}' for exit_code rule")

    if actual == expected_int:
        return (True, f"exit_code {actual} == expected {expected_int}")
    return (False, f"exit_code {actual} != expected {expected_int}")


def _check_grep(result: dict, expected: str) -> tuple:
    """Substring check: expected must be present in stdout."""
    stdout = result.get("stdout") or ""
    if expected is None:
        return (False, "rule expected field is NULL")

    if expected in stdout:
        return (True, f"pattern '{expected}' found in stdout")
    return (False, f"pattern '{expected}' not found in stdout")


def _check_grep_not(result: dict, expected: str) -> tuple:
    """Substring check: expected must NOT be present in stdout."""
    stdout = result.get("stdout") or ""
    if expected is None:
        return (False, "rule expected field is NULL")

    if expected not in stdout:
        return (True, f"pattern '{expected}' correctly absent from stdout")
    return (False, f"pattern '{expected}' unexpectedly present in stdout")


def _check_deferred(rule_type: str) -> tuple:
    """Stub for file_exists and http_200 - both deferred to Session 5+."""
    return (True, f"{rule_type}: {DEFERRED_NOTE}")


def _compute_effective_on_fail(failed_rules: List[MatchedRule]) -> str:
    """Pick the strictest on_fail value across failed rules.

    Precedence (most strict first): abort > escalate > fix > retry.
    Defensive: if a rule has an unknown on_fail value, treat it as 'abort'
    (strictest) so we fail safe rather than ignore the failure.
    """
    def rank(mr: MatchedRule) -> int:
        return ON_FAIL_PRECEDENCE.get(mr.on_fail, ON_FAIL_PRECEDENCE["abort"])

    strictest = max(failed_rules, key=rank)
    return strictest.on_fail if strictest.on_fail in ON_FAIL_PRECEDENCE else "abort"
