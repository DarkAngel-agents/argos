"""
ARGOS Agent - Main orchestrator loop.

Session 2 MVP scope: single phase 'executing' (SQUAD role). No phase
transitions, no verification chain - those come in Session 3.

Public API:
    final_status = await run_agent_loop(session_id)

Pattern A (conversation history): system_prompt built once per session,
messages[] accumulated across iterations, Claude sees full history via
conversation turns. Cost-efficient with prompt caching.

Resume semantics:
- On startup, if session.iteration > 0, rebuild messages[] from evidence
  (llm_calls + commands in chronological order) and continue.
- If session was paused for clarification (evidence.decisions has
  PAUSE_CLARIFICATION marker), abort unless clarification_answer provided.

Terminal states:
- complete: GOAL_COMPLETE signal received
- failed: max_iterations reached, STUCK signal, fatal error, or
          no_tool_use count >= 3
- cancelled: external stop via argos-agent stop (sets active=FALSE)

This module owns the asyncpg pool lifecycle via try/finally. Every path
through the loop closes the pool on exit to prevent connection leaks.
"""
import asyncio
import json
import os
import re
import sys
import traceback
from typing import Optional

import asyncpg
from dotenv import load_dotenv

# Ensure repo root is on path for api.executor lazy import via tools.py.
_ARGOS_CORE = os.path.expanduser("~/.argos/argos-core")
if _ARGOS_CORE not in sys.path:
    sys.path.insert(0, _ARGOS_CORE)

from agent import evidence, autonomy, tools, prompts, verification  # noqa: E402
from llm import providers  # noqa: E402
from llm.providers import LLMError  # noqa: E402


# Load DB credentials from the agent-side env file (not the container one).
load_dotenv(os.path.expanduser("~/.argos/argos-core/config/.env"))


# ============================================================================
# Signal detection constants
# ============================================================================

SIGNAL_GOAL_COMPLETE = "GOAL_COMPLETE"
SIGNAL_CLARIFICATION_NEEDED = "CLARIFICATION_NEEDED"
SIGNAL_STUCK = "STUCK"
SIGNAL_NEEDS_MORE_CONTEXT = "NEEDS_MORE_CONTEXT"

# Pattern: echo SIGNAL: payload (with optional whitespace tolerance).
_SIGNAL_RE = re.compile(
    r"^\s*echo\s+(GOAL_COMPLETE|CLARIFICATION_NEEDED|STUCK|NEEDS_MORE_CONTEXT)\s*:\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)

# Regex to extract explicit skill IDs from NEEDS_MORE_CONTEXT payload.
_SKILL_ID_RE = re.compile(r"skill[s]?\s*#?\s*(\d+)", re.IGNORECASE)

# Session 4 (Faza E): max consecutive fix attempts before session terminates failed.
# Counter is reset on every successful verification (D6 - session-scoped, in-memory).
MAX_FIX_ATTEMPTS = 3

# Max LLM calls with no tool_use in a row before failing the session.
MAX_NO_TOOL_USE_COUNT = 3

# Max skills loaded per NEEDS_MORE_CONTEXT request.
MAX_CONTEXT_EXPANSION_SKILLS = 5

# Max chars per skill when expanding context.
CONTEXT_EXPANSION_SKILL_CHARS = 1000

# Marker prefix used in evidence.decisions.reason to tag pause-for-clarification.
PAUSE_CLARIFICATION_PREFIX = "PAUSE_CLARIFICATION:"


# ============================================================================
# DB helpers
# ============================================================================


async def _build_pool() -> asyncpg.Pool:
    """
    Build asyncpg pool from env vars. Caller owns lifecycle.
    """
    return await asyncpg.create_pool(
        host=os.getenv("DB_HOST", "11.11.11.111"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.getenv("DB_USER", "claude"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "claudedb"),
        min_size=1,
        max_size=4,
    )


async def _load_session(pool: asyncpg.Pool, session_id: int) -> Optional[dict]:
    """
    Load session row. Returns dict or None if not found.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, title, goal, phase, iteration, max_iterations, active,
                   current_task, evidence, autonomy_level, llm_provider,
                   total_tokens, total_cost_eur
            FROM agent_sessions
            WHERE id = $1
            """,
            session_id,
        )
    if row is None:
        return None
    result = dict(row)
    # asyncpg returns JSONB as string - parse it for consistency.
    if isinstance(result.get("evidence"), str):
        result["evidence"] = json.loads(result["evidence"])
    return result


async def _set_session_phase(pool: asyncpg.Pool, session_id: int, phase: str) -> None:
    """
    Update session phase. Does not change active flag.
    """
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE agent_sessions SET phase = $2, last_active_at = NOW() WHERE id = $1",
            session_id,
            phase,
        )


