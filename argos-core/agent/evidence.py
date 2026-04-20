"""
ARGOS Agent - Evidence JSONB helpers.

Append-only helpers for agent_sessions.evidence JSONB column.
Uses jsonb_set + || operator with $N::jsonb binding - NEVER string concat.

Evidence schema (5 top-level keys, documented in skill #92):
- commands:      list of executed commands with output
- verifications: list of verification rule matches with pass/fail
- errors:        list of error events with code + phase + iter
- decisions:     list of agent decisions with reason
- llm_calls:     list of LLM invocations with tokens + cost

All helpers are idempotent-safe: they append, never overwrite.
Each helper also touches last_active_at as a checkpoint heartbeat.
"""
import json
from datetime import datetime, timezone
from typing import Optional

import asyncpg


async def _append_to_evidence_key(
    pool: asyncpg.Pool,
    session_id: int,
    key: str,
    entry: dict,
) -> None:
    """
    Internal helper: append `entry` to evidence[key] array atomically.

    Uses jsonb_set + || operator. Entry is serialized to JSON once in Python
    and passed as $3::jsonb binding. Updates last_active_at in same statement
    for checkpoint heartbeat.

    NULLIF on evidence->$2 defends against JSONB null stored in the key
    (distinct from SQL NULL): if someone accidentally writes
    `UPDATE agent_sessions SET evidence = '{"commands": null}'::jsonb`,
    plain COALESCE would pass null through and || would fail. NULLIF catches it.

    Raises asyncpg errors on DB failure - caller decides retry/abort.
    """
    # default=str is permissive - datetime/Decimal serialize correctly,
    # but bytes/Path/custom objects become str(obj) representation (e.g. "b'\\x...'")
    # without raising. Only pass primitives + datetime + Decimal in entry dicts.
    entry_json = json.dumps([entry], default=str)  # wrap in list for || array concat
    sql = """
        UPDATE agent_sessions
        SET evidence = jsonb_set(
                evidence,
                ARRAY[$2]::text[],
                COALESCE(NULLIF(evidence->$2, 'null'::jsonb), '[]'::jsonb) || $3::jsonb
            ),
            last_active_at = NOW()
        WHERE id = $1
    """
    async with pool.acquire() as conn:
        await conn.execute(sql, session_id, key, entry_json)


async def append_command(
    pool: asyncpg.Pool,
    session_id: int,
    cmd: str,
    machine: str,
    exit_code: int,
    stdout: str,
    stderr: str,
    duration_ms: int,
) -> None:
    """
    Append a command execution record to evidence.commands.

    Shape per skill #92:
    {
      "cmd": "...",
      "machine": "beasty",
      "exit_code": 0,
      "stdout": "...",
      "stderr": "...",
      "duration_ms": 1200,
      "ts": "2026-04-06T18:30:00Z"
    }
    """
    entry = {
        "cmd": cmd,
        "machine": machine,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "duration_ms": duration_ms,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    await _append_to_evidence_key(pool, session_id, "commands", entry)


async def append_verification(
    pool: asyncpg.Pool,
    session_id: int,
    rule_id: Optional[int],
    pattern_matched: Optional[str],
    rule_type: str,
    passed: bool,
    details: str = "",
) -> None:
    """
    Append a verification check result to evidence.verifications.

    Shape per skill #92:
    {
      "rule_id": 11,
      "pattern_matched": "^docker service ls",
      "rule_type": "grep_not",
      "passed": true,
      "details": "no 0/N found",
      "ts": "..."
    }
    """
    entry = {
        "rule_id": rule_id,
        "pattern_matched": pattern_matched,
        "rule_type": rule_type,
        "passed": passed,
        "details": details,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    await _append_to_evidence_key(pool, session_id, "verifications", entry)


async def append_error(
    pool: asyncpg.Pool,
    session_id: int,
    code: str,
    msg: str,
    phase: str,
    iteration: int,
) -> None:
    """
    Append an error event to evidence.errors.

    Shape per skill #92:
    {
      "code": "E_VERIFY_FAIL",
      "msg": "nixos-rebuild exit=1",
      "phase": "verifying",
      "iter": 3,
      "ts": "..."
    }
    """
    entry = {
        "code": code,
        "msg": msg,
        "phase": phase,
        "iter": iteration,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    await _append_to_evidence_key(pool, session_id, "errors", entry)


async def append_decision(
    pool: asyncpg.Pool,
    session_id: int,
    phase: str,
    action: str,
    reason: str,
    iteration: int,
) -> None:
    """
    Append an agent decision to evidence.decisions.

    Shape per skill #92:
    {
      "phase": "fixing",
      "action": "retry_with_sudo",
      "reason": "permission denied in stderr",
      "iter": 4,
      "ts": "..."
    }
    """
    entry = {
        "phase": phase,
        "action": action,
        "reason": reason,
        "iter": iteration,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    await _append_to_evidence_key(pool, session_id, "decisions", entry)


async def append_llm_call(
    pool: asyncpg.Pool,
    session_id: int,
    provider: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    phase: str,
    cost_eur: Optional[float] = None,
) -> None:
    """
    Append an LLM call record to evidence.llm_calls.

    Shape per skill #92:
    {
      "provider": "claude",
      "model": "claude-sonnet-4-6",
      "tokens_in": 1500,
      "tokens_out": 400,
      "cost_eur": 0.012,
      "phase": "planning",
      "ts": "..."
    }

    cost_eur is optional: None until pricing module exists (Session 3+).
    """
    entry = {
        "provider": provider,
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_eur": cost_eur,
        "phase": phase,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    await _append_to_evidence_key(pool, session_id, "llm_calls", entry)


async def update_session_totals(
    pool: asyncpg.Pool,
    session_id: int,
    tokens_delta: int,
    cost_delta_eur: float = 0.0,
) -> None:
    """
    Increment agent_sessions.total_tokens and total_cost_eur atomically.

    Called after each LLM response. Separate from append_llm_call because
    totals live in dedicated columns (indexed, fast aggregates), while
    per-call detail lives in evidence.llm_calls JSONB.

    IMPORTANT: cost_delta_eur MUST be 0.0 (not None) when pricing module is
    unavailable. Passing None will fail on NULL arithmetic in SQL.
    Caller is responsible for converting None -> 0.0 before calling this.
    """
    sql = """
        UPDATE agent_sessions
        SET total_tokens = total_tokens + $2,
            total_cost_eur = total_cost_eur + $3,
            last_active_at = NOW()
        WHERE id = $1
    """
    async with pool.acquire() as conn:
        await conn.execute(sql, session_id, tokens_delta, cost_delta_eur)
