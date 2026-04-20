import os
import re
import asyncpg
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/.argos/argos-core/config/.env"))

pool = None
system_prompt = None  # core prompt - mereu prezent
_module_cache = {}    # cache module din DB
_axiom_cache = {}     # cache reasoning axioms per domain

AXIOM_KEYWORDS = {
    "infrastructure": ["docker","swarm","postgres","postgresql","proxmox","backup","haproxy","container","registry","volume","stack","deploy","nfs","replication"],
    "linux-admin": ["nixos","debian","systemd","apt","service","sudo","chmod","chown","cron","kernel","boot","grub","mount","fstab","journal"],
    "networking": ["unifi","vlan","dns","network","firewall","port","ip ","route","ping","ssh","haproxy","proxy","udm","mikrotik","cisco","adguard"],
    "programming": ["python","bash","code","script","function","api"," sql","query","json","async","import","class","def ","error","debug"],
}

def _select_axioms(text: str) -> list:
    text_lower = text.lower()
    selected = ["base"]
    for domain, keywords in AXIOM_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            selected.append(domain)
    return selected



def escape_like(value: str) -> str:
    """Escape special ILIKE characters to prevent false positives"""
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


async def load_core_prompt(conn) -> str:
    """Incarca modulul core din DB"""
    row = await conn.fetchrow(
        "SELECT content FROM prompt_modules WHERE name = 'core-behavior' AND active = TRUE"
    )
    if not row:
        return ""
    core = row["content"]

    # Load reasoning axioms from DB to cache (replicated to Hermes via streaming)
    axiom_rows = await conn.fetch(
        "SELECT domain, content FROM reasoning_axioms WHERE active = TRUE ORDER BY domain"
    )
    if axiom_rows:
        _axiom_cache.clear()
        for row in axiom_rows:
            _axiom_cache[row['domain']] = row['content']
        print(f"[STARTUP] Reasoning axioms cached: {list(_axiom_cache.keys())}")
        # Include only base axiom in core prompt
        if 'base' in _axiom_cache:
            core = core + "\n---\n## REASONING AXIOMS\n### BASE\n" + _axiom_cache['base']

    # reasoning_mode: local=axioms only, full=axioms+reasoning_log
    reasoning_mode = await conn.fetchval(
        "SELECT value FROM settings WHERE key='reasoning_mode'"
    ) or "local"
    if reasoning_mode == "full":
        log_rows = await conn.fetch(
            "SELECT type, content FROM reasoning_log ORDER BY ts DESC LIMIT 20"
        )
        if log_rows:
            parts2 = [core, "\n---\n## REASONING HISTORY (last 20)"]
            for row in log_rows:
                parts2.append(f"[{row['type']}] {row['content'][:200]}")
            core = "\n\n".join(parts2)
            print(f"[STARTUP] Reasoning mode=full, loaded {len(log_rows)} log entries")
    # Substitute placeholders from settings
    username = await conn.fetchval("SELECT value FROM settings WHERE key='username'") or "user"
    language = await conn.fetchval("SELECT value FROM settings WHERE key='language'") or "en"
    core = core.replace("$username$", username).replace("$language$", language)
    return core


async def detect_modules(text: str, conn) -> list:
    """Detecteaza ce module sunt relevante pe baza textului"""
    text_lower = text.lower()
    rows = await conn.fetch(
        "SELECT name, keywords, priority, content FROM prompt_modules WHERE active = TRUE AND name NOT IN ('core-behavior', 'core-self-knowledge') ORDER BY priority"
    )
    matched = []
    for row in rows:
        keywords = row["keywords"] or []
        if any(kw in text_lower for kw in keywords):
            matched.append(dict(row))
    return matched