async def _increment_iteration(pool: asyncpg.Pool, session_id: int) -> int:
    """
    Increment iteration counter atomically. Returns new value.
    """
    async with pool.acquire() as conn:
        new_val = await conn.fetchval(
            """
            UPDATE agent_sessions
            SET iteration = iteration + 1,
                last_active_at = NOW()
            WHERE id = $1
            RETURNING iteration
            """,
            session_id,
        )
    return int(new_val)


async def _mark_terminal(
    pool: asyncpg.Pool,
    session_id: int,
    phase: str,
    reason: str,
) -> None:
    """
    Set terminal phase (complete/failed/cancelled), mark inactive,
    set completed_at. Appends final decision for audit.
    """
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE agent_sessions
            SET phase = $2,
                active = FALSE,
                completed_at = NOW(),
                last_active_at = NOW()
            WHERE id = $1
            """,
            session_id,
            phase,
        )
    await evidence.append_decision(
        pool=pool,
        session_id=session_id,
        phase=phase,
        action=f"terminal_{phase}",
        reason=reason,
        iteration=-1,
    )
    print(f"[loop] session {session_id} marked {phase}: {reason}")


async def _pause_for_clarification(
    pool: asyncpg.Pool,
    session_id: int,
    question: str,
    iteration: int,
) -> None:
    """
    Pause a session awaiting user clarification.

    Sets active=FALSE (loop cannot resume on its own) and appends a
    decision with PAUSE_CLARIFICATION marker in reason so resume logic
    can detect and require --answer.
    """
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE agent_sessions SET active = FALSE, last_active_at = NOW() WHERE id = $1",
            session_id,
        )
    await evidence.append_decision(
        pool=pool,
        session_id=session_id,
        phase="executing",
        action="pause",
        reason=f"{PAUSE_CLARIFICATION_PREFIX} {question}",
        iteration=iteration,
    )
    print(f"[loop] session {session_id} paused for clarification: {question[:80]}")


async def _check_pending_clarification(
    pool: asyncpg.Pool,
    session_id: int,
) -> Optional[str]:
    """
    Check if session has a pending clarification (latest pause decision
    with PAUSE_CLARIFICATION marker, no resume decision after it).

    Returns the pending question string, or None if no pending clarification.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT evidence FROM agent_sessions WHERE id = $1",
            session_id,
        )
    if row is None:
        return None
    ev = row["evidence"]
    if isinstance(ev, str):
        ev = json.loads(ev)
    decisions = ev.get("decisions", []) if ev else []

    # Walk decisions backward looking for the latest pause marker.
    # If a "resume" action exists after it, the pause is already handled.
    latest_pause_idx = None
    for i in range(len(decisions) - 1, -1, -1):
        reason = str(decisions[i].get("reason") or "")
        action = str(decisions[i].get("action") or "")
        if action == "resume_clarification":
            return None  # already resumed
        if reason.startswith(PAUSE_CLARIFICATION_PREFIX):
            latest_pause_idx = i
            break

    if latest_pause_idx is None:
        return None

    reason = str(decisions[latest_pause_idx].get("reason") or "")
    question = reason[len(PAUSE_CLARIFICATION_PREFIX):].strip()
    return question


# ============================================================================
# Resume: rebuild messages from evidence
# ============================================================================


async def _rebuild_messages_from_evidence(
    pool: asyncpg.Pool,
    session: dict,
) -> list:
    """
    Reconstruct Claude conversation messages[] from evidence after crash.

    Uses evidence.commands timestamps as the chronological anchor. Each
    command becomes a pair of (assistant tool_use, user tool_result)
    approximating what the original conversation looked like.

    This is a BEST-EFFORT reconstruction - the original exact tool_use_ids
    and text content from Claude are lost. We rebuild a conversation that
    Claude can continue from, not a bit-exact replay.

    Returns:
        list of message dicts suitable for providers.call_claude messages arg.
    """
    session_id = session["id"]
    ev = session.get("evidence") or {}
    commands = ev.get("commands", [])

    messages = []

    # First, the initial user message (iteration 0 framing).
    initial = prompts.build_iteration_message(session, last_command_result=None)
    messages.append({"role": "user", "content": initial})

    # For each historical command, synthesize assistant + user turns.
    # We use synthetic tool_use_ids since originals are lost. Claude
    # tolerates this when the conversation is coherent.
    for idx, cmd_entry in enumerate(commands):
        synth_id = f"resume_{session_id}_{idx}"
        cmd_str = cmd_entry.get("cmd", "")
        machine = cmd_entry.get("machine", "beasty")

        # Synthetic assistant turn with tool_use.
        messages.append({
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": synth_id,
                    "name": "execute_command",
                    "input": {"machine": machine, "command": cmd_str},
                }
            ],
        })

        # Synthetic user turn with tool_result.
        result_text = (
            f"exit_code={cmd_entry.get('exit_code', -1)}, "
            f"duration={cmd_entry.get('duration_ms', 0)}ms\n"
            f"stdout: {(cmd_entry.get('stdout') or '')[:500]}\n"
            f"stderr: {(cmd_entry.get('stderr') or '')[:300]}"
        )
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": synth_id,
                    "content": result_text,
                }
            ],
        })

    print(f"[loop] rebuilt {len(messages)} messages from evidence for resume")
    return messages


