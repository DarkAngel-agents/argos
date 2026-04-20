"""
ARGOS Agent - Phase-aware prompt builder.

Session 2 MVP scope: only 'executing' phase (SQUAD role) is implemented.
Sessions 3+ will add COMMANDER (planning), SCOUT (verifying), ENGINEER (fixing).

Public API:
    system_prompt, tools = await build_session_context(pool, session, phase)
    user_msg = build_iteration_message(session, last_command_result=..., ...)

Pattern A (conversation history): system_prompt is built ONCE per session at
iteration 0 (or on resume), cached by loop.py, and NEVER modified across
iterations. Per-iteration updates go into user messages only. This keeps
Claude prompt caching effective and reduces cost significantly.

Token budget: ~30K input tokens total. Adaptive truncation drops dynamic
skills section if system prompt exceeds budget. Fixed skills (#88, #91,
#92 core) are never truncated in MVP.
"""
import re
from typing import Optional

import asyncpg


# ============================================================================
# SECTION 1: Constants and helpers
# ============================================================================

# Token budget for input side (system + tools + user message).
# Leaves ~8K for Claude response (max_tokens in providers.call_claude).
# Using char approximation: ~4 chars per token (rough average for English+code).
INPUT_BUDGET_TOKENS = 30000
CHARS_PER_TOKEN = 4
INPUT_BUDGET_CHARS = INPUT_BUDGET_TOKENS * CHARS_PER_TOKEN  # 120_000 chars

# Skill #92 core section size - first N chars contain scope, phase machine
# diagram, military role mapping, and basic anti-patterns. Rest is detailed
# reference that agent can load on demand via execute_command if needed.
# Permanent defensive pattern: skill #92 may be rewritten or modified at
# any point in the future. We never crash on size mismatch - we log and
# use what's available.
SKILL_92_CORE_CHARS = 3000

# Max dynamic skills selected per phase (minimalist context philosophy).
# Session 2 MVP: 3 skills in initial context is enough. LLM loads more on
# demand via NEEDS_MORE_CONTEXT signal or direct execute_command queries.
MAX_DYNAMIC_SKILLS = 3

# Max chars per dynamic skill content (truncate head-only via _truncate_tail).
MAX_DYNAMIC_SKILL_CHARS = 600

# Max evidence commands included in user message per iteration.
# Not heavily used in Pattern A - LLM has full history via conversation.
EVIDENCE_COMMANDS_IN_MSG = 5

# Max chars per evidence command stdout in user message.
EVIDENCE_STDOUT_MAX_CHARS = 500

# Max evidence errors included in user message per iteration.
EVIDENCE_ERRORS_IN_MSG = 2

# Simple English stopwords list for keyword extraction from goal/task.
# Keep small - this is MVP scoring, not NLP.
STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "of", "to", "in", "on", "for", "with", "and", "or", "but", "not",
    "at", "by", "from", "as", "it", "this", "that", "these", "those",
    "i", "me", "my", "we", "us", "our", "you", "your", "he", "she",
    "they", "them", "their", "do", "does", "did", "have", "has", "had",
    "can", "could", "should", "would", "will", "may", "might",
    "shall", "must", "need", "needs", "get", "gets", "got", "make", "made",
})


def _extract_keywords(text: str) -> set:
    """
    Extract lowercase keywords from text, excluding stopwords and short tokens.

    Used for matching session.goal and session.current_task against skill
    names, paths, and tags. MVP scoring - word overlap count only.

    Args:
        text: raw text (goal, current_task, or both concatenated)

    Returns:
        Set of lowercase keywords, stopwords removed, min length 3.
    """
    if not text:
        return set()
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in tokens if len(t) >= 3 and t not in STOPWORDS}


def _estimate_chars(text: str) -> int:
    """
    Rough char count for budget estimation. Simple len() wrapper for clarity
    and future swap to tiktoken if needed.
    """
    return len(text) if text else 0


def _truncate_middle(text: str, max_chars: int, marker: str = "\n... [truncated] ...\n") -> str:
    """
    Truncate by keeping head AND tail, inserting marker in the middle.

    Use for: error messages, multi-section content where both beginning
    (context/setup) and end (conclusion/failure point) carry information.
    """
    if text is None:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars < len(marker) + 20:
        return text[:max_chars]
    keep = (max_chars - len(marker)) // 2
    return text[:keep] + marker + text[-keep:]


