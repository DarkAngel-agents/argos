#!/usr/bin/env python3
"""
ARGOS Skill Selector
Selects relevant sub-skills from skills_tree based on task context.
Strategy: keyword match -> Ollama ranking -> Grok fallback (max 100 tokens)
"""
import os
import re
import asyncio
import asyncpg
import httpx
import json
from typing import Optional

DB_HOST = os.getenv("DB_HOST", "11.11.11.111")
DB_PORT = int(os.getenv("DB_PORT", 5433))
DB_USER = os.getenv("DB_USER", "claude")
DB_PASS = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "claudedb")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://172.17.0.1:11435")
OLLAMA_MODEL = "qwen3:14b"
GROK_API_KEY = os.getenv("GROK_API_KEY", "")
GROK_URL = "https://api.x.ai/v1/chat/completions"
GROK_MODEL = "grok-3-mini"

STOPWORDS = {
    "the","a","an","is","are","was","were","be","been","being",
    "have","has","had","do","does","did","will","would","could",
    "should","may","might","shall","can","need","want","make",
    "how","what","when","where","why","which","who","please",
    "help","me","my","i","it","its","this","that","these","those",
    "and","or","but","if","then","so","for","to","in","on","at",
    "with","from","by","of","as","not","no","yes","ok"
}

OLLAMA_HEALTHY = True
OLLAMA_RETRY_COUNT = 0
MAX_OLLAMA_RETRIES = 3


async def extract_keywords(task: str) -> list[str]:
    """Extract meaningful keywords from task text."""
    words = re.findall(r'[a-z0-9]+', task.lower())
    keywords = [w for w in words if w not in STOPWORDS and len(w) > 2]
    # Add compound terms
    compounds = re.findall(r'[a-z0-9]+-[a-z0-9]+', task.lower())
    keywords.extend(compounds)
    return list(set(keywords))


async def keyword_search(conn, keywords: list[str], limit: int = 15) -> list[dict]:
    """Fast keyword match against tags array."""
    if not keywords:
        return []
    rows = await conn.fetch("""
        SELECT id, path, name, tags, source, emergency, content,
               (SELECT COUNT(*) FROM unnest(tags) t WHERE t = ANY($1::text[])) as match_score
        FROM skills_tree
        WHERE EXISTS (SELECT 1 FROM unnest(tags) t WHERE t = ANY($1::text[]))
        ORDER BY
            CASE WHEN source = 'manual' THEN 1 ELSE 2 END,
            (SELECT COUNT(*) FROM unnest(tags) t WHERE t = ANY($1::text[])) DESC,
            usage_count DESC
        LIMIT $2
    """, keywords, limit)
    return [dict(r) for r in rows]


async def ollama_rank(task: str, candidates: list[dict]) -> list[dict]:
    """Use Ollama to rank candidates by relevance. Returns ordered list."""
    global OLLAMA_HEALTHY, OLLAMA_RETRY_COUNT

    if not OLLAMA_HEALTHY:
        return candidates

    candidate_list = "\n".join([
        f"{i+1}. [{r['path']}] {r['name']} (tags: {','.join(r['tags'])})"
        for i, r in enumerate(candidates)
    ])

    prompt = f"""Task: {task}

Skills available:
{candidate_list}

Return ONLY a JSON array of numbers representing the ranking from most to least relevant.
Example: [3,1,4,2,5]
No explanation, just the JSON array."""

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
            )
            if resp.status_code != 200:
                raise Exception(f"Ollama HTTP {resp.status_code}")

            text = resp.json().get("response", "").strip()
            match = re.search(r'\[[\d,\s]+\]', text)
            if not match:
                raise Exception("No valid ranking in response")

            ranking = json.loads(match.group())
            OLLAMA_RETRY_COUNT = 0
            OLLAMA_HEALTHY = True

            reordered = []
            for idx in ranking:
                if 1 <= idx <= len(candidates):
                    reordered.append(candidates[idx-1])
            # append any missed
            for c in candidates:
                if c not in reordered:
                    reordered.append(c)
            return reordered

    except Exception as e:
        OLLAMA_RETRY_COUNT += 1
        if OLLAMA_RETRY_COUNT >= MAX_OLLAMA_RETRIES:
            OLLAMA_HEALTHY = False
            print(f"[SKILL_SELECTOR] Ollama unhealthy after {MAX_OLLAMA_RETRIES} failures: {e}")
            print("[SKILL_SELECTOR] STATUS: Ollama GPU down")
            print("[SKILL_SELECTOR] CAUSE: Container not responding")
            print("[SKILL_SELECTOR] ACTION: Attempting restart...")
            await attempt_ollama_restart()
        return candidates