# ============================================================================
# Tool use parsing and signal detection
# ============================================================================


def _extract_tool_use(content_blocks: list) -> Optional[dict]:
    """
    Find the first execute_command tool_use block in Claude's response.

    Returns:
        dict with {id, name, input} or None if no execute_command found.
    """
    if not content_blocks:
        return None
    for block in content_blocks:
        block_type = getattr(block, "type", None) or (
            block.get("type") if isinstance(block, dict) else None
        )
        if block_type != "tool_use":
            continue
        name = getattr(block, "name", None) or (
            block.get("name") if isinstance(block, dict) else None
        )
        if name != "execute_command":
            continue
        tool_id = getattr(block, "id", None) or (
            block.get("id") if isinstance(block, dict) else None
        )
        inputs = getattr(block, "input", None) or (
            block.get("input") if isinstance(block, dict) else {}
        )
        return {"id": tool_id, "name": name, "input": dict(inputs or {})}
    return None


def _detect_signal(command: str) -> tuple:
    """
    Detect if a command is a loop signal (GOAL_COMPLETE, CLARIFICATION_NEEDED,
    STUCK, NEEDS_MORE_CONTEXT).

    Returns:
        (signal_name: str, payload: str) or (None, None) if not a signal.
    """
    if not command:
        return (None, None)
    match = _SIGNAL_RE.match(command)
    if not match:
        return (None, None)
    return (match.group(1).upper(), match.group(2).strip())


def _content_blocks_to_serializable(content_blocks) -> list:
    """
    Convert Claude SDK content blocks to plain dict list for messages history.

    Claude API accepts both raw SDK objects and plain dicts in messages, but
    plain dicts are safer for resume-from-evidence and JSON serialization.
    """
    if not content_blocks:
        return []
    result = []
    for block in content_blocks:
        btype = getattr(block, "type", None)
        if btype == "text":
            result.append({"type": "text", "text": getattr(block, "text", "")})
        elif btype == "tool_use":
            result.append({
                "type": "tool_use",
                "id": getattr(block, "id", ""),
                "name": getattr(block, "name", ""),
                "input": dict(getattr(block, "input", {}) or {}),
            })
        elif isinstance(block, dict):
            result.append(block)
        else:
            # Unknown block type - stringify defensively.
            result.append({"type": "text", "text": str(block)})
    return result


# ============================================================================
# NEEDS_MORE_CONTEXT handler
# ============================================================================


async def _load_context_for_request(pool: asyncpg.Pool, payload: str) -> str:
    """
    Load skills matching a NEEDS_MORE_CONTEXT request.

    Strategy:
    1. If payload mentions explicit skill IDs (e.g. "skill #42"), load those.
    2. Otherwise, extract keywords and SELECT skills matching tags or path.
    3. Limit to MAX_CONTEXT_EXPANSION_SKILLS, truncate each to
       CONTEXT_EXPANSION_SKILL_CHARS via _truncate_tail.
    4. If no matches, return a message telling LLM to rephrase or query directly.
    """
    explicit_ids = [int(m) for m in _SKILL_ID_RE.findall(payload)]

    async with pool.acquire() as conn:
        if explicit_ids:
            rows = await conn.fetch(
                """
                SELECT id, path, content
                FROM skills_tree
                WHERE id = ANY($1::bigint[])
                ORDER BY id
                LIMIT $2
                """,
                explicit_ids[:MAX_CONTEXT_EXPANSION_SKILLS],
                MAX_CONTEXT_EXPANSION_SKILLS,
            )
        else:
            keywords = prompts._extract_keywords(payload)
            if not keywords:
                return (
                    "No keywords extracted from your request. "
                    "Try rephrasing with specific terms, or query directly: "
                    "SELECT id, path FROM skills_tree WHERE path ILIKE '%keyword%'."
                )
            kw_list = list(keywords)
            # Build ILIKE patterns for path matching.
            path_patterns = [f"%{kw}%" for kw in kw_list]
            rows = await conn.fetch(
                """
                SELECT id, path, content
                FROM skills_tree
                WHERE EXISTS (
                    SELECT 1 FROM unnest(tags) t
                    WHERE lower(t) = ANY($1::text[])
                )
                OR path ILIKE ANY($2::text[])
                ORDER BY emergency DESC, verified DESC, id ASC
                LIMIT $3
                """,
                kw_list,
                path_patterns,
                MAX_CONTEXT_EXPANSION_SKILLS,
            )

    if not rows:
        return (
            "No skills matched your request. "
            "Try rephrasing or query directly via execute_command with SELECT "
            "from skills_tree."
        )

    parts = []
    for row in rows:
        content = row["content"] or ""
        if len(content) > CONTEXT_EXPANSION_SKILL_CHARS:
            content = prompts._truncate_tail(content, CONTEXT_EXPANSION_SKILL_CHARS)
        parts.append(f"### Skill #{row['id']}: {row['path']}\n\n{content}\n")
    return "\n---\n\n".join(parts)