def _truncate_tail(text: str, max_chars: int, marker: str = "\n... [truncated] ...") -> str:
    """
    Truncate by keeping HEAD only, cutting the tail.

    Use for: skill content (head has purpose + main commands), documentation
    where beginning is more important than end.
    """
    if not text or len(text) <= max_chars:
        return text or ""
    if max_chars < len(marker) + 20:
        return text[:max_chars]
    return text[:max_chars - len(marker)] + marker


def _truncate_head(text: str, max_chars: int, marker: str = "... [truncated] ...\n") -> str:
    """
    Truncate by keeping TAIL only, cutting the head.

    Use for: command stdout (tail has latest output relevant to verification),
    log streams where recent entries matter most.
    """
    if not text or len(text) <= max_chars:
        return text or ""
    if max_chars < len(marker) + 20:
        return text[-max_chars:]
    return marker + text[-(max_chars - len(marker)):]


# ============================================================================
# SECTION 2: Skill selection logic
# ============================================================================

# Fixed skill IDs always included in system prompt (regardless of phase).
# - #88: argos-api-redeploy (deploy protocol, emergency)
# - #91: argos-output-patterns (SQL/code patterns, emergency)
# - #92: argos-agent-loop-architecture (agent self-reference, FIRST N CHARS ONLY)
#
# Pattern A (conversation history) means system prompt is FIXED across all
# iterations in a session. Skill #92 is always injected at iteration 0 and
# stays in cached system prompt for the entire session lifetime. LLM does
# not re-read it - it remembers from first message.
FIXED_EMERGENCY_IDS = [88, 91]
SKILL_92_ID = 92

# Skill #90 is excluded from prompt (too large: 21K chars). Referenced by ID
# in system prompt footer so LLM knows it can query on demand.
SKILL_90_REFERENCE_ID = 90


def _score_skill(
    skill_row: dict,
    keywords: set,
) -> int:
    """
    Score a skill by keyword overlap against its name, path, and tags.

    Simple word-count scoring:
    - +2 for each keyword found in skill.path (strongest signal, path is curated)
    - +1 for each keyword found in skill.tags array
    - +1 for each keyword found in skill.name

    Ties are broken by caller (emergency/verified/id ASC).

    Args:
        skill_row: asyncpg Record with id, path, name, tags, emergency, verified
        keywords: set of lowercase keywords from goal/task

    Returns:
        Integer score, 0 if no match.
    """
    if not keywords:
        return 0

    score = 0
    path = (skill_row.get("path") or "").lower()
    name = (skill_row.get("name") or "").lower()
    tags = skill_row.get("tags") or []

    # Tokenize path and name the same way as keyword extraction for fair match.
    path_tokens = set(re.findall(r"[a-z0-9]+", path))
    name_tokens = set(re.findall(r"[a-z0-9]+", name))
    # Tags are already discrete strings - tokenize each for multi-word tags.
    tag_tokens = set()
    for tag in tags:
        tag_tokens.update(re.findall(r"[a-z0-9]+", str(tag).lower()))

    for kw in keywords:
        if kw in path_tokens:
            score += 2
        if kw in tag_tokens:
            score += 1
        if kw in name_tokens:
            score += 1

    return score


async def _load_fixed_skills(pool: asyncpg.Pool) -> dict:
    """
    Load fixed emergency skills (#88, #91) and skill #92 core section.

    Returns:
        dict with keys:
          - "fixed_emergency" (list of rows): #88 and #91 full content
          - "skill_92_core" (str): first SKILL_92_CORE_CHARS of #92, or full if shorter
          - "skill_92_available" (bool): True if #92 exists in DB
    """
    async with pool.acquire() as conn:
        # Load #88 and #91 in full.
        emergency_rows = await conn.fetch(
            """
            SELECT id, path, name, content, tags, emergency, verified
            FROM skills_tree
            WHERE id = ANY($1::int[])
            ORDER BY id
            """,
            FIXED_EMERGENCY_IDS,
        )

        # Load #92 separately (not phase-tagged, is agent self-reference).
        skill_92_row = await conn.fetchrow(
            "SELECT id, path, name, content FROM skills_tree WHERE id = $1",
            SKILL_92_ID,
        )

    skill_92_core = ""
    skill_92_available = False
    if skill_92_row and skill_92_row["content"]:
        content = skill_92_row["content"]
        skill_92_available = True
        if len(content) < SKILL_92_CORE_CHARS:
            # Permanent defensive pattern: skill #92 may be rewritten or
            # modified at any point in the future. Use what's available,
            # log a warning so ops notices the drift.
            print(
                f"[prompts] WARNING: skill #92 content is {len(content)} chars, "
                f"expected >= {SKILL_92_CORE_CHARS}. Using full content."
            )
            skill_92_core = content
        else:
            skill_92_core = content[:SKILL_92_CORE_CHARS]
    else:
        # Defensive: skill #92 missing from DB. Agent still functions with
        # hardcoded base prompt, but self-reference is gone. Warn loudly.
        print(
            "[prompts] WARNING: skill #92 (agent-loop-architecture) not found "
            "in skills_tree. Agent will run with hardcoded base prompt only."
        )

    return {
        "fixed_emergency": list(emergency_rows),
        "skill_92_core": skill_92_core,
        "skill_92_available": skill_92_available,
    }


