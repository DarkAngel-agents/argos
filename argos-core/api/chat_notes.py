# chat_notes.py - Notes/agenda handling extracted from chat.py
# Pool passed as parameter, not global

NOTE_WRITE_KEYWORDS = [
    "noteaza asta",
    "noteaza",
    "adauga in agenda",
    "pune in agenda",
    "scrie in lista",
    "adauga task",
    "note this",
    "add to agenda",
    "add task",
    "put in list",
]

NOTE_READ_KEYWORDS = [
    "ce am de facut",
    "ce am in agenda",
    "arata agenda",
    "ce e in lista",
    "ce urmeaza",
    "what's on my agenda",
    "what do i have to do",
    "show agenda",
    "show my tasks",
    "what's next",
]


def detect_note_intent(text: str):
    """Detecteaza daca mesajul e comanda notes. Returneaza dict sau None."""
    if not text:
        return None
    t = text.strip().lower()
    # Citire - match la start
    for kw in NOTE_READ_KEYWORDS:
        if t == kw or t.startswith(kw + "?") or t.startswith(kw + "!") or t == kw + ".":
            return {"action": "read", "content": ""}
    # Scriere - match la start, cele mai lungi primele (lista ordonata)
    for kw in NOTE_WRITE_KEYWORDS:
        if t.startswith(kw):
            rest = text.strip()[len(kw):].lstrip(" :-,")
            return {"action": "write", "content": rest}
    return None


async def handle_note_write(pool, content: str) -> str:
    """Insereaza in notes. Refuza continut gol."""
    if not content or not content.strip():
        return "? Ce sa notez? Spune-mi dupa keyword, ex: 'noteaza sapun la cumparaturi'"
    async with pool.acquire() as conn:
        note_id = await conn.fetchval(
            """INSERT INTO notes (category, content, status, priority, created_at, updated_at)
               VALUES ('general', $1, 'active', 5, NOW(), NOW()) RETURNING id""",
            content.strip()
        )
    preview = content.strip()
    if len(preview) > 80:
        preview = preview[:80] + "..."
    return f"Notat #{note_id}: {preview}"


async def handle_agenda_read(pool) -> str:
    """Citeste notes active grupate pe categorii."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, category, content, priority, created_at
               FROM notes WHERE status = 'active'
               ORDER BY priority ASC, created_at DESC LIMIT 50"""
        )
    if not rows:
        return "Agenda e goala."
    by_cat = {}
    for r in rows:
        by_cat.setdefault(r['category'] or 'general', []).append(r)
    lines = [f"Agenda ({len(rows)} active):"]
    for cat in sorted(by_cat.keys()):
        items = by_cat[cat]
        lines.append(f"\n**{cat.upper()}** ({len(items)}):")
        for n in items:
            # stele pentru priority: 1=5 stele, 5=1 stea
            stars_count = max(1, 6 - (n['priority'] or 5))
            stars = "*" * stars_count
            text = n['content'] or ''
            if len(text) > 100:
                text = text[:100] + "..."
            lines.append(f"  #{n['id']} {stars} {text}")
    return "\n".join(lines)