# ============================================================================
# Main orchestrator
# ============================================================================


async def run_agent_loop(
    session_id: int,
    clarification_answer: Optional[str] = None,
) -> dict:
    """
    Main entry point. Runs the agent loop for a given session until it
    reaches a terminal state or max_iterations.

    Args:
        session_id: agent_sessions.id
        clarification_answer: if provided, injects as response to a prior
                              CLARIFICATION_NEEDED pause and resumes.

    Returns:
        dict with final status: {session_id, phase, iteration, reason}.
    """
    pool = None
    try:
        pool = await _build_pool()

        # Load session.
        session = await _load_session(pool, session_id)
        if session is None:
            return {"session_id": session_id, "phase": "error", "reason": "session not found"}

        # Check pending clarification state.
        pending_question = await _check_pending_clarification(pool, session_id)
        if pending_question is not None:
            if clarification_answer is None:
                msg = (
                    f"Session {session_id} is paused awaiting clarification. "
                    f"Question: {pending_question}. "
                    f"Use: argos-agent resume {session_id} --answer '<your response>'"
                )
                print(f"[loop] {msg}")
                return {
                    "session_id": session_id,
                    "phase": "paused",
                    "reason": msg,
                    "pending_question": pending_question,
                }
            # User provided an answer - mark resume and reactivate session.
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE agent_sessions SET active = TRUE, last_active_at = NOW() WHERE id = $1",
                    session_id,
                )
            await evidence.append_decision(
                pool=pool,
                session_id=session_id,
                phase="executing",
                action="resume_clarification",
                reason=f"user answered: {clarification_answer[:200]}",
                iteration=session.get("iteration", 0),
            )
            # Reload session after state change.
            session = await _load_session(pool, session_id)

        # Validate session is runnable.
        if not session.get("active"):
            return {
                "session_id": session_id,
                "phase": session.get("phase"),
                "reason": "session is not active",
            }
        if session.get("phase") in ("complete", "failed", "cancelled"):
            return {
                "session_id": session_id,
                "phase": session["phase"],
                "reason": "session already in terminal state",
            }

        # Transition to executing phase if not already there.
        if session.get("phase") in ("starting", "planning"):
            await _set_session_phase(pool, session_id, "executing")
            session["phase"] = "executing"

        # Build fixed session context (system prompt + tools) ONCE.
        try:
            system_prompt, tool_defs = await prompts.build_session_context(
                pool, session, phase="executing"
            )
        except Exception as e:
            await evidence.append_error(
                pool=pool,
                session_id=session_id,
                code="E_PROMPT_BUILD_FAIL",
                msg=f"{type(e).__name__}: {e}",
                phase="executing",
                iteration=session.get("iteration", 0),
            )
            await _mark_terminal(pool, session_id, "failed", f"prompt build failed: {e}")
            return {"session_id": session_id, "phase": "failed", "reason": str(e)}

        # Resume: rebuild messages[] from evidence if iteration > 0.
        if session.get("iteration", 0) > 0:
            messages = await _rebuild_messages_from_evidence(pool, session)
        else:
            messages = []
            initial_msg = prompts.build_iteration_message(session, last_command_result=None)
            messages.append({"role": "user", "content": initial_msg})

        # If we're resuming with a clarification answer, inject it as the
        # next user turn. Otherwise, the rebuilt messages or the initial
        # user turn are enough to continue.
        if clarification_answer is not None:
            clarify_msg = prompts.build_iteration_message(
                session, clarification_answer=clarification_answer
            )
            messages.append({"role": "user", "content": clarify_msg})

        # Main loop state.
        max_iterations = int(session.get("max_iterations") or 50)
        no_tool_count = 0
        last_command_result = None
        pending_injection: Optional[str] = None

        # Session 4 (Faza E) state.
        # NOTE on resume from crash: fix_attempt resets to 0 here. This is
        # intentional per D6 - the counter is in-memory only, never persisted.
        # Crash recovery is a rare path and granting a fresh fix budget on
        # resume is acceptable (it is more lenient, not less safe).
        fix_attempt = 0
        current_phase = "executing"
        last_verification_result: Optional[dict] = None

        def _verif_to_dict(v):
            """Convert agent.verification.VerificationResult into a plain dict
            for prompts.py (which must remain decoupled from verification.py)."""
            return {
                "passed": v.passed,
                "matched_rules": [
                    {
                        "rule_id": mr.rule_id,
                        "pattern": mr.pattern,
                        "rule_type": mr.rule_type,
                        "expected": mr.expected,
                        "passed": mr.passed,
                        "note": mr.note,
                    }
                    for mr in v.matched_rules
                ],
                "failed_rules": [
                    {
                        "rule_id": mr.rule_id,
                        "pattern": mr.pattern,
                        "rule_type": mr.rule_type,
                        "expected": mr.expected,
                        "passed": mr.passed,
                        "note": mr.note,
                    }
                    for mr in v.failed_rules
                ],
                "effective_on_fail": v.effective_on_fail,
                "note": v.note,
            }

        while True:
            # Reload current iteration from DB (could have been updated
            # externally or by increment calls).
            current = await _load_session(pool, session_id)
            if current is None:
                await _mark_terminal(pool, session_id, "failed", "session disappeared mid-loop")
                return {"session_id": session_id, "phase": "failed", "reason": "session vanished"}
            if not current.get("active"):
                print(f"[loop] session {session_id} deactivated externally, stopping")
                return {
                    "session_id": session_id,
                    "phase": current.get("phase"),
                    "reason": "session deactivated externally",
                }

            iteration = int(current.get("iteration") or 0)
            if iteration >= max_iterations:
                await _mark_terminal(
                    pool,
                    session_id,
                    "failed",
                    f"max_iterations reached ({max_iterations})",
                )
                return {
                    "session_id": session_id,
                    "phase": "failed",
                    "iteration": iteration,
                    "reason": "max_iterations",
                }

            # Build and append next user message (unless this is a fresh
            # iteration 0 where the initial msg is already in messages[],
            # or a resume where rebuilt history is enough).
            if pending_injection is not None:
                inj_msg = prompts.build_iteration_message(
                    current, injected_context=pending_injection
                )
                messages.append({"role": "user", "content": inj_msg})
                pending_injection = None
            elif last_command_result is not None:
                # Z6 (Session 4): pass phase + verification_result so prompts.py
                # picks Case 5 (verifying) or Case 6 (fixing) when applicable.
                msg_session = dict(current)
                msg_session["fix_attempt"] = fix_attempt
                next_msg = prompts.build_iteration_message(
                    msg_session,
                    last_command_result=last_command_result,
                    phase=current_phase,
                    verification_result=last_verification_result,
                )
                messages.append({"role": "user", "content": next_msg})
                last_command_result = None
                last_verification_result = None
            # else: messages[] already has the right last user turn
            # (fresh iteration 0 initial msg, or resume rebuild).

            # Call Claude.
            try:
                response = await providers.call_claude(
                    messages=messages,
                    tools=tool_defs,
                    system=system_prompt,
                )
            except LLMError as e:
                await evidence.append_error(
                    pool=pool,
                    session_id=session_id,
                    code="E_LLM_CALL_FAIL",
                    msg=str(e),
                    phase="executing",
                    iteration=iteration,
                )
                await _mark_terminal(pool, session_id, "failed", f"LLM call failed: {e}")
                return {"session_id": session_id, "phase": "failed", "reason": str(e)}

            # Log LLM call to evidence.
            provider_name = "claude"
            tokens_in = response["usage"]["input_tokens"]
            tokens_out = response["usage"]["output_tokens"]
            model_used = response.get("model", "unknown")
            await evidence.append_llm_call(
                pool=pool,
                session_id=session_id,
                provider=provider_name,
                model=model_used,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                phase="executing",
                cost_eur=None,  # pricing module not yet available in Session 2
            )
            await evidence.update_session_totals(
                pool=pool,
                session_id=session_id,
                tokens_delta=(tokens_in + tokens_out),
                cost_delta_eur=0.0,
            )

            # Append assistant turn to messages[] as serializable dict.
            assistant_content = _content_blocks_to_serializable(response["content_blocks"])
            messages.append({"role": "assistant", "content": assistant_content})

            # Parse tool use.
            tool_use = _extract_tool_use(response["content_blocks"])
            if tool_use is None:
                no_tool_count += 1
                await evidence.append_error(
                    pool=pool,
                    session_id=session_id,
                    code="E_NO_TOOL_USE",
                    msg=f"LLM response lacked execute_command tool_use (count {no_tool_count})",
                    phase="executing",
                    iteration=iteration,
                )
                if no_tool_count >= MAX_NO_TOOL_USE_COUNT:
                    await _mark_terminal(
                        pool,
                        session_id,
                        "failed",
                        f"LLM failed to emit tool_use {no_tool_count} times in a row",
                    )
                    return {
                        "session_id": session_id,
                        "phase": "failed",
                        "reason": "no_tool_use_limit",
                    }
                # Nudge LLM to use the tool. No iteration increment.
                nudge = (
                    "Your previous response did not contain a tool_use block. "
                    "You must use the execute_command tool or emit a signal "
                    "(echo GOAL_COMPLETE: ..., echo STUCK: ..., etc). Please proceed."
                )
                messages.append({"role": "user", "content": nudge})
                continue

            # Reset no_tool_count on any valid tool_use.
            no_tool_count = 0

            tool_input = tool_use["input"] or {}
            command = str(tool_input.get("command") or "")
            machine = str(tool_input.get("machine") or "beasty")
            tool_use_id = tool_use["id"] or ""

            # Z4 (Session 4): Pre-execution safety guard check (D2).
            # Skip safety for signals (they are intercepted, not executed).
            if _detect_signal(command)[0] is None:
                try:
                    safety = await verification.check_safety_guards(pool, command)
                except asyncpg.PostgresError as e:
                    await evidence.append_error(
                        pool=pool,
                        session_id=session_id,
                        code="E_SAFETY_DB",
                        msg=f"safety guard DB query failed: {type(e).__name__}: {e}",
                        phase=current_phase,
                        iteration=iteration,
                    )
                    await _mark_terminal(pool, session_id, "failed", f"safety guard DB error: {e}")
                    return {"session_id": session_id, "phase": "failed", "reason": "safety_db_error"}

                if safety.blocked:
                    # D5: write to errors + decisions, NOT to commands (command never ran).
                    await evidence.append_error(
                        pool=pool,
                        session_id=session_id,
                        code="E_SAFETY_BLOCK",
                        msg=safety.reason or f"safety rule {safety.rule_id} matched",
                        phase=current_phase,
                        iteration=iteration,
                    )
                    await evidence.append_decision(
                        pool=pool,
                        session_id=session_id,
                        phase=current_phase,
                        action="safety_block",
                        reason=f"rule {safety.rule_id} pattern '{safety.rule_pattern}'",
                        iteration=iteration,
                    )
                    # Feed denial to LLM as tool_result so messages[] stays well-formed,
                    # then terminate session immediately. No fix chance for safety blocks.
                    messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": f"SAFETY_BLOCK: {safety.reason}",
                            "is_error": True,
                        }],
                    })
                    await _mark_terminal(
                        pool, session_id, "failed",
                        f"safety_guard_blocked: rule {safety.rule_id}"
                    )
                    return {
                        "session_id": session_id,
                        "phase": "failed",
                        "iteration": iteration,
                        "reason": "safety_guard_blocked",
                    }

            # Detect signal.
            signal_name, payload = _detect_signal(command)

            if signal_name == SIGNAL_GOAL_COMPLETE:
                await evidence.append_decision(
                    pool=pool,
                    session_id=session_id,
                    phase="executing",
                    action="goal_complete",
                    reason=payload or "(no summary)",
                    iteration=iteration,
                )
                # Feed a synthetic tool_result so messages[] stays well-formed
                # in case of resume, then terminate.
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": "signal intercepted: GOAL_COMPLETE",
                    }],
                })
                await _mark_terminal(pool, session_id, "complete", payload or "goal complete")
                return {
                    "session_id": session_id,
                    "phase": "complete",
                    "iteration": iteration,
                    "reason": payload or "goal complete",
                }

            if signal_name == SIGNAL_STUCK:
                await evidence.append_decision(
                    pool=pool,
                    session_id=session_id,
                    phase="executing",
                    action="stuck",
                    reason=payload or "(no reason)",
                    iteration=iteration,
                )
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": "signal intercepted: STUCK",
                    }],
                })
                await _mark_terminal(pool, session_id, "failed", f"STUCK: {payload}")
                return {
                    "session_id": session_id,
                    "phase": "failed",
                    "iteration": iteration,
                    "reason": f"STUCK: {payload}",
                }

            if signal_name == SIGNAL_CLARIFICATION_NEEDED:
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": "signal intercepted: CLARIFICATION_NEEDED, session paused",
                    }],
                })
                await _pause_for_clarification(
                    pool, session_id, payload or "(no question)", iteration
                )
                return {
                    "session_id": session_id,
                    "phase": "paused",
                    "iteration": iteration,
                    "reason": "awaiting clarification",
                    "pending_question": payload,
                }

            if signal_name == SIGNAL_NEEDS_MORE_CONTEXT:
                # Load context, inject as next user message, NO iteration increment.
                await evidence.append_decision(
                    pool=pool,
                    session_id=session_id,
                    phase="executing",
                    action="needs_more_context",
                    reason=payload or "(no request)",
                    iteration=iteration,
                )
                try:
                    expansion = await _load_context_for_request(pool, payload or "")
                except Exception as e:
                    expansion = f"Error loading context: {type(e).__name__}: {e}"
                # Feed tool_result for the signal call.
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": "signal intercepted: NEEDS_MORE_CONTEXT, material incoming",
                    }],
                })
                pending_injection = expansion
                continue  # NO iteration increment

            # Regular command: run autonomy check, execute, append evidence.
            decision = await autonomy.check_session_autonomy(pool, session_id, command)
            await evidence.append_decision(
                pool=pool,
                session_id=session_id,
                phase="executing",
                action="autonomy_check",
                reason=decision.reason,
                iteration=iteration,
            )

            if not decision.allowed:
                # Feed denial as tool_result so LLM knows why it was blocked,
                # increment iteration (costs an LLM turn), continue.
                deny_text = f"AUTONOMY_DENY: {decision.reason}"
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": deny_text,
                        "is_error": True,
                    }],
                })
                # Synthetic "result" for next iteration user message builder
                # to avoid duplicate turn injection.
                last_command_result = {
                    "cmd": command,
                    "machine": machine,
                    "exit_code": 126,  # conventional "permission denied"
                    "stdout": "",
                    "stderr": deny_text,
                    "duration_ms": 0,
                }
                await evidence.append_command(
                    pool=pool,
                    session_id=session_id,
                    cmd=command,
                    machine=machine,
                    exit_code=126,
                    stdout="",
                    stderr=deny_text,
                    duration_ms=0,
                )
                await _increment_iteration(pool, session_id)

                # If the deny was specifically a require_job that needs user
                # confirmation and we're not allowed to escalate inline,
                # pause the session instead of spinning.
                if "requires user confirmation" in decision.reason:
                    await _pause_for_clarification(
                        pool,
                        session_id,
                        f"Command requires user confirmation: {command[:200]}",
                        iteration,
                    )
                    return {
                        "session_id": session_id,
                        "phase": "paused",
                        "iteration": iteration,
                        "reason": "requires user confirmation",
                        "pending_question": f"Approve command: {command[:200]}",
                    }
                # Otherwise let loop continue; LLM will see deny and adapt.
                # Clear last_command_result because we already injected the
                # deny as tool_result above - the next user msg would be the
                # synthetic fallback which is fine.
                last_command_result = None
                continue

            # Autonomy allowed - execute the command.
            print(f"[loop] iter {iteration} autonomy ALLOW: {decision.reason}")
            print(f"[loop] iter {iteration} exec on {machine}: {command[:200]}")
            try:
                result = await tools.exec_tool(machine=machine, command=command)
            except Exception as e:
                await evidence.append_error(
                    pool=pool,
                    session_id=session_id,
                    code="E_EXEC_FAIL",
                    msg=f"{type(e).__name__}: {e}",
                    phase="executing",
                    iteration=iteration,
                )
                result = {
                    "cmd": command,
                    "machine": machine,
                    "exit_code": 255,
                    "stdout": "",
                    "stderr": f"exec_tool exception: {e}",
                    "duration_ms": 0,
                }

            await evidence.append_command(
                pool=pool,
                session_id=session_id,
                cmd=result["cmd"],
                machine=result["machine"],
                exit_code=result["exit_code"],
                stdout=result["stdout"],
                stderr=result["stderr"],
                duration_ms=result["duration_ms"],
            )

            # Z5 (Session 4): Post-execution verification chain (Faza E).
            await _set_session_phase(pool, session_id, "verifying")
            current_phase = "verifying"

            try:
                verif = await verification.run_verification_chain(
                    pool=pool, cmd=command, result=result, exec_fn=None
                )
            except asyncpg.PostgresError as e:
                await evidence.append_error(
                    pool=pool, session_id=session_id, code="E_VERIFY_DB",
                    msg=f"verification DB query failed: {type(e).__name__}: {e}",
                    phase="verifying", iteration=iteration,
                )
                await _mark_terminal(pool, session_id, "failed", f"verification DB error: {e}")
                return {"session_id": session_id, "phase": "failed", "reason": "verify_db_error"}

            verif_dict = _verif_to_dict(verif)

            # Append verification entries to evidence (D8: include zero-match case).
            if not verif.matched_rules:
                await evidence.append_verification(
                    pool=pool, session_id=session_id,
                    rule_id=None, pattern_matched=None, rule_type="none",
                    passed=True, details="no rules matched, treating as pass",
                )
            else:
                for mr in verif.matched_rules:
                    await evidence.append_verification(
                        pool=pool, session_id=session_id,
                        rule_id=mr.rule_id, pattern_matched=mr.pattern,
                        rule_type=mr.rule_type, passed=mr.passed, details=mr.note,
                    )

            if verif.passed:
                # Verification passed - reset fix counter, return to executing.
                fix_attempt = 0
                last_verification_result = verif_dict
                await _set_session_phase(pool, session_id, "executing")
                current_phase = "executing"
            else:
                on_fail = verif.effective_on_fail or "abort"
                await evidence.append_decision(
                    pool=pool, session_id=session_id, phase="verifying",
                    action=f"verify_fail_{on_fail}", reason=verif.note,
                    iteration=iteration,
                )

                if on_fail == "abort":
                    await _mark_terminal(
                        pool, session_id, "failed",
                        f"verification abort: {verif.note}"
                    )
                    return {
                        "session_id": session_id, "phase": "failed",
                        "iteration": iteration,
                        "reason": f"verify_abort: {verif.note}",
                    }
                elif on_fail == "escalate":
                    await _pause_for_clarification(
                        pool, session_id,
                        f"Verification escalated to user review: {verif.note}",
                        iteration,
                    )
                    return {
                        "session_id": session_id, "phase": "paused",
                        "iteration": iteration, "reason": "verify_escalate",
                        "pending_question": verif.note,
                    }
                elif on_fail == "retry":
                    # D9: re-run same command, max 2 retries, no LLM call.
                    retry_passed = False
                    for retry_n in range(1, 3):
                        print(f"[loop] iter {iteration} verify retry {retry_n}/2: {command[:120]}")
                        try:
                            retry_result = await tools.exec_tool(machine=machine, command=command)
                        except Exception as e:
                            retry_result = {
                                "cmd": command, "machine": machine, "exit_code": 255,
                                "stdout": "", "stderr": f"retry exec exception: {e}",
                                "duration_ms": 0,
                            }
                        await evidence.append_command(
                            pool=pool, session_id=session_id,
                            cmd=retry_result["cmd"], machine=retry_result["machine"],
                            exit_code=retry_result["exit_code"], stdout=retry_result["stdout"],
                            stderr=retry_result["stderr"], duration_ms=retry_result["duration_ms"],
                        )
                        try:
                            retry_verif = await verification.run_verification_chain(
                                pool=pool, cmd=command, result=retry_result, exec_fn=None
                            )
                        except asyncpg.PostgresError as e:
                            await evidence.append_error(
                                pool=pool, session_id=session_id, code="E_VERIFY_DB",
                                msg=f"verify DB error in retry: {e}",
                                phase="verifying", iteration=iteration,
                            )
                            await _mark_terminal(pool, session_id, "failed", "verify db error in retry")
                            return {"session_id": session_id, "phase": "failed", "reason": "verify_db_error"}

                        if not retry_verif.matched_rules:
                            await evidence.append_verification(
                                pool=pool, session_id=session_id,
                                rule_id=None, pattern_matched=None, rule_type="none",
                                passed=True, details="no rules matched on retry",
                            )
                        else:
                            for mr in retry_verif.matched_rules:
                                await evidence.append_verification(
                                    pool=pool, session_id=session_id,
                                    rule_id=mr.rule_id, pattern_matched=mr.pattern,
                                    rule_type=mr.rule_type, passed=mr.passed, details=mr.note,
                                )

                        if retry_verif.passed:
                            retry_passed = True
                            result = retry_result
                            verif = retry_verif
                            verif_dict = _verif_to_dict(verif)
                            break

                    if retry_passed:
                        fix_attempt = 0
                        last_verification_result = verif_dict
                        await _set_session_phase(pool, session_id, "executing")
                        current_phase = "executing"
                    else:
                        # D12: retry exhausted -> fall through to fix path.
                        on_fail = "fix"

                # NOT elif - this catches both direct fix and retry-exhausted fall-through.
                if on_fail == "fix":
                    # Bug fix: check cap BEFORE increment so MAX_FIX_ATTEMPTS=3 means
                    # exactly 3 fix attempts allowed (1, 2, 3 then terminal on the 4th).
                    if fix_attempt >= MAX_FIX_ATTEMPTS:
                        await _mark_terminal(
                            pool, session_id, "failed",
                            f"fix_loop_exhausted after {MAX_FIX_ATTEMPTS} attempts"
                        )
                        return {
                            "session_id": session_id, "phase": "failed",
                            "iteration": iteration, "reason": "fix_loop_exhausted",
                        }
                    fix_attempt += 1
                    await _set_session_phase(pool, session_id, "fixing")
                    current_phase = "fixing"
                    last_verification_result = verif_dict

            # Feed tool_result back to Claude in messages[].
            tr_text = (
                f"exit_code={result['exit_code']}, duration={result['duration_ms']}ms\n"
                f"stdout: {(result['stdout'] or '')[:1500]}\n"
                f"stderr: {(result['stderr'] or '')[:500]}"
            )
            messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": tr_text,
                }],
            })

            last_command_result = result
            await _increment_iteration(pool, session_id)

    except Exception as e:
        tb = traceback.format_exc(limit=5)
        print(f"[loop] fatal exception in run_agent_loop: {e}\n{tb}")
        if pool is not None:
            try:
                await evidence.append_error(
                    pool=pool,
                    session_id=session_id,
                    code="E_LOOP_FATAL",
                    msg=f"{type(e).__name__}: {e}",
                    phase="executing",
                    iteration=-1,
                )
                await _mark_terminal(pool, session_id, "failed", f"fatal: {e}")
            except Exception:
                pass
        return {"session_id": session_id, "phase": "failed", "reason": str(e)}
    finally:
        if pool is not None:
            await pool.close()