async def _select_dynamic_skills(
    pool: asyncpg.Pool,
    phase: str,
    goal: str,
    current_task: Optional[str],
) -> list:
    """
    Select up to MAX_DYNAMIC_SKILLS skills for the given phase, ranked by
    keyword overlap with goal + current_task.

    Minimalist context philosophy (Session 2 design decision):
    fewer skills in initial context = better focus. LLM loads more on demand
    via NEEDS_MORE_CONTEXT signal or direct execute_command queries.

    Excludes fixed emergency skills (#88, #91) and skill #92 - they come from
    _load_fixed_skills. Also excludes skill #90 (too large, on-demand only).

    Fallback when scoring yields all zeros: emergency DESC, verified DESC, id ASC.

    Args:
        pool: asyncpg pool
        phase: phase name (e.g. "executing")
        goal: session.goal string
        current_task: session.current_task string (may be None)

    Returns:
        List of skill row dicts (top MAX_DYNAMIC_SKILLS by relevance).
    """
    phase_tag = f"phase:{phase}"
    excluded_ids = FIXED_EMERGENCY_IDS + [SKILL_90_REFERENCE_ID, SKILL_92_ID]

    async with pool.acquire() as conn:
        candidates = await conn.fetch(
            """
            SELECT id, path, name, content, tags, emergency, verified
            FROM skills_tree
            WHERE $1 = ANY(tags)
              AND id != ALL($2::int[])
            """,
            phase_tag,
            excluded_ids,
        )

    # Convert to plain dicts so _score_skill can use .get() safely.
    candidates_list = [dict(row) for row in candidates]

    # Build keyword set from goal + current_task.
    combined_text = " ".join(filter(None, [goal, current_task]))
    keywords = _extract_keywords(combined_text)

    # Score each candidate.
    scored = []
    for skill in candidates_list:
        score = _score_skill(skill, keywords)
        scored.append((score, skill))

    # Check if any skill scored > 0.
    any_match = any(score > 0 for score, _ in scored)

    if not any_match:
        # Fallback: deterministic default order.
        if keywords:
            # Goal had keywords but none matched any skill - signal for review.
            print(
                f"[prompts] goal keywords matched zero skills for phase={phase}, "
                f"using default order. Keywords tried: {sorted(keywords)}"
            )
        scored.sort(
            key=lambda item: (
                not item[1].get("emergency", False),  # emergency first
                not item[1].get("verified", False),   # verified first
                item[1].get("id", 999999),            # then id ASC
            )
        )
    else:
        # Primary sort by score DESC, tiebreak by emergency/verified/id.
        scored.sort(
            key=lambda item: (
                -item[0],                                # score DESC
                not item[1].get("emergency", False),     # emergency first
                not item[1].get("verified", False),      # verified first
                item[1].get("id", 999999),               # id ASC
            )
        )

    # Return top MAX_DYNAMIC_SKILLS, stripping the score.
    return [skill for _, skill in scored[:MAX_DYNAMIC_SKILLS]]


# ============================================================================
# SECTION 3: Main system prompt builder (called once per session)
# ============================================================================

# Markers used in multiple places - extracted to constants to prevent drift.
FIXED_REFERENCE_MARKER = "\n## CRITICAL REFERENCE\n\n"
AGENT_ARCH_MARKER = "\n## AGENT ARCHITECTURE REFERENCE\n\n"
DYNAMIC_SKILLS_MARKER = "\n## RELEVANT SKILLS FOR CURRENT PHASE\n"


