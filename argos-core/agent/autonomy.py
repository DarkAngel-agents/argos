"""
ARGOS Agent - Session-scoped autonomy gate.

Pre-execution check: given a command, decides whether the agent session
is allowed to run it autonomously or must escalate to the user.

Decision logic (in order):

1. Fail-closed checks: session exists and is active. Otherwise DENY.

2. Read-only whitelist check (Python constant SAFE_READONLY_WHITELIST):
   fast-path for safe read-only commands so MVP sessions can start without
   populating dozens of DB rules. If command matches a whitelist entry,
   return ALLOW with reason "read-only whitelist".

3. Match command against autonomy_rules via SQL ILIKE. Rules are ordered by
   action priority (block > allow > require_job), then by pattern specificity
   (longer patterns first). The first matching rule decides:

   - action='block'                          -> DENY always (safety absolute,
                                                ignores session ceiling)
   - action='allow'                          -> ALLOW always
   - action='require_job' + ceiling >= 1     -> ALLOW (ceiling override)
   - action='require_job' + ceiling == 0     -> DENY with "requires user
                                                confirmation" reason
                                                (loop.py escalates to user)

4. No rule matched and no whitelist hit -> DENY by default.

This is a PRE-execution gate only. It is NOT a replacement for
agent_verification_rules (those are POST-execution checks).

Discrepancy note (Vikunja #215): autonomy_config.risk_level is text
(low/med/high) while autonomy_rules.level is int (0-1 today). This module
reads autonomy_rules only - autonomy_config is the old category-based
system and will be unified in a future task.
"""
from typing import Optional

import asyncpg


# Read-only command whitelist for MVP fast-path.
# Documented in skill #92 as part of MVP session 2 behavior.
# Session 3+ may move this to DB as a setting.
#
# STRICT RULE for additions: a command goes in this whitelist ONLY if NONE of
# its standard options/flags can write to disk, modify state, or execute
# subprocesses. If the tool has ANY write-mode flag in its man page, it does
# NOT belong here - add an explicit 'allow' rule in autonomy_rules instead.
#
# Rejected candidates and why:
# - find:  has -delete, -exec, -execdir, -fprint, -fprintf, -fls (file writes)
# - sort:  has -o FILE (writes to file)
# - uniq:  has -o FILE (writes to file)
SAFE_READONLY_WHITELIST = [
    "ls",
    "cat",
    "echo",
    "grep",
    "ps",
    "df",
    "du",
    "uptime",
    "hostname",
    "pwd",
    "whoami",
    "date",
    "which",
    "wc",
    "head",
    "tail",
]


def _is_whitelisted_command(command: str) -> bool:
    """
    Check if command starts with a whitelisted read-only program.

    Matches the first token (program name) against SAFE_READONLY_WHITELIST.
    Commands with shell operators (|, ;, &&, >, etc) are NOT whitelisted
    because they could pipe read-only output into a destructive command.
    """
    stripped = command.strip()
    if not stripped:
        return False

    # Reject shell compound commands - we only whitelist single simple invocations.
    # A pipe could chain "ls | xargs rm" which would bypass the intent.
    for shell_op in ("|", ";", "&&", "||", ">", "<", "`", "$("):
        if shell_op in stripped:
            return False

    # Extract program name (first token, strip any leading path).
    first_token = stripped.split()[0]
    program = first_token.rsplit("/", 1)[-1]  # strip /usr/bin/ prefix if any

    return program in SAFE_READONLY_WHITELIST


class AutonomyDecision:
    """Result of an autonomy check. Simple value object."""

    __slots__ = ("allowed", "reason", "rule_pattern", "rule_action", "session_ceiling")

    def __init__(
        self,
        allowed: bool,
        reason: str,
        rule_pattern: Optional[str] = None,
        rule_action: Optional[str] = None,
        session_ceiling: Optional[int] = None,
    ):
        self.allowed = allowed
        self.reason = reason
        self.rule_pattern = rule_pattern
        self.rule_action = rule_action
        self.session_ceiling = session_ceiling

    def to_dict(self) -> dict:
        """Serialize for evidence.append_decision."""
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "rule_pattern": self.rule_pattern,
            "rule_action": self.rule_action,
            "session_ceiling": self.session_ceiling,
        }

    def __repr__(self) -> str:
        status = "ALLOW" if self.allowed else "DENY"
        return f"<AutonomyDecision {status} reason={self.reason!r}>"