async def build_prompt_for_conversation(conversation_id: int, new_message: str) -> str:
    """Construieste system prompt complet pentru o conversatie"""
    global pool
    async with pool.acquire() as conn:
        # Core intotdeauna
        core = await load_core_prompt(conn)
        # Contextual axiom selection
        relevant_domains = _select_axioms(new_message)
        axiom_parts = []
        for domain in relevant_domains:
            if domain in _axiom_cache and domain != "base":
                axiom_parts.append(f"### {domain.upper()}\n{_axiom_cache[domain]}")
        if axiom_parts:
            core = core + "\n---\n## REASONING AXIOMS (contextual)\n" + "\n".join(axiom_parts)

        # Detecteaza module din mesajul nou + ultimele 3 mesaje din conversatie
        context_rows = await conn.fetch(
            "SELECT content FROM messages WHERE conversation_id = $1 ORDER BY created_at DESC LIMIT 3",
            conversation_id
        )
        context_text = new_message + " " + " ".join(r["content"] for r in context_rows)
        modules = await detect_modules(context_text, conn)

        # Verifica preferinte salvate
        pref = await conn.fetchrow(
            "SELECT modules FROM module_preferences WHERE confirmed_by_user = TRUE AND $1 ILIKE '%' || pattern || '%' ESCAPE '\\' ORDER BY times_used DESC LIMIT 1",
            escape_like(new_message)
        )

    if not modules and not pref:
        return core

    # Construieste prompt complet
    parts = [core]
    module_names = []

    if pref:
        # Foloseste preferintele confirmate de user
        pref_modules = pref["modules"]
        async with pool.acquire() as conn:
            for mod_name in pref_modules:
                row = await conn.fetchrow("SELECT content FROM prompt_modules WHERE name = $1", mod_name)
                if row:
                    parts.append(f"\n---\n{row['content']}")
                    module_names.append(mod_name)
    else:
        for mod in modules:
            parts.append(f"\n---\n{mod['content']}")
            module_names.append(mod["name"])

    if module_names:
        print(f"[ARGOS] Module incarcate: {', '.join(module_names)}")

    return "\n".join(parts)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool, system_prompt
    import socket
    is_hermes = socket.gethostname().lower() == 'hermes'
    db_candidates = [
        (os.getenv("DB_HOST", "11.11.11.111"), int(os.getenv("DB_PORT", 5433))),
    ] if is_hermes else [
        ("172.17.0.1", 5433),
        (os.getenv("DB_HOST", "11.11.11.111"), int(os.getenv("DB_PORT", 5433))),
    ]
    pool = None
    for db_host, db_port in db_candidates:
        try:
            async def init_connection(conn):
                await conn.execute("SET tcp_keepalives_idle = 20")
                await conn.execute("SET tcp_keepalives_interval = 5")
                await conn.execute("SET tcp_keepalives_count = 3")

            pool = await asyncpg.create_pool(
                host=db_host,
                port=db_port,
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                database=os.getenv("DB_NAME"),
                ssl=False,
                min_size=1,
                max_size=5,
                timeout=3,
                max_inactive_connection_lifetime=25,
                command_timeout=60,
                server_settings={"tcp_keepalives_idle": "20", "tcp_keepalives_interval": "5", "tcp_keepalives_count": "3"},
                init=init_connection
            )
            print(f"[ARGOS] DB connected via {db_host}:{db_port}", flush=True)
            break
        except Exception as e:
            print(f"[ARGOS] DB {db_host}:{db_port} failed: {e}", flush=True)
            pool = None
    if pool is None:
        raise Exception("All DB connections failed")

    from api.debug import set_pool as debug_set_pool
    debug_set_pool(pool)
    # Curata pending
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM messages WHERE pending = TRUE")
        if count:
            await conn.execute("UPDATE messages SET pending = FALSE WHERE pending = TRUE")
            print(f"Cleared {count} pending messages from previous session")

    # Working memory check - anunta daca era ceva in lucru la crash
    async with pool.acquire() as conn:
        wm = await conn.fetch(
            "SELECT id, task_current, steps_done, conversation_id FROM working_memory WHERE status='active' ORDER BY last_update DESC LIMIT 3"
        )
        if wm:
            print(f"[ARGOS] WARNING: {len(wm)} task(s) interrupted at crash:", flush=True)
            for w in wm:
                steps = w['steps_done'] or []
                last_step = steps[-1] if steps else "unknown"
                print(f"  - Conv {w['conversation_id']}: {str(w['task_current'])[:80]} | last step: {last_step}", flush=True)
            # Marca ca interrupted, nu sterge
            await conn.execute("UPDATE working_memory SET status='interrupted' WHERE status='active'")


    # Health check - restaureaza fisiere lipsa din LTS
    from api.backup import WATCHED_FILES
    async with pool.acquire() as conn:
        for module_name, file_path in WATCHED_FILES.items():
            if not os.path.exists(file_path):
                print(f"[STARTUP] Fisier lipsa: {file_path} - restaurez din LTS")
                row = await conn.fetchrow(
                    "SELECT content FROM file_versions WHERE module_name = $1 AND version_type = 'lts'",
                    module_name
                )
                if row:
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    with open(file_path, "wb") as f:
                        f.write(bytes(row["content"]))
                    print(f"[STARTUP] Restaurat: {file_path}")

    # Incarca core prompt din DB
    async with pool.acquire() as conn:
        system_prompt = await load_core_prompt(conn)
        if system_prompt:
            print(f"[STARTUP] Core prompt incarcat din DB ({len(system_prompt)} chars)")
        else:
            # Fallback la fisier daca DB nu are modulul
            path = os.path.expanduser("~/.argos/argos-core/config/system_prompt.txt")
            if os.path.exists(path):
                with open(path, "r") as f:
                    system_prompt = f.read().strip()
                print(f"[STARTUP] System prompt incarcat din fisier ({len(system_prompt)} chars)")

    print("DB connected")
    yield
    await pool.close()
    print("DB closed")


async def get_pool():
    """Returneaza pool-ul activ, recreandu-l daca e mort."""
    global pool
    if pool is None:
        return None
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return pool
    except Exception:
        print("[ARGOS] Pool mort - recreez conexiunea DB...", flush=True)
        try:
            pool = await asyncpg.create_pool(
                host="172.17.0.1", port=5433,
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                database=os.getenv("DB_NAME"),
                ssl=False, min_size=1, max_size=5,
                max_inactive_connection_lifetime=25,
                command_timeout=60
            )
            print("[ARGOS] Pool recreat OK", flush=True)
        except Exception as e:
            print(f"[ARGOS] Pool recreat FAIL: {e}", flush=True)
        return pool