# Hardcoded base template for SQUAD role (phase: executing).
# Session 2 MVP: only SQUAD is implemented. Other roles (COMMANDER/SCOUT/
# ENGINEER) come in Session 3 when phase transitions go live.
_SQUAD_BASE_TEMPLATE = """You are the SQUAD role of the ARGOS-Commander agent loop, executing phase.

Your job: given a goal and current task, propose ONE shell command at a time via the execute_command tool. The command runs on a target machine and its output is captured for verification. You iterate until the goal is complete, failed, or cancelled.

OPERATING PRINCIPLES:

1. ONE command per iteration. Never batch multiple commands with shell operators (|, &&, ;) in a single call - split into separate iterations. The agent verification chain matches one command at a time.

2. Minimalist context is a feature. Your initial context is deliberately small. When you need information you don't have (file paths, specific state, user preferences, config contents, additional skills), DO NOT guess. Use one of these options:

   a) Query directly via execute_command: SELECT from skills_tree, cat a file, ls a directory, grep a log, docker ps, etc. This is the default - query what you need when you need it.

   b) Request more reference material via the NEEDS_MORE_CONTEXT signal (see SIGNALS below). The loop will load relevant skills or data and inject them without consuming an iteration.

   c) Ask the user for clarification via the CLARIFICATION_NEEDED signal. The loop pauses until the user responds.

   Better to ask or query than proceed on assumptions.

3. Determinism over cleverness. Prefer absolute paths. Prefer single-purpose commands with predictable output. Avoid interactive programs (vim, nano, top without -b). Avoid commands whose success depends on environment you cannot see.

4. Autonomy awareness. Commands matching the read-only whitelist (ls, cat, grep, ps, df, du, uptime, hostname, pwd, whoami, date, which, wc, head, tail, echo) run without gate checks. Commands requiring state change (nixos-rebuild, systemctl restart, docker service update, etc) will be blocked or require user confirmation based on session autonomy_level. Plan accordingly.

SIGNALS (special commands intercepted by the agent loop, NOT executed as shell):

- echo GOAL_COMPLETE: <short summary>
  Use when you believe the goal is achieved. Loop marks session complete.

- echo CLARIFICATION_NEEDED: <your specific question>
  Use when you need user input that cannot be derived from queries. Loop pauses and waits for user response.

- echo STUCK: <what you tried and why it failed>
  Use when you cannot make progress after 3+ consecutive failed attempts on the same sub-task. Loop escalates to user.

- echo NEEDS_MORE_CONTEXT: <what you need>
  Use when your initial context is insufficient and direct queries would be tedious (e.g., "all skills about docker swarm", "the current HAProxy config", "recent errors for service X"). Loop loads the material and injects it in the next turn WITHOUT incrementing the iteration counter. Prefer this over guessing.

All four signals are detected by prefix match on the command string. They are not executed as shell - the loop intercepts and handles them. Output from regular execute_command calls (exit_code, stdout, stderr) is captured normally.

AVAILABLE MACHINES: {machines_list}

For ARGOS infrastructure details (hostnames, paths, DB schema, deploy protocol), query: SELECT content FROM skills_tree WHERE id=90; (this skill is excluded from your initial context due to size but is available on demand)."""


_SCOUT_VERIFICATION_FRAGMENT = """[VERIFICATION PASSED]

The verification chain has run against agent_verification_rules and all matched rules passed. Details below.

You remain in SQUAD role. Use the verification evidence to confirm your previous command achieved the intended effect, then propose the next command to advance the goal. If verification confirms the goal is complete, emit GOAL_COMPLETE."""