async def attempt_ollama_restart() -> bool:
    """Try to restart Ollama container. Returns True if successful."""
    import subprocess
    for attempt in range(1, 4):
        try:
            result = subprocess.run(
                ["docker", "restart", "argos-ollama"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                await asyncio.sleep(5)
                # verify
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(f"{OLLAMA_URL}/api/tags")
                    if resp.status_code == 200:
                        global OLLAMA_HEALTHY, OLLAMA_RETRY_COUNT
                        OLLAMA_HEALTHY = True
                        OLLAMA_RETRY_COUNT = 0
                        print("[SKILL_SELECTOR] Ollama restart OK")
                        return True
        except Exception as e:
            print(f"[SKILL_SELECTOR] Restart attempt {attempt} failed: {e}")
        await asyncio.sleep(3)

    print("[SKILL_SELECTOR] DEFCON: Ollama could not be restarted after 3 attempts")
    print("[SKILL_SELECTOR] Fallback available: Grok / Claude")
    print("[SKILL_SELECTOR] Awaiting DarkAngel confirmation to switch provider")
    return False


async def grok_tags(task: str) -> list[str]:
    """Use Grok micro-query to suggest tags. Max 100 tokens output."""
    if not GROK_API_KEY:
        return []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                GROK_URL,
                headers={"Authorization": f"Bearer {GROK_API_KEY}"},
                json={
                    "model": GROK_MODEL,
                    "max_tokens": 100,
                    "messages": [{
                        "role": "user",
                        "content": f"List 5-8 technical tags for this task (lowercase, comma separated, no explanation): {task}"
                    }]
                }
            )
            text = resp.json()["choices"][0]["message"]["content"]
            tags = [t.strip().lower() for t in text.split(",") if t.strip()]
            return tags[:8]
    except Exception as e:
        print(f"[SKILL_SELECTOR] Grok fallback failed: {e}")
        return []


async def update_usage(conn, skill_ids: list[int]):
    """Increment usage_count for selected skills."""
    if skill_ids:
        await conn.execute(
            "UPDATE skills_tree SET usage_count = usage_count + 1, last_used = now() WHERE id = ANY($1)",
            skill_ids
        )


async def select_skills(task: str, max_results: int = 5) -> list[dict]:
    """
    Main entry point. Returns ordered list of relevant skills.
    """
    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASS, database=DB_NAME
    )

    try:
        keywords = await extract_keywords(task)
        candidates = await keyword_search(conn, keywords)

        if len(candidates) < 3 and GROK_API_KEY:
            grok_tags_list = await grok_tags(task)
            if grok_tags_list:
                extra_keywords = list(set(keywords + grok_tags_list))
                candidates = await keyword_search(conn, extra_keywords)

        if len(candidates) > 3:
            candidates = await ollama_rank(task, candidates)

        selected = candidates[:max_results]
        await update_usage(conn, [s["id"] for s in selected])
        return selected

    finally:
        await conn.close()


async def main():
    """CLI test mode."""
    import sys
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "restart postgres docker container"
    print(f"Task: {task}\n")
    results = await select_skills(task)
    for i, skill in enumerate(results, 1):
        print(f"{i}. [{skill['source']}] {skill['path']}")
        print(f"   {skill['name']}")
        print(f"   tags: {skill['tags']}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