app = FastAPI(lifespan=lifespan)
@app.middleware("http")
async def catch_db_errors(request, call_next):
    try:
        response = await call_next(request)
        # Log 5xx responses even when they come as HTTPException (FastAPI doesn't traceback them)
        if hasattr(response, 'status_code') and response.status_code >= 500:
            print(f"[REQ ERROR] {request.method} {request.url.path} -> HTTP {response.status_code}", flush=True)
        return response
    except Exception as e:
        import traceback
        print(f"[REQ ERROR] {request.method} {request.url.path} -> {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()
        raise



from api.chat import router as chat_router
from api.compress import router as compress_router
from api.executor import router as executor_router
from api.vms import router as vms_router
from api.jobs import router as jobs_router
from api.local_executor import router as local_router
from api.backup import router as backup_router
from api.iso_builder import router as iso_router
from api.archives import router as archives_router
from api.nanite import router as nanite_router
from api.dashboard import router as dashboard_router
from api.conversations import router as conversations_router
from api.fleet import router as fleet_router
from api.stream import router as stream_router
from api.health import router as health_router
app.include_router(chat_router, prefix="/api")
app.include_router(compress_router, prefix="/api")
app.include_router(executor_router, prefix="/api")
app.include_router(vms_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(local_router, prefix="/api")
app.include_router(backup_router, prefix="/api")
app.include_router(iso_router, prefix="/api")
app.include_router(archives_router, prefix="/api")
app.include_router(nanite_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(conversations_router, prefix="/api")
app.include_router(fleet_router, prefix="/api")
app.include_router(stream_router, prefix="/api")
app.include_router(health_router, prefix="/api")


# UI v1 redesign - workflow paralel, nu atinge UI vechi (ruta /)
app.mount(
    "/ui",
    StaticFiles(directory="/home/darkangel/.argos/argos-core/ui", html=True),
    name="ui",
)


@app.get("/")
async def index():
    return FileResponse("/home/darkangel/.argos/argos-core/ui/index.html")


@app.get("/health")
async def health():
    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT version()")
        modules = await conn.fetchval("SELECT COUNT(*) FROM prompt_modules WHERE active = TRUE")
    return {"status": "ok", "db": result, "prompt_modules": modules}


@app.get("/api/prompt-modules")
async def list_prompt_modules():
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT name, category, display_name, keywords, priority, active FROM prompt_modules ORDER BY priority"
        )
    return {"modules": [dict(r) for r in rows]}


@app.get("/api/system-profiles")
async def list_system_profiles():
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, display_name, os_type, ip, role, purpose, prompt_modules FROM system_profiles WHERE active = TRUE ORDER BY name"
        )
        profiles = []
        for r in rows:
            p = dict(r)
            creds = await conn.fetch(
                "SELECT credential_type, label, username, value_hint FROM system_credentials WHERE system_id = $1 AND active = TRUE",
                r["id"]
            )
            p["credentials"] = [dict(c) for c in creds]
            profiles.append(p)
    return {"profiles": profiles}


@app.get("/api/settings/{key}")
async def get_setting(key: str):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT value FROM settings WHERE key = $1", key)
    return {"key": key, "value": row["value"] if row else None}


@app.post("/api/settings/{key}")
async def set_setting(key: str, value: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES ($1, $2, NOW()) ON CONFLICT (key) DO UPDATE SET value=$2, updated_at=NOW()",
            key, value
        )
    return {"key": key, "value": value}


@app.get("/api/reasoning-mode")
async def get_reasoning_mode():
    async with pool.acquire() as conn:
        mode = await conn.fetchval(
            "SELECT value FROM settings WHERE key='reasoning_mode'"
        ) or "local"
    return {"mode": mode}

@app.post("/api/reasoning-mode")
async def set_reasoning_mode(data: dict):
    mode = data.get("mode", "local")
    if mode not in ("local", "full"):
        mode = "local"
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO settings (key, value) VALUES ('reasoning_mode', $1) ON CONFLICT (key) DO UPDATE SET value=$1",
            mode
        )
    return {"mode": mode}

@app.get("/api/debug/logs")
async def get_debug_logs(limit: int = 50, code: str = None, level: str = None):
    async with pool.acquire() as conn:
        if code:
            rows = await conn.fetch(
                "SELECT ts, level, module, code, message, context FROM debug_logs WHERE code=$1 ORDER BY ts DESC LIMIT $2",
                code, limit
            )
        elif level:
            rows = await conn.fetch(
                "SELECT ts, level, module, code, message, context FROM debug_logs WHERE level=$1 ORDER BY ts DESC LIMIT $2",
                level, limit
            )
        else:
            rows = await conn.fetch(
                "SELECT ts, level, module, code, message, context FROM debug_logs ORDER BY ts DESC LIMIT $1",
                limit
            )
    return {"logs": [dict(r) for r in rows]}