_ENGINEER_FIX_FRAGMENT = """[ROLE SWITCH: ENGINEER]

For this turn, you are the ENGINEER role. Your job is to diagnose and fix.

The previous command FAILED verification. The failure details are included below: which rules matched, which failed, and why.

Your tasks as ENGINEER for this turn:
1. Read the failure carefully - look at the failed rule's pattern, what was expected vs what actually happened in stdout/stderr
2. Diagnose root cause from the available evidence (do not guess)
3. Propose ONE corrective command via the execute_command tool

Constraints:
- You have a limited number of consecutive fix attempts on the same failure (max 3). After that the session will be marked failed automatically.
- If you believe the failure cannot be fixed (e.g. missing prerequisite that cannot be installed, environment limitation, goal is impossible), emit STUCK with a clear explanation instead of a fix command.
- A fix command can be: (a) a retry with adjusted arguments, (b) a prerequisite setup command (install missing tool, create missing dir), or (c) a different approach to the same sub-task.
- Do not retry the exact same command that just failed - the verification will reject it again.
- Diagnostic-first principle: BEFORE proposing any state-changing fix, prefer diagnostic commands from the read-only whitelist (ls, cat, grep, ps, df, etc - see SQUAD operating principle 4) to gather evidence about why the previous command failed.
- Read filesystem state, file contents, process status, or logs to confirm the root cause structurally - do not guess.
- Only propose state-changing commands once diagnostic evidence confirms the structural cause AND the fix is actionable within session autonomy.
- If diagnostic reveals the fix requires an action that will be denied by autonomy and no whitelist alternative exists, emit STUCK with the diagnostic evidence collected, rather than guessing at commands that will be denied.
- If a proposed fix command is denied by autonomy, do NOT retry the same denied command - try a functionally equivalent safer alternative or emit STUCK if none exists."""


def _build_execute_command_tool(machines_list: list) -> dict:
    """
    Build the execute_command tool definition for Claude API.

    Session 2 scope: single tool. English descriptions written from scratch
    (chat.py version is in Romanian with diacritics and targeted at interactive
    chat, not agent loop).
    """
    machines_str = ", ".join(machines_list) if machines_list else "beasty"
    return {
        "name": "execute_command",
        "description": (
            "Execute a shell command on a target machine. Single command per call, "
            "no interactive programs. The command runs non-interactively and output "
            "is captured for verification.\n\n"
            f"Available machines: {machines_str}\n\n"
            "Guidelines:\n"
            "- Use absolute paths when possible\n"
            "- Avoid commands with shell operators (|, &&, ;) in a single invocation - split into multiple calls\n"
            "- Commands matching read-only whitelist (ls, cat, grep, etc) run without autonomy check\n"
            "- Commands requiring state change may be blocked or require confirmation based on session autonomy_level\n"
            "- Special signals (GOAL_COMPLETE, CLARIFICATION_NEEDED, STUCK, NEEDS_MORE_CONTEXT) are intercepted by the loop, see system prompt\n\n"
            "Return value includes: exit_code, stdout, stderr, duration_ms."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "machine": {
                    "type": "string",
                    "description": "Target machine name (e.g., 'beasty', 'hermes', 'zeus') or IP address.",
                },
                "command": {
                    "type": "string",
                    "description": "Shell command to execute. Single command, no interactive input.",
                },
            },
            "required": ["machine", "command"],
        },
    }


def _format_skill_section_full(skill_row: dict) -> str:
    """
    Format a fixed skill (emergency, not truncated) for system prompt.
    """
    path = skill_row.get("path", "unknown")
    skill_id = skill_row.get("id", "?")
    content = skill_row.get("content") or ""
    return f"### Skill #{skill_id}: {path}\n\n{content}\n"


def _format_skill_section_truncated(skill_row: dict, max_chars: int) -> str:
    """
    Format a dynamic skill (truncated via _truncate_tail - head keeps purpose
    and main commands).
    """
    path = skill_row.get("path", "unknown")
    skill_id = skill_row.get("id", "?")
    content = skill_row.get("content") or ""
    if len(content) > max_chars:
        content = _truncate_tail(content, max_chars)
    return f"### Skill #{skill_id}: {path}\n\n{content}\n"


