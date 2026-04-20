import os
import anthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

COMPRESS_THRESHOLD = 30000  # tokeni input - prag avertisment
KEEP_LAST_N = 10            # mesaje recente care raman intotdeauna complete


class CompressRequest(BaseModel):
    conversation_id: int


@router.get("/conversations/{conv_id}/token-count")
async def get_token_count(conv_id: int):
    from api.main import pool
    messages = await _load_messages(pool, conv_id)
    if not messages:
        return {"input_tokens": 0, "warning": False}

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    try:
        response = client.messages.count_tokens(
            model="claude-sonnet-4-6",
            messages=messages,
        )
        input_tokens = response.input_tokens
        return {
            "input_tokens": input_tokens,
            "warning": input_tokens >= COMPRESS_THRESHOLD,
            "threshold": COMPRESS_THRESHOLD
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations/compress")
async def compress_conversation(req: CompressRequest):
    from api.main import pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, role, content FROM messages
            WHERE conversation_id = $1
            ORDER BY created_at ASC
            """,
            req.conversation_id
        )

    if len(rows) <= KEEP_LAST_N:
        return {"status": "skipped", "reason": "prea putine mesaje"}

    # Mesajele vechi de comprimat (toate mai putin ultimele N)
    old_messages = rows[:-KEEP_LAST_N]
    recent_messages = rows[-KEEP_LAST_N:]

    if not old_messages:
        return {"status": "skipped", "reason": "nimic de comprimat"}

    # Construim textul pentru rezumat
    text_to_summarize = "\n".join([
        f"[{r['role'].upper()}]: {r['content']}"
        for r in old_messages
    ])

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": f"""Fă un rezumat tehnic concis al acestei conversații.
Reține: decizii luate, configurații discutate, probleme rezolvate, fișiere importante, IP-uri, comenzi cheie, starea curentă a proiectului.
Ignoră: salutări, întrebări retorice, confirmări simple, bla-bla.
Format: paragraf scurt per subiect major, fără bullet points excesive.

CONVERSAȚIE:
{text_to_summarize}"""
            }]
        )
        summary = response.content[0].text
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Salvam segmentul in DB si stergem mesajele vechi
    async with pool.acquire() as conn:
        old_ids = [r['id'] for r in old_messages]

        # Salvam rezumatul ca segment
        await conn.execute(
            """
            INSERT INTO segments (conversation_id, summary, message_start_id, message_end_id, created_at)
            VALUES ($1, $2, $3, $4, NOW())
            """,
            req.conversation_id,
            summary,
            old_ids[0],
            old_ids[-1]
        )

        # Stergem mesajele vechi
        await conn.execute(
            "DELETE FROM messages WHERE id = ANY($1::int[])",
            old_ids
        )

        # Inseram rezumatul ca mesaj sistem la inceputul conversatiei
        await conn.execute(
            """
            INSERT INTO messages (conversation_id, role, content, created_at)
            VALUES ($1, 'assistant', $2, (
                SELECT created_at FROM messages WHERE conversation_id = $1 ORDER BY created_at ASC LIMIT 1
            ) - interval '1 second')
            """,
            req.conversation_id,
            f"[REZUMAT CONVERSAȚIE ANTERIOARĂ]\n{summary}"
        )

    return {
        "status": "ok",
        "messages_compressed": len(old_messages),
        "messages_kept": len(recent_messages),
        "summary_length": len(summary)
    }


async def _load_messages(pool, conversation_id: int) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT role, content FROM messages WHERE conversation_id = $1 ORDER BY created_at ASC",
            conversation_id
        )
    return [{"role": r["role"], "content": r["content"]} for r in rows]
