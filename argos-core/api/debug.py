"""
Argos Debug Logger
Coduri eroare:
  KB001 - KB insert fail        KB002 - KB query fail
  SSH001 - SSH connect fail     SSH002 - SSH timeout       SSH003 - SSH command fail (rc!=0)
  API001 - Anthropic API error  API002 - Grok API error    API003 - Ollama error
  SKILL001 - Skill load fail    SKILL002 - Skill not found
  DB001 - Pool acquire fail     DB002 - Query fail
  TOOL001 - Tool execute fail   TOOL002 - Tool unknown
  AUTH001 - Job auth fail
"""
import json
import traceback
import sys
from datetime import datetime

_pool = None

def set_pool(pool):
    global _pool
    _pool = pool

async def argos_log(level: str, module: str, code: str, message: str, context: dict = None):
    """
    level: DEBUG / INFO / WARN / ERROR / CRITICAL
    module: chat / executor / kb / skill / api / backup
    code: KB001, SSH002, etc
    """
    ctx = context or {}
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}][{level}][{code}] {module}: {message}", flush=True)

    if _pool is None:
        return
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO debug_logs (level, module, code, message, context) VALUES ($1, $2, $3, $4, $5)",
                level, module, code, message[:500], json.dumps(ctx)
            )
    except Exception as e:
        print(f"[DEBUG] log write fail: {e}", flush=True)

async def argos_error(module: str, code: str, message: str, exc: Exception = None, context: dict = None):
    ctx = context or {}
    if exc:
        ctx["traceback"] = traceback.format_exc()[-500:]
        ctx["exception"] = str(exc)[:200]
    await argos_log("ERROR", module, code, message, ctx)

async def argos_info(module: str, code: str, message: str, context: dict = None):
    await argos_log("INFO", module, code, message, context)