async def build_session_context(
    pool: asyncpg.Pool,
    session: dict,
    phase: str = "executing",
) -> tuple:
    """
    Build the fixed system prompt + tool definitions for a session.

    CALLED ONCE PER SESSION at iteration 0 (or at resume after crash).
    Result is cached by loop.py for the entire session lifetime.

    Pattern A (conversation history): system_prompt MUST NOT change between
    iterations - Claude prompt caching requires stable system content. Per-
    iteration updates go into user messages via build_iteration_message.

    Args:
        pool: asyncpg pool
        session: dict with id, goal, current_task (optional)
        phase: phase name, used for initial dynamic skill selection only - system prompt is stable across phase transitions per Pattern A

    Returns:
        (system_prompt: str, tools: list[dict])

    """

    # Lazy import to avoid circular imports between agent/prompts and agent/tools.
    from agent.tools import list_known_machines
    machines_list = list_known_machines()

    # Step 1: Load fixed skills (#88, #91, #92 core).
    fixed = await _load_fixed_skills(pool)

    # Step 2: Load dynamic skills via keyword scoring on goal + current_task.
    goal = session.get("goal") or ""
    current_task = session.get("current_task")
    dynamic_skills = await _select_dynamic_skills(pool, phase, goal, current_task)

    # Step 3: Assemble system prompt sections.
    sections = []

    # 3a: Base template with machines placeholder filled in.
    machines_str = ", ".join(machines_list) if machines_list else "beasty (default)"
    sections.append(_SQUAD_BASE_TEMPLATE.format(machines_list=machines_str))

    # 3b: Agent self-reference (skill #92 core, first SKILL_92_CORE_CHARS chars).
    if fixed["skill_92_available"] and fixed["skill_92_core"]:
        sections.append(AGENT_ARCH_MARKER + fixed["skill_92_core"] + "\n")

    # 3c: Fixed emergency skills (#88, #91) in full.
    for skill in fixed["fixed_emergency"]:
        sections.append(FIXED_REFERENCE_MARKER + _format_skill_section_full(skill))

    # 3d: Dynamic skills (top MAX_DYNAMIC_SKILLS by relevance, head-truncated).
    if dynamic_skills:
        sections.append(DYNAMIC_SKILLS_MARKER)
        for skill in dynamic_skills:
            sections.append(
                _format_skill_section_truncated(skill, MAX_DYNAMIC_SKILL_CHARS)
            )

    system_prompt = "\n".join(sections)

    # Step 4: Adaptive truncation if over budget.
    system_prompt = _enforce_budget(system_prompt)

    # Step 5: Build tool definitions.
    tools = [_build_execute_command_tool(machines_list)]

    return system_prompt, tools


def _enforce_budget(system_prompt: str) -> str:
    """
    Adaptive truncation if system_prompt exceeds budget.

    Budget order (from cheapest to most destructive):
    1. If under system budget: return as-is
    2. Drop dynamic skills section entirely, replace with on-demand note
    3. If still over: log error and return anyway (fail open)

    Fixed skills (#88, #91, #92 core) are NEVER truncated in MVP -
    they are critical operational knowledge.
    """
    current = _estimate_chars(system_prompt)
    # Reserve ~40% of total budget for tools + user messages + response headroom.
    system_budget = int(INPUT_BUDGET_CHARS * 0.6)  # 72_000 chars ~ 18K tokens

    if current <= system_budget:
        return system_prompt

    # Over budget. Drop dynamic skills section entirely.
    if DYNAMIC_SKILLS_MARKER in system_prompt:
        head = system_prompt.split(DYNAMIC_SKILLS_MARKER, 1)[0]
        print(
            f"[prompts] WARNING: system prompt {current} chars exceeds budget "
            f"{system_budget}. Dropping dynamic skills section."
        )
        reduced = head + DYNAMIC_SKILLS_MARKER + (
            "(dynamic skills omitted due to budget; emit 'echo NEEDS_MORE_CONTEXT: "
            "<what you need>' to request specific material on demand)\n"
        )
        if _estimate_chars(reduced) <= system_budget:
            return reduced
        system_prompt = reduced
        current = _estimate_chars(system_prompt)

    # Still over budget even without dynamic skills. Fail open.
    print(
        f"[prompts] ERROR: system prompt {current} chars exceeds budget "
        f"{system_budget} even without dynamic skills. Fixed skills "
        f"(#88, #91, #92 core) alone are oversized. Returning anyway - "
        f"check if fixed skill content grew unexpectedly."
    )
    return system_prompt


# ============================================================================
# SECTION 4: Per-iteration user message builder (called every iteration)
# ============================================================================