async def check_session_autonomy(
    pool: asyncpg.Pool,
    session_id: int,
    command: str,
) -> AutonomyDecision:
    """
    Pre-execution gate. Returns AutonomyDecision with allowed/denied + reason.

    Does NOT raise on denial - caller (loop.py) decides whether to escalate
    to user prompt, skip iteration, or mark session failed.

    Args:
        pool: asyncpg pool (not closed here, caller owns it).
        session_id: agent_sessions.id
        command: raw command string that LLM wants to execute.

    Returns:
        AutonomyDecision instance.
    """
    # Step 1: Load session and fail closed on missing/inactive.
    async with pool.acquire() as conn:
        session_row = await conn.fetchrow(
            "SELECT autonomy_level, active, phase FROM agent_sessions WHERE id = $1",
            session_id,
        )
    if session_row is None:
        return AutonomyDecision(
            allowed=False,
            reason=f"session {session_id} not found",
        )
    if not session_row["active"]:
        return AutonomyDecision(
            allowed=False,
            reason=f"session {session_id} is not active (phase={session_row['phase']})",
            session_ceiling=int(session_row["autonomy_level"]),
        )

    ceiling = int(session_row["autonomy_level"])

    # Step 2: Whitelist fast-path for read-only commands.
    # Checked BEFORE DB rules because it's cheap and deterministic.
    if _is_whitelisted_command(command):
        return AutonomyDecision(
            allowed=True,
            reason="read-only whitelist",
            session_ceiling=ceiling,
        )

    # Step 3: Match command against autonomy_rules via SQL ILIKE.
    #
    # Ordering strategy:
    # - action_priority CASE: block(1) < allow(2) < require_job(3)
    #   Lower number wins - block rules are evaluated first so a matching
    #   block rule always takes precedence over allow/require_job matches.
    # - length(pattern) DESC: longer patterns are more specific, win over
    #   generic catch-alls at the same action priority.
    # - pattern ASC: stable tiebreaker for deterministic behavior.
    #
    # LIMIT 1 because we only care about the winning rule.
    match_sql = """
        SELECT pattern, action
        FROM autonomy_rules
        WHERE $1 ILIKE pattern
        ORDER BY
            CASE action
                WHEN 'block' THEN 1
                WHEN 'allow' THEN 2
                WHEN 'require_job' THEN 3
                ELSE 4
            END,
            length(pattern) DESC,
            pattern ASC
        LIMIT 1
    """
    async with pool.acquire() as conn:
        matched = await conn.fetchrow(match_sql, command)

    if matched is None:
        # Step 4: No rule matched and no whitelist hit -> default DENY.
        return AutonomyDecision(
            allowed=False,
            reason="no autonomy rule matched (default deny)",
            session_ceiling=ceiling,
        )

    pattern = matched["pattern"]
    action = matched["action"]

    # Branch on action with explicit comments per case.
    if action == "block":
        # Absolute safety: block rules ignore session ceiling entirely.
        # Example: 'rm -rf%' is blocked even for autonomy_level=99.
        return AutonomyDecision(
            allowed=False,
            reason=f"blocked by rule: {pattern}",
            rule_pattern=pattern,
            rule_action=action,
            session_ceiling=ceiling,
        )

    if action == "allow":
        # Explicit allow: ignores ceiling, always ALLOW.
        # Example: 'systemctl status%' is always safe.
        return AutonomyDecision(
            allowed=True,
            reason=f"allowed by rule: {pattern}",
            rule_pattern=pattern,
            rule_action=action,
            session_ceiling=ceiling,
        )

    if action == "require_job":
        # Ceiling override: session with autonomy_level >= 1 bypasses
        # user confirmation for require_job commands. This is the explicit
        # purpose of the session ceiling - user opted in at session start.
        # Example: 'nixos-rebuild%' runs unattended if --autonomy 1 was set.
        if ceiling >= 1:
            return AutonomyDecision(
                allowed=True,
                reason=f"require_job overridden by ceiling {ceiling}: {pattern}",
                rule_pattern=pattern,
                rule_action=action,
                session_ceiling=ceiling,
            )
        # Default safe: ceiling=0 means escalate to user for require_job.
        return AutonomyDecision(
            allowed=False,
            reason=f"requires user confirmation (rule: {pattern}, ceiling={ceiling})",
            rule_pattern=pattern,
            rule_action=action,
            session_ceiling=ceiling,
        )

    # Unknown action value - fail closed. Defensive against future schema
    # extensions where someone adds a new action without updating this branch.
    return AutonomyDecision(
        allowed=False,
        reason=f"unknown action {action!r} in rule: {pattern}",
        rule_pattern=pattern,
        rule_action=action,
        session_ceiling=ceiling,
    )
