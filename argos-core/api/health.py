"""
ARGOS health endpoints.
Pas 4.2 - snapshot + log queries pe heartbeat_log direct.
heartbeat_checks tabel exista dar e mort (daemon nu il updateaza), folosim heartbeat_log ca sursa de adevar.
"""
from fastapi import APIRouter
from typing import Optional


router = APIRouter()


@router.get("/health/snapshot")
async def health_snapshot():
    """
    Latest entry per (node, service) pair from heartbeat_log.
    Returns one row per unique node+service combination, most recent first.
    """
    from api.main import pool

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT DISTINCT ON (node, service)
                   id, node, service, status, cpu_pct, mem_pct,
                   db_latency_ms, containers_up, error_code, error_msg, ts
               FROM heartbeat_log
               ORDER BY node, service, ts DESC"""
        )

    items = []
    for r in rows:
        items.append({
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

    # Summary counts
    counts = {
        "total": len(items),
        "ok":    sum(1 for x in items if x["status"] == "ok"),
        "warn":  sum(1 for x in items if x["status"] == "warn"),
        "error": sum(1 for x in items if x["status"] == "error"),
        "unknown": sum(1 for x in items if x["status"] not in ("ok","warn","error")),
    }

    # Group by node for UI
    by_node = {}
    for it in items:
        by_node.setdefault(it["node"], []).append(it)

    return {
        "items": items,
        "by_node": by_node,
        "counts": counts,
        "source": "heartbeat_log",
        "note": "heartbeat_checks table is dead - daemon writes to log only",
    }


@router.get("/health/log")
async def health_log(node: Optional[str] = None, service: Optional[str] = None, limit: int = 100):
    """
    Recent history from heartbeat_log, optional filter by node and/or service.
    """
    from api.main import pool

    if limit < 1: limit = 1
    if limit > 500: limit = 500

    where_parts = []
    params = []
    if node:
        params.append(node)
        where_parts.append(f"node = ${len(params)}")
    if service:
        params.append(service)
        where_parts.append(f"service = ${len(params)}")
    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    params.append(limit)
    limit_param = f"${len(params)}"

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT id, node, service, status, cpu_pct, mem_pct,
                       db_latency_ms, containers_up, error_code, error_msg, ts
                FROM heartbeat_log
                {where_sql}
                ORDER BY ts DESC
                LIMIT {limit_param}""",
            *params
        )

    return {
        "log": [
            {
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
            }
            for r in rows
        ],
        "filter": {"node": node, "service": service, "limit": limit},
    }