def _format_verification_section(verification_result: dict) -> str:
    """
    Format a verification result dict into a readable text section for inclusion
    in user messages during verifying or fixing phases.

    verification_result dict shape (from loop.py converting agent.verification.VerificationResult):
        {
            "passed": bool,
            "matched_rules": [{"rule_id": int, "pattern": str, "rule_type": str,
                               "expected": str, "passed": bool, "note": str}, ...],
            "failed_rules": [...],   # subset of matched_rules where passed=False
            "effective_on_fail": str or None,
            "note": str,
        }
    """
    if not verification_result:
        return "Verification result: (none)"

    passed = verification_result.get("passed", False)
    matched = verification_result.get("matched_rules", []) or []
    failed = verification_result.get("failed_rules", []) or []
    effective = verification_result.get("effective_on_fail")
    note = verification_result.get("note", "")

    if passed:
        lines = [f"Verification result: PASSED ({len(matched)} rule(s) matched)"]
        if matched:
            lines.append("Matched rules:")
            for mr in matched:
                rid = mr.get("rule_id")
                pat = mr.get("pattern", "")
                rt = mr.get("rule_type", "")
                mnote = mr.get("note", "")
                if rid is None:
                    lines.append(f"  - (no rules matched, treated as pass): {mnote}")
                else:
                    lines.append(f"  - rule {rid} (pattern '{pat}', type {rt}): {mnote}")
        return "\n".join(lines)

    lines = [f"Verification result: FAILED ({len(failed)} of {len(matched)} rule(s) failed, effective on_fail={effective})"]
    if failed:
        lines.append("Failed rules:")
        for mr in failed:
            rid = mr.get("rule_id")
            pat = mr.get("pattern", "")
            rt = mr.get("rule_type", "")
            exp = mr.get("expected", "")
            mnote = mr.get("note", "")
            lines.append(f"  - rule {rid} (pattern '{pat}', type {rt}, expected '{exp}'): {mnote}")
    if note:
        lines.append(f"Summary: {note}")
    return "\n".join(lines)


