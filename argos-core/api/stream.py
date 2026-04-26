"""
ARGOS SSE activity stream.
Pas 3.3 - polling DB intern (variant A), eventuri minime: tick + heartbeat + heartbeat_summary.
TODO Pas 4: chat_message, auth_pending, job_update, fleet_change, agent_phase.
"""
import asyncio
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from api.rate_limit import limiter


router = APIRouter()


def _sse(event: str, data: dict) -> str:
    """Format one SSE message block."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.get("/stream/activity")
@limiter.limit("10/minute")  # audit N6 — cap SSE connection rate per IP
async def stream_activity(request: Request):
    """
    Single SSE stream for ARGOS live activity.
    Polls DB every 2s. Emits:
      - tick (every 5s) keep-alive + seq
      - heartbeat (per new heartbeat_log row)
      - heartbeat_summary (every 30s, snapshot of heartbeat_checks)
    """
    from api.main import pool

    POLL_INTERVAL = 2.0
    TICK_INTERVAL = 5.0
    SUMMARY_INTERVAL = 30.0

    async def event_generator():
        last_seen_log_id = 0
        last_seen_msg_id = 0
        known_pending_auth_ids: set = set()
        last_job_states: dict = {}
        tick_seq = 0
        last_tick = 0.0
        last_summary = 0.0

        # Bootstrap: snapshot current max ids + state so we don't dump history
        try:
            async with pool.acquire() as conn:
                last_seen_log_id = await conn.fetchval(
                    "SELECT COALESCE(MAX(id), 0) FROM heartbeat_log"
                ) or 0
                last_seen_msg_id = await conn.fetchval(
                    "SELECT COALESCE(MAX(id), 0) FROM messages"
                ) or 0
                pending_rows = await conn.fetch(
                    "SELECT id FROM authorizations WHERE status = 'pending'"
                )
                known_pending_auth_ids = {r["id"] for r in pending_rows}
                job_rows = await conn.fetch("SELECT id, status FROM jobs")
                last_job_states = {r["id"]: r["status"] for r in job_rows}
        except Exception as e:
            yield _sse("error", {"msg": f"bootstrap failed: {type(e).__name__}: {e}"})

        # Initial hello so client knows stream is alive immediately
        yield _sse("hello", {
            "ts": datetime.now(timezone.utc).isoformat(),
            "msg": "argos stream connected",
            "bootstrap_log_id": last_seen_log_id,
            "bootstrap_msg_id": last_seen_msg_id,
            "bootstrap_pending_auth": len(known_pending_auth_ids),
            "bootstrap_jobs": len(last_job_states),
        })

        while True:
            # Check disconnect
            if await request.is_disconnected():
                return

            now = asyncio.get_event_loop().time()

            # === heartbeat_log delta ===
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT id, node, service, status, cpu_pct, mem_pct, "
                        "       db_latency_ms, containers_up, error_code, error_msg, ts "
                        "FROM heartbeat_log WHERE id > $1 ORDER BY id ASC LIMIT 50",
                        last_seen_log_id,
                    )
                for r in rows:
                    last_seen_log_id = r["id"]
                    yield _sse("heartbeat", {
                        "id": r["id"],
                        "node": r["node"],
                        "service": r["service"],
                        "status": r["status"],
                        "cpu_pct": r["cpu_pct"],
                        "mem_pct": r["mem_pct"],
                        "db_latency_ms": r["db_latency_ms"],
                        "containers_up": r["containers_up"],
                        "error_code": r["error_code"],
                        "error_msg": r["error_msg"],
                        "ts": r["ts"].isoformat() if r["ts"] else None,
                    })
            except Exception as e:
                yield _sse("error", {"src": "heartbeat_log", "msg": f"{type(e).__name__}: {e}"})

            # === auth_pending delta ===
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT id, job_id, operation, details, risk_level, requested_at "
                        "FROM authorizations WHERE status = 'pending'"
                    )
                current_pending = {r["id"]: r for r in rows}
                # Added (new pending)
                for aid in set(current_pending.keys()) - known_pending_auth_ids:
                    r = current_pending[aid]
                    yield _sse("auth_pending", {
                        "id": r["id"],
                        "job_id": r["job_id"],
                        "operation": r["operation"],
                        "details": r["details"],
                        "risk_level": r["risk_level"],
                        "requested_at": r["requested_at"].isoformat() if r["requested_at"] else None,
                        "action": "added",
                    })
                # Removed (decided)
                for aid in known_pending_auth_ids - set(current_pending.keys()):
                    yield _sse("auth_decided", {
                        "id": aid,
                        "action": "removed",
                    })
                known_pending_auth_ids = set(current_pending.keys())
            except Exception as e:
                yield _sse("error", {"src": "auth_pending", "msg": f"{type(e).__name__}: {e}"})

            # === job_state changes ===
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch("SELECT id, status, title FROM jobs")
                for r in rows:
                    jid = r["id"]
                    new_status = r["status"]
                    old_status = last_job_states.get(jid)
                    if old_status is not None and old_status != new_status:
                        yield _sse("job_state", {
                            "id": jid,
                            "title": r["title"],
                            "old_status": old_status,
                            "new_status": new_status,
                        })
                    last_job_states[jid] = new_status
            except Exception as e:
                yield _sse("error", {"src": "job_state", "msg": f"{type(e).__name__}: {e}"})

            # === chat_message new ===
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT id, conversation_id, role, content, created_at "
                        "FROM messages WHERE id > $1 ORDER BY id ASC LIMIT 20",
                        last_seen_msg_id,
                    )
                for r in rows:
                    last_seen_msg_id = r["id"]
                    content = r["content"] or ""
                    preview = content[:120] + ("..." if len(content) > 120 else "")
                    yield _sse("chat_message", {
                        "id": r["id"],
                        "conversation_id": r["conversation_id"],
                        "role": r["role"],
                        "preview": preview,
                        "ts": r["created_at"].isoformat() if r["created_at"] else None,
                    })
            except Exception as e:
                yield _sse("error", {"src": "chat_message", "msg": f"{type(e).__name__}: {e}"})

            # === heartbeat_summary every 30s ===
            if now - last_summary >= SUMMARY_INTERVAL:
                try:
                    async with pool.acquire() as conn:
                        srows = await conn.fetch(
                            "SELECT component, check_name, display_name, last_status, "
                            "       last_value, last_checked, unit "
                            "FROM heartbeat_checks WHERE enabled = TRUE "
                            "ORDER BY display_order, component"
                        )
                    yield _sse("heartbeat_summary", {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "checks": [
                            {
                                "component": r["component"],
                                "check_name": r["check_name"],
                                "display_name": r["display_name"],
                                "status": r["last_status"] or "unknown",
                                "value": float(r["last_value"]) if r["last_value"] is not None else None,
                                "unit": r["unit"],
                                "last_checked": r["last_checked"].isoformat() if r["last_checked"] else None,
                            }
                            for r in srows
                        ],
                    })
                    last_summary = now
                except Exception as e:
                    yield _sse("error", {"src": "heartbeat_summary", "msg": f"{type(e).__name__}: {e}"})

            # === tick keep-alive every 5s ===
            if now - last_tick >= TICK_INTERVAL:
                tick_seq += 1
                yield _sse("tick", {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "seq": tick_seq,
                })
                last_tick = now

            await asyncio.sleep(POLL_INTERVAL)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
