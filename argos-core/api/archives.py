"""
Archives - arhivare conversatii cu taguri + log entries pentru Android
"""
import os
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()

# ── Models ────────────────────────────────────────────────────────────────────

class CreateArchiveRequest(BaseModel):
    conversation_id: int
    title: str
    summary: Optional[str] = None
    tags: List[str] = []

class UpdateArchiveRequest(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[List[str]] = None

class LogEntryRequest(BaseModel):
    type: str = "info"   # cmd, ok, error, info
    message: str
    conversation_id: Optional[int] = None

# ── Log endpoints ─────────────────────────────────────────────────────────────

@router.post("/livelog")
async def add_log_entry(entry: LogEntryRequest):
    """Adauga o intrare in log — apelat intern de Argos"""
    from api.main import pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO log_entries (type, message, conversation_id) VALUES ($1, $2, $3) RETURNING id, created_at",
            entry.type, entry.message, entry.conversation_id
        )
    return {"id": row["id"], "created_at": row["created_at"]}


@router.get("/livelog")
async def get_log(since_id: int = 0, limit: int = 50):
    """Returneaza log entries dupa since_id — folosit de Android app pentru polling"""
    from api.main import pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, type, message, conversation_id, created_at
               FROM log_entries
               WHERE id > $1
               ORDER BY id ASC
               LIMIT $2""",
            since_id, limit
        )
    return {
        "entries": [
            {
                "id": r["id"],
                "type": r["type"],
                "message": r["message"],
                "conversation_id": r["conversation_id"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None
            }
            for r in rows
        ]
    }


@router.delete("/livelog/cleanup")
async def cleanup_log(keep_last: int = 1000):
    """Sterge log entries vechi, pastreaza ultimele N"""
    from api.main import pool
    async with pool.acquire() as conn:
        deleted = await conn.fetchval(
            """DELETE FROM log_entries WHERE id NOT IN (
               SELECT id FROM log_entries ORDER BY id DESC LIMIT $1
            ) RETURNING COUNT(*)""",
            keep_last
        )
    return {"deleted": deleted or 0}

# ── Archive endpoints ─────────────────────────────────────────────────────────

@router.get("/archives")
async def list_archives(tag: str = None, search: str = None, limit: int = 50):
    """Lista arhivari cu filtrare dupa tag sau cuvant cheie"""
    from api.main import pool
    async with pool.acquire() as conn:
        query = """
            SELECT a.id, a.conversation_id, a.title, a.summary, a.tags,
                   a.created_at, a.updated_at,
                   c.title as conv_title
            FROM conversation_archives a
            LEFT JOIN conversations c ON a.conversation_id = c.id
            WHERE 1=1
        """
        args = []
        if tag:
            args.append(tag)
            query += f" AND ${ len(args)} = ANY(a.tags)"
        if search:
            args.append(f"%{search}%")
            query += f" AND (a.title ILIKE ${len(args)} OR a.summary ILIKE ${len(args)})"
        query += f" ORDER BY a.updated_at DESC LIMIT {limit}"
        rows = await conn.fetch(query, *args)
    return {
        "archives": [
            {
                "id": r["id"],
                "conversation_id": r["conversation_id"],
                "title": r["title"],
                "summary": r["summary"],
                "tags": list(r["tags"]) if r["tags"] else [],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
                "conv_title": r["conv_title"]
            }
            for r in rows
        ]
    }


@router.get("/archives/tags")
async def list_tags():
    """Lista toate tagurile disponibile cu count"""
    from api.main import pool
    async with pool.acquire() as conn:
        tags = await conn.fetch(
            "SELECT name, display_name, color, icon, sort_order FROM archive_tags ORDER BY sort_order"
        )
        counts = await conn.fetch(
            "SELECT unnest(tags) as tag, COUNT(*) as cnt FROM conversation_archives GROUP BY tag"
        )
    count_map = {r["tag"]: r["cnt"] for r in counts}
    return {
        "tags": [
            {
                "name": t["name"],
                "display_name": t["display_name"],
                "color": t["color"],
                "icon": t["icon"],
                "count": count_map.get(t["name"], 0)
            }
            for t in tags
        ]
    }


@router.post("/archives")
async def create_archive(req: CreateArchiveRequest):
    """Creeaza o arhivare noua pentru o conversatie"""
    from api.main import pool
    async with pool.acquire() as conn:
        # Verifica daca conversatia exista
        conv = await conn.fetchrow(
            "SELECT id, title FROM conversations WHERE id = $1", req.conversation_id
        )
        if not conv:
            raise HTTPException(status_code=404, detail="Conversatie negasita")

        # Daca nu are titlu, foloseste titlul conversatiei
        title = req.title or conv["title"] or f"Arhiva #{req.conversation_id}"

        row = await conn.fetchrow(
            """INSERT INTO conversation_archives (conversation_id, title, summary, tags)
               VALUES ($1, $2, $3, $4) RETURNING id, created_at""",
            req.conversation_id, title, req.summary, req.tags
        )
    return {"id": row["id"], "created_at": row["created_at"].isoformat(), "status": "ok"}


@router.get("/archives/{archive_id}")
async def get_archive(archive_id: int):
    """Detalii arhivare + mesajele conversatiei asociate"""
    from api.main import pool
    async with pool.acquire() as conn:
        archive = await conn.fetchrow(
            """SELECT a.*, c.title as conv_title
               FROM conversation_archives a
               LEFT JOIN conversations c ON a.conversation_id = c.id
               WHERE a.id = $1""",
            archive_id
        )
        if not archive:
            raise HTTPException(status_code=404, detail="Arhivare negasita")

        messages = []
        if archive["conversation_id"]:
            msgs = await conn.fetch(
                """SELECT id, role, content, created_at
                   FROM messages
                   WHERE conversation_id = $1 AND pending = FALSE
                   ORDER BY created_at ASC""",
                archive["conversation_id"]
            )
            messages = [
                {
                    "id": m["id"],
                    "role": m["role"],
                    "content": m["content"],
                    "created_at": m["created_at"].isoformat() if m["created_at"] else None
                }
                for m in msgs
            ]

    return {
        "id": archive["id"],
        "conversation_id": archive["conversation_id"],
        "title": archive["title"],
        "summary": archive["summary"],
        "tags": list(archive["tags"]) if archive["tags"] else [],
        "created_at": archive["created_at"].isoformat() if archive["created_at"] else None,
        "updated_at": archive["updated_at"].isoformat() if archive["updated_at"] else None,
        "conv_title": archive["conv_title"],
        "messages": messages
    }


@router.patch("/archives/{archive_id}")
async def update_archive(archive_id: int, req: UpdateArchiveRequest):
    """Actualizeaza titlu, rezumat sau taguri"""
    from api.main import pool
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT * FROM conversation_archives WHERE id = $1", archive_id
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Arhivare negasita")

        title   = req.title   if req.title   is not None else existing["title"]
        summary = req.summary if req.summary is not None else existing["summary"]
        tags    = req.tags    if req.tags    is not None else list(existing["tags"])

        await conn.execute(
            """UPDATE conversation_archives
               SET title=$1, summary=$2, tags=$3, updated_at=NOW()
               WHERE id=$4""",
            title, summary, tags, archive_id
        )
    return {"status": "ok"}


@router.delete("/archives/{archive_id}")
async def delete_archive(archive_id: int):
    """Sterge o arhivare"""
    from api.main import pool
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM conversation_archives WHERE id = $1", archive_id
        )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Arhivare negasita")
    return {"status": "ok"}


@router.post("/archives/{archive_id}/resume")
async def resume_from_archive(archive_id: int):
    """Creeaza o conversatie noua preincarcata cu contextul arhivarii"""
    from api.main import pool
    async with pool.acquire() as conn:
        archive = await conn.fetchrow(
            "SELECT * FROM conversation_archives WHERE id = $1", archive_id
        )
        if not archive:
            raise HTTPException(status_code=404, detail="Arhivare negasita")

        # Creeaza conversatie noua
        new_conv = await conn.fetchrow(
            """INSERT INTO conversations (title, created_at, updated_at)
               VALUES ($1, NOW(), NOW()) RETURNING id""",
            f"Resume: {archive['title']}"
        )
        conv_id = new_conv["id"]

        # Adauga mesaj de context ca prim mesaj system
        context = f"[Continuare arhiva: {archive['title']}]\n"
        if archive["summary"]:
            context += f"\nRezumat: {archive['summary']}"
        if archive["tags"]:
            context += f"\nTaguri: {', '.join(archive['tags'])}"

        await conn.execute(
            """INSERT INTO messages (conversation_id, role, content, tokens_input, cost_eur, pending, created_at)
               VALUES ($1, 'assistant', $2, 0, 0, FALSE, NOW())""",
            conv_id, context
        )

    return {"status": "ok", "conversation_id": conv_id, "title": f"Resume: {archive['title']}"}