def build_iteration_message(
    session: dict,
    last_command_result: Optional[dict] = None,
    clarification_answer: Optional[str] = None,
    injected_context: Optional[str] = None,
    phase: str = "executing",
    verification_result: Optional[dict] = None,
) -> str:
    """
    Build the user message for a single iteration.

    CALLED EVERY ITERATION. Short, delta-focused. Pattern A (conversation
    history) means LLM already has previous iterations in its context -
    we only add what's new.

    Six distinct message shapes based on state:

    1. Iteration 0 (fresh start): goal + current_task + initial prompt
    2. Clarification answer: user responded to a CLARIFICATION_NEEDED signal
    3. Injected context: loop is responding to a NEEDS_MORE_CONTEXT signal
    4. Normal iteration 1+: previous command result + continue prompt
    5. Verifying phase: previous result + verification PASS evidence + scout fragment
    6. Fixing phase: previous result + verification FAIL evidence + engineer fragment

    Args:
        session: dict with goal, current_task, iteration, max_iterations.
                 May also contain 'fix_attempt' (int) when phase=fixing.
        last_command_result: dict from exec_tool (cmd, exit_code, stdout,
                             stderr, duration_ms) or None for iteration 0
        clarification_answer: user response to prior CLARIFICATION_NEEDED,
                              or None
        injected_context: material loaded in response to NEEDS_MORE_CONTEXT,
                          or None
        phase: current session phase ('executing', 'verifying', 'fixing').
               Cases 5 and 6 are selected when phase is 'verifying' or 'fixing'
               AND verification_result is provided.
        verification_result: dict converted from agent.verification.VerificationResult
                             by loop.py. Required for cases 5 and 6.

    Returns:
        String ready to be used as user message content in messages list.

    Priority order: injected_context > clarification_answer >
    (verification_result + phase=fixing) > (verification_result + phase=verifying) >
    last_command_result > iteration_0. If multiple are set, higher priority wins
    (loop.py should only set the appropriate combination per turn; this is defensive).
    """
    iteration = session.get("iteration", 0)
    max_iterations = session.get("max_iterations", 50)
    goal = session.get("goal") or ""
    current_task = session.get("current_task") or "(not set)"

    # Case 3: Injected context (response to NEEDS_MORE_CONTEXT).
    # Does not advance iteration in loop.py - this is a context expansion turn.
    if injected_context is not None:
        return (
            "Context expansion (you requested more material via NEEDS_MORE_CONTEXT):\n\n"
            f"{injected_context}\n\n"
            f"Iteration {iteration} of {max_iterations}. Proceed with the next command."
        )

    # Case 2: User responded to a clarification request.
    if clarification_answer is not None:
        return (
            "User response to your clarification request:\n\n"
            f"{clarification_answer}\n\n"
            f"Iteration {iteration} of {max_iterations}. Proceed with the next command."
        )

    # Case 6: Fixing phase - previous command failed verification, ENGINEER role.
    if phase == "fixing" and verification_result is not None and last_command_result is not None:
        cmd = last_command_result.get("cmd", "(unknown)")
        machine = last_command_result.get("machine", "(unknown)")
        exit_code = last_command_result.get("exit_code", -1)
        duration_ms = last_command_result.get("duration_ms", 0)
        stdout = last_command_result.get("stdout", "") or ""
        stderr = last_command_result.get("stderr", "") or ""
        stdout_preview = _truncate_head(stdout, EVIDENCE_STDOUT_MAX_CHARS)
        stderr_preview = _truncate_head(stderr, 300) if stderr else ""
        fix_attempt = session.get("fix_attempt", 0)
        verif_section = _format_verification_section(verification_result)

        parts = [
            _ENGINEER_FIX_FRAGMENT,
            "",
            f"Previous command: {cmd}",
            f"Machine: {machine}",
            f"Result: exit_code={exit_code}, duration={duration_ms}ms",
        ]
        if stdout_preview:
            parts.append(f"stdout:\n{stdout_preview}")
        if stderr_preview:
            parts.append(f"stderr:\n{stderr_preview}")
        parts.append("")
        parts.append(verif_section)
        parts.append("")
        parts.append(f"Fix attempt {fix_attempt} of 3 max. Diagnose and propose a fix command, or emit STUCK.")
        return "\n".join(parts)

    # Case 5: Verifying phase - previous command verified successfully.
    if phase == "verifying" and verification_result is not None and last_command_result is not None:
        cmd = last_command_result.get("cmd", "(unknown)")
        machine = last_command_result.get("machine", "(unknown)")
        exit_code = last_command_result.get("exit_code", -1)
        duration_ms = last_command_result.get("duration_ms", 0)
        stdout = last_command_result.get("stdout", "") or ""
        stderr = last_command_result.get("stderr", "") or ""
        stdout_preview = _truncate_head(stdout, EVIDENCE_STDOUT_MAX_CHARS)
        stderr_preview = _truncate_head(stderr, 300) if stderr else ""
        verif_section = _format_verification_section(verification_result)

        parts = [
            _SCOUT_VERIFICATION_FRAGMENT,
            "",
            f"Previous command: {cmd}",
            f"Machine: {machine}",
            f"Result: exit_code={exit_code}, duration={duration_ms}ms",
        ]
        if stdout_preview:
            parts.append(f"stdout:\n{stdout_preview}")
        if stderr_preview:
            parts.append(f"stderr:\n{stderr_preview}")
        parts.append("")
        parts.append(verif_section)
        parts.append("")
        parts.append(f"Iteration {iteration} of {max_iterations}. Proceed.")
        return "\n".join(parts)

    # Case 1: Fresh start (iteration 0, no prior result).
    if last_command_result is None:
        return (
            f"Goal: {goal}\n"
            f"Current task: {current_task}\n"
            f"Iteration {iteration} of {max_iterations}. Propose the first command to execute."
        )

    # Case 4: Normal iteration 1+ with previous command result.
    cmd = last_command_result.get("cmd", "(unknown)")
    machine = last_command_result.get("machine", "(unknown)")
    exit_code = last_command_result.get("exit_code", -1)
    duration_ms = last_command_result.get("duration_ms", 0)
    stdout = last_command_result.get("stdout", "") or ""
    stderr = last_command_result.get("stderr", "") or ""

    # Truncate stdout/stderr - keep tail (most recent output is most relevant).
    stdout_preview = _truncate_head(stdout, EVIDENCE_STDOUT_MAX_CHARS)
    stderr_preview = _truncate_head(stderr, 300) if stderr else ""

    parts = [
        f"Previous command: {cmd}",
        f"Machine: {machine}",
        f"Result: exit_code={exit_code}, duration={duration_ms}ms",
    ]
    if stdout_preview:
        parts.append(f"stdout:\n{stdout_preview}")
    if stderr_preview:
        parts.append(f"stderr:\n{stderr_preview}")
    parts.append(f"\nIteration {iteration} of {max_iterations}. What's next?")

    return "\n".join(parts)
