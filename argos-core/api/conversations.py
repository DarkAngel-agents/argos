"""
ARGOS conversations - extra endpoints peste cele din chat.py.
Pas 2.5 - Instant promote flow (Q4=A): muta toate mesajele din conv id=1
intr-o conversatie noua named, lasand Instant gol.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


router = APIRouter()


class PromoteRequest(BaseModel):
    title: str


@router.post("/conversations/1/promote")
async def promote_instant(req: PromoteRequest):
    """
    Q4=A flow: promote Instant (conv id=1) to a new named conversation.
    Atomic move: create new conversation, move all messages from id=1 to new id.
    Instant ramane gol dar pastreaza id=1 si setarile.
    """
    from api.main import pool

    title = (req.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title required")
    if len(title) > 200:
        raise HTTPException(status_code=400, detail="title too long (max 200)")

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Verify Instant exists
            instant = await conn.fetchval(
                "SELECT id FROM conversations WHERE id = 1"
            )
            if instant is None:
                raise HTTPException(status_code=404, detail="Instant (id=1) missing")

            # Count messages to move (for response + sanity)
            msg_count = await conn.fetchval(
                "SELECT COUNT(*) FROM messages WHERE conversation_id = 1"
            )
            if msg_count == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Instant is empty, nothing to promote"
                )

            # Create new conversation
            new_id = await conn.fetchval(
                "INSERT INTO conversations (title, created_at, updated_at) "
                "VALUES ($1, NOW(), NOW()) RETURNING id",
                title
            )

            # Move messages
            moved = await conn.execute(
                "UPDATE messages SET conversation_id = $1 WHERE conversation_id = 1",
                new_id
            )

    return {
        "new_id": new_id,
        "title": title,
        "messages_moved": msg_count,
        "moved_status": moved,
    }
