"""
ARGOS dashboard summary endpoint.
Pas 2.1 - aggregates counts for the dashboard module landing page.
Read-only. Single endpoint: GET /api/dashboard/summary
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/dashboard/summary")
async def dashboard_summary():
    from api.main import pool

    async with pool.acquire() as conn:
        # SESSIONS card (agent_sessions)
        sessions_active   = await conn.fetchval(
            "SELECT COUNT(*) FROM agent_sessions WHERE active = TRUE"
        )
        sessions_complete = await conn.fetchval(
            "SELECT COUNT(*) FROM agent_sessions WHERE phase = 'complete'"
        )
        sessions_failed   = await conn.fetchval(
            "SELECT COUNT(*) FROM agent_sessions WHERE phase = 'failed'"
        )
        sessions_total    = await conn.fetchval(
            "SELECT COUNT(*) FROM agent_sessions"
        )

        # JOBS card
        jobs_waiting = await conn.fetchval(
            "SELECT COUNT(*) FROM jobs WHERE status IN ('pending','waiting_auth')"
        )
        jobs_running = await conn.fetchval(
            "SELECT COUNT(*) FROM jobs WHERE status = 'running'"
        )
        jobs_today   = await conn.fetchval(
            "SELECT COUNT(*) FROM jobs WHERE created_at >= CURRENT_DATE"
        )
        jobs_total   = await conn.fetchval(
            "SELECT COUNT(*) FROM jobs"
        )

        # CHATS card (conversations + conversation_archives)
        conversations_total = await conn.fetchval(
            "SELECT COUNT(*) FROM conversations"
        )
        archives_total = await conn.fetchval(
            "SELECT COUNT(*) FROM conversation_archives"
        )
        last_activity = await conn.fetchval(
            "SELECT MAX(updated_at) FROM conversations"
        )

        # REASONING card
        reasoning_today = await conn.fetchval(
            "SELECT COUNT(*) FROM reasoning_log WHERE ts >= CURRENT_DATE"
        )
        reasoning_total = await conn.fetchval(
            "SELECT COUNT(*) FROM reasoning_log"
        )

        # HEALTH card (heartbeat_checks, only enabled)
        health_rows = await conn.fetch(
            "SELECT last_status, COUNT(*) AS n FROM heartbeat_checks "
            "WHERE enabled = TRUE GROUP BY last_status"
        )
        health_by_status = {r["last_status"] or "unknown": r["n"] for r in health_rows}
        health_total_enabled = sum(health_by_status.values())

        # FLEET card - Pas 2 stub. Real data vine la /api/fleet in Pas 3.
        # Marcam clar ca placeholder ca sa nu para date reale.
        fleet_stub = {
            "total": None,
            "online": None,
            "announced": None,
            "installing": None,
            "note": "stub - /api/fleet vine la Pas 3"
        }

        # RECENT ACTIVITY (Pas 2 stub: doar ultimele 10 conversations updated)
        # TODO Pas 3 SSE: union pe sessions/jobs/fleet/chats cu timestamp.
        recent_rows = await conn.fetch(
            "SELECT id, title, updated_at FROM conversations "
            "ORDER BY updated_at DESC NULLS LAST LIMIT 10"
        )
        recent_activity = [
            {
                "kind": "chat",
                "id": r["id"],
                "label": r["title"] or f"conv #{r['id']}",
                "ts": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
            for r in recent_rows
        ]

    return {
        "sessions": {
            "active":   sessions_active,
            "complete": sessions_complete,
            "failed":   sessions_failed,
            "total":    sessions_total,
        },
        "jobs": {
            "waiting": jobs_waiting,
            "running": jobs_running,
            "today":   jobs_today,
            "total":   jobs_total,
        },
        "chats": {
            "conversations": conversations_total,
            "archived":      archives_total,
            "last_activity": last_activity.isoformat() if last_activity else None,
        },
        "reasoning": {
            "today": reasoning_today,
            "total": reasoning_total,
        },
        "health": {
            "by_status":     health_by_status,
            "total_enabled": health_total_enabled,
        },
        "fleet": fleet_stub,
        "recent_activity": recent_activity,
    }
