# AUDIT REPORT 06 - API Endpoints + Middleware Deep Dive

**Generated:** 2026-04-14 20:42 UTC
**Target:** /home/darkangel/.argos/argos-core/api/
**Auditor:** Claude Code (read-only audit)

---

## Section 1: Rezumat executiv

API-ul ARGOS contine **77 endpoints** distribuite in **18 fisiere** cu un total de **5282 linii**. Fisierul dominant este `chat.py` cu **1550 linii** si **11 endpoints**. Distribution by method: GET (41), POST (28), DELETE (5). Arhitectura este modulara cu **15 routers** inclusi in main.py. **CRITICAL:** Zero authentication patterns detectate - toate endpoints sunt publice. Design-ul general este bun dar chat.py necesita decompose urgent.

---

## Section 2: Files overview (api/)

| File | Lines | Size | Severity |
|------|-------|------|----------|
| chat.py | 1550 | 68,773 bytes | **[CRITICAL]** |
| iso_builder.py | 630 | 25,230 bytes | **[HIGH]** |
| main.py | 432 | 17,347 bytes | **[MEDIUM]** |
| executor.py | 319 | 13,301 bytes | **[MEDIUM]** |
| archives.py | 290 | 10,955 bytes | **[MEDIUM]** |
| nanite.py | 289 | 10,776 bytes | **[MEDIUM]** |
| backup.py | 285 | 11,216 bytes | **[MEDIUM]** |
| jobs.py | 238 | 8,906 bytes | **[MEDIUM]** |
| stream.py | 226 | 9,725 bytes | **[MEDIUM]** |
| code_runner.py | 169 | 5,809 bytes | **[LOW]** |
| compress.py | 137 | 4,501 bytes | **[LOW]** |
| vms.py | 136 | 4,365 bytes | **[LOW]** |
| fleet.py | 131 | 5,161 bytes | **[LOW]** |
| dashboard.py | 125 | 4,320 bytes | **[LOW]** |
| health.py | 121 | 3,818 bytes | **[LOW]** |
| local_executor.py | 83 | 2,916 bytes | **[LOW]** |
| conversations.py | 69 | 2,236 bytes | **[LOW]** |
| debug.py | 52 | 1,826 bytes | **[LOW]** |

**TOTAL:** 5282 lines, 18 files

---

## Section 3: Endpoints inventory

- **Total endpoints:** 77
- **Distribution by HTTP method:**

| Method | Count |
|--------|-------|
| GET | 41 |
| POST | 28 |
| DELETE | 5 |
| PATCH | 2 |
| PUT | 1 |

**Endpoints per file (top files):**

### api/chat.py (11 endpoints)
| Line | Method | Path | Function |
|------|--------|------|----------|
| L189 | POST | /conversations | create_conversation |
| L200 | DELETE | /conversations/{conv_id} | delete_conversation |
| L209 | POST | /conversations/{conv_id}/stop | stop_conversation |
| L226 | POST | /estimate | estimate_cost |
| L249 | POST | /messages | send_message |
| L590 | GET | /conversations | list_conversations |
| L608 | PATCH | /prompt-modules/{module_id} | update_module |
| L618 | GET | /conversations/{conv_id}/reasoning | get_reasoning |
| L628 | DELETE | /conversations/{conv_id}/messages | clear_messages |
| L636 | GET | /conversations/{conv_id}/messages | get_messages |
| L654 | GET | /conversations/{conv_id}/pending | get_pending |

### api/archives.py (10 endpoints)
| Line | Method | Path | Function |
|------|--------|------|----------|
| L32 | POST | /livelog | add_log_entry |
| L44 | GET | /livelog | get_log |
| L71 | DELETE | /livelog/cleanup | cleanup_log |
| L86 | GET | /archives | list_archives |
| L125 | GET | /archives/tags | list_tags |
| L151 | POST | /archives | create_archive |
| L174 | GET | /archives/{archive_id} | get_archive |
| L221 | PATCH | /archives/{archive_id} | update_archive |
| L245 | DELETE | /archives/{archive_id} | delete_archive |
| L258 | POST | /archives/{archive_id}/resume | resume_from_archive |

### api/main.py (9 endpoints)
| Line | Method | Path | Function |
|------|--------|------|----------|
| L337 | GET | / | index |
| L342 | GET | /health | health |
| L350 | GET | /api/prompt-modules | list_prompt_modules |
| L359 | GET | /api/system-profiles | list_system_profiles |
| L377 | GET | /api/settings/{key} | get_setting |
| L384 | POST | /api/settings/{key} | set_setting |
| L394 | GET | /api/reasoning-mode | get_reasoning_mode |
| L402 | POST | /api/reasoning-mode | set_reasoning_mode |
| L414 | GET | /api/debug/logs | get_debug_logs |

**[INFO]** Structura clara cu endpoints bine distribuite. chat.py cu 11 endpoints e sub threshold de 50.

---

## Section 4: Middleware stack

| File | Line | Type |
|------|------|------|
| api/main.py | L281 | @app.middleware("http") |

**[INFO]** Un middleware HTTP prezent in main.py. Middleware stack minimal dar functional.

---

## Section 5: Router includes

**api/main.py router includes:**

| Line | Router |
|------|--------|
| L312 | chat_router |
| L313 | compress_router |
| L314 | executor_router |
| L315 | vms_router |
| L316 | jobs_router |
| L317 | local_router |
| L318 | backup_router |
| L319 | iso_router |
| L320 | archives_router |
| L321 | nanite_router |
| L322 | dashboard_router |
| L323 | conversations_router |
| L324 | fleet_router |
| L325 | stream_router |
| L326 | health_router |

**[INFO]** Arhitectura modulara cu 15 routers. Design pattern bun pentru organizare.

---

## Section 6: Pydantic models

| File | Models |
|------|--------|
| api/nanite.py | 4 (DiskInfo, NetworkInterface, NaniteAnnounce, InstallRequest) |
| api/chat.py | 3 (NewConversationRequest, MessageRequest, EstimateRequest) |
| api/executor.py | 3 (ExecRequest, NixosRebuildRequest, RestoreRequest) |
| api/archives.py | 3 (CreateArchiveRequest, UpdateArchiveRequest, LogEntryRequest) |
| api/iso_builder.py | 2 (BuildISORequest, KBEntry) |
| api/backup.py | 2 (MarkLTSRequest, RollbackRequest) |
| api/jobs.py | 2 (JobCreate, AuthDecision) |
| api/vms.py | 2 (VMAnnounce, VMProgress) |
| api/compress.py | 1 (CompressRequest) |
| api/local_executor.py | 1 (LocalTask) |
| api/conversations.py | 1 (PromoteRequest) |

**Total Pydantic models:** 24

**[INFO]** Buna acoperire cu Pydantic models pentru request validation.

---

## Section 7: HTTPException usage

**Distribution by status code:**

| Status | Count | Meaning |
|--------|-------|---------|
| 404 | 12 | Not Found |
| 500 | 8 | Internal Server Error |
| 400 | 6 | Bad Request |
| 409 | 1 | Conflict |
| 503 | 1 | Service Unavailable |
| 200 | 1 | OK (unusual for exception) |

**Per file:**

| File | Count |
|------|-------|
| api/jobs.py | 7 |
| api/chat.py | 6 |
| api/archives.py | 5 |
| api/conversations.py | 3 |
| api/executor.py | 2 |
| api/backup.py | 2 |
| api/compress.py | 2 |
| api/iso_builder.py | 1 |
| api/nanite.py | 1 |

**[MEDIUM]** 8 HTTPException cu status 500 - errors generice in loc de specifice. Ar beneficia de error codes mai granulare.

---

## Section 8: Authentication / Authorization

**Files using Depends/auth patterns:** 0

**[CRITICAL]** Zero authentication patterns detectate in api/. Toate cele 77 endpoints sunt publice si accesibile fara autentificare. Daca API-ul este expus extern, aceasta este o vulnerabilitate critica.

---

## Section 9: CORS

**[INFO]** No CORS configuration found.

Aceasta poate fi:
- OK daca API-ul si UI-ul sunt servite de pe acelasi origin
- **[HIGH]** Problema daca UI-ul este separat si CORS e necesar

---

## Section 10: chat.py deep

- **Total lines:** 1550

### Top 15 functions by length

| Lines | Location | Function | Severity |
|-------|----------|----------|----------|
| 337 | L250-586 | `async send_message()` | **[HIGH]** |
| 272 | L731-1002 | `async _execute_tool()` | **[HIGH]** |
| 84 | L1467-1550 | `async _generate_skill_from_web_impl()` | |
| 51 | L1206-1256 | `async _detect_and_load_skills()` | |
| 43 | L1259-1301 | `async _detect_os_and_load_skill()` | |
| 43 | L1386-1428 | `async _grok_search_for_skill()` | |
| 41 | L1343-1383 | `async _grok_reasoning()` | |
| 27 | L703-729 | `async _update_command_score()` | |
| 26 | L1174-1199 | `async _handle_agenda_read()` | |
| 25 | L1032-1056 | `async _compress_messages()` | |
| 19 | L227-245 | `async estimate_cost()` | |
| 18 | L655-672 | `async get_pending()` | |
| 18 | L1074-1091 | `_mask_credentials()` | |
| 15 | L637-651 | `async get_messages()` | |
| 15 | L1141-1155 | `_detect_note_intent()` | |

### Anthropic API call sites

| Line | Usage |
|------|-------|
| L231 | `client = anthropic.Anthropic(api_key=...)` |
| L383 | `client = anthropic.Anthropic(api_key=...)` |
| L405 | `response = client.messages.create(**kwargs)` |
| L1482 | `client = anthropic.Anthropic(api_key=...)` |
| L1513 | `response = client.messages.create(` |

**[MEDIUM]** 3 instantieri separate ale Anthropic client (L231, L383, L1482). Ar trebui un singur client instantiat la nivel de modul sau dependency injection.

### DB access calls

**Total:** 65 DB calls in chat.py

**[HIGH]** 65 DB calls intr-un singur fisier indica ca chat.py face prea multe. Combina LLM calls, tool execution, DB writes, skill detection.

---

## Section 11: main.py lifespan

- **Total lines:** 432
- **Lifecycle function:** `lifespan()` = 98 lines (L153-250)

### DB pool initialization

| Line | Pattern |
|------|---------|
| L171 | `pool = await asyncpg.create_pool(...)` |
| L265 | `pool = await asyncpg.create_pool(...)` |

### Global declarations

| Line | Declaration |
|------|-------------|
| L98 | `global pool` |
| L154 | `global pool, system_prompt` |
| L255 | `global pool` |

**[INFO]** Lifespan structurat cu pool init. 3 globals (pool, system_prompt) - acceptabil.

---

## Section 12: Streaming endpoints

**Files with streaming patterns:** 2

### api/stream.py (SSE)
| Line | Pattern |
|------|---------|
| L10 | `from fastapi.responses import StreamingResponse` |
| L61 | `yield _sse("error", ...)` |
| L64 | `yield _sse("hello", ...)` |
| L91 | `yield _sse("heartbeat", ...)` |
| L105 | `yield _sse("error", ...)` |

### api/main.py
| Line | Pattern |
|------|---------|
| L248 | `yield` |

**[INFO]** SSE implementat in stream.py pentru real-time activity. Modern UI pattern.

---

## Section 13: Cross-module dependencies

**Files importing from agent/llm/tools/reasoning:** 0

**[INFO]** API layer nu importa direct din agent/llm/tools/reasoning. Separare clara intre layers.

---

## Section 14: executor.py + backup.py + code_runner.py

### executor.py (319 lines)

| Lines | Function |
|-------|----------|
| 52 | `check_autonomy()` |
| 35 | `_exec_ssh()` |
| 30 | `nixos_rebuild()` |
| 25 | `restore_backup()` |
| 23 | `_exec_local()` |
| 23 | `log_action_outcome()` |
| 22 | `_exec_ssh_by_name()` |
| 13 | `execute_command()` |

### backup.py (285 lines)

| Lines | Function |
|-------|----------|
| 54 | `backup_file()` |
| 38 | `rollback_file()` |
| 25 | `auto_rollback_if_broken()` |
| 20 | `mark_lts()` |
| 16 | `_write_file_local()` |
| 12 | `get_backup_logs()` |
| 10 | `_read_file_local()` |
| 10 | `get_config_index()` |

### code_runner.py (169 lines)

| Lines | Function |
|-------|----------|
| 55 | `run_code()` |

**[INFO]** Confirmare task 02/03: IPs hardcoded in executor.py pentru SSH. KNOWN_HOSTS pattern folosit.

---

## Section 15: Endpoint complexity summary

| File | Endpoints | Methods Distribution |
|------|-----------|---------------------|
| api/chat.py | 11 | POST=4, GET=4, DELETE=2, PATCH=1 |
| api/archives.py | 10 | GET=4, POST=3, DELETE=2, PATCH=1 |
| api/main.py | 9 | GET=7, POST=2 |
| api/iso_builder.py | 8 | GET=5, POST=2, PUT=1 |
| api/backup.py | 7 | GET=4, POST=3 |
| api/jobs.py | 6 | POST=3, GET=3 |
| api/executor.py | 5 | POST=3, GET=2 |
| api/nanite.py | 5 | GET=3, POST=2 |
| api/vms.py | 5 | POST=2, GET=2, DELETE=1 |
| api/local_executor.py | 3 | POST=2, GET=1 |

---

## Section 16: Top 15 findings cross-cutting

1. **[CRITICAL]** api/chat.py = 1550 lines - urgent decompose in multiple modules
2. **[CRITICAL]** Zero auth on all 77 endpoints - API complet expus fara autentificare
3. **[HIGH]** chat.py `send_message()` = 337 lines - mixing LLM call + tool dispatch + DB write
4. **[HIGH]** chat.py `_execute_tool()` = 272 lines - complex tool execution logic
5. **[HIGH]** chat.py: 65 DB access calls - face prea multe responsabilitati
6. **[HIGH]** iso_builder.py = 630 lines - aproape de threshold 500, monitorizare
7. **[MEDIUM]** 3 Anthropic client instantiations in chat.py - should be single instance
8. **[MEDIUM]** 8 HTTPException cu status 500 - errors generice
9. **[MEDIUM]** executor.py + backup.py: SSH operations in API layer
10. **[INFO]** Arhitectura modulara cu 15 routers - design bun
11. **[INFO]** 24 Pydantic models pentru request validation
12. **[INFO]** SSE streaming implementat in stream.py
13. **[INFO]** Lifespan cu DB pool init structurat
14. **[INFO]** API layer nu importa direct din agent/ - separare clara
15. **[INFO]** No CORS - OK daca same-origin, problema daca UI separat

---

## Section 17: Observatii colaterale

- **[FOR-TASK-7 INFRASTRUCTURE]** executor.py si backup.py contin SSH operations direct in API layer. Ar trebui mutat in dedicated executor module pentru separare mai clara.

- **[FOR-TASK-8 SKILLS]** chat.py contine `_detect_and_load_skills()` si `_grok_search_for_skill()` - skill loading logic este in API layer, ar putea fi mutat in skills module.

- **[FOR-TASK-9 UI]** stream.py implementeaza SSE pentru `/stream/activity` - cuplaj cu UI pentru real-time updates.

- **[FOR-TASK-99 SYNTHESIS]** Pattern cross-cutting: chat.py combina prea multe responsabilitati (LLM, tools, DB, skills, compression). Aceasta problema apare si in rapoartele 02, 03, 05.

- **[FOR-TASK-7 INFRASTRUCTURE]** KNOWN_HOSTS in executor.py (L23-27 probabil) - hardcoded IPs pentru SSH, confirmat din task 02.

---

## Section 18: Recomandari prioritare

1. **Add minimal auth middleware** - API key in header sau JWT token inainte de expunere externa. Implementare in main.py middleware.

2. **Decompose chat.py** prin extragere module:
   - `chat_send.py` - send_message logic
   - `chat_tools.py` - _execute_tool logic
   - `chat_skills.py` - skill detection/loading
   - `chat_compress.py` - compression logic

3. **Refactor send_message()** in 4-5 functii mai mici:
   - `_build_messages()` - prepare message history
   - `_call_llm()` - Anthropic API call
   - `_dispatch_tool()` - tool execution
   - `_save_response()` - DB persistence

4. **Single Anthropic client instance** - instantiere la nivel de modul sau dependency injection in loc de 3 instantieri separate.

5. **Move SSH operations** din api/executor.py si api/backup.py intr-un dedicated executor module sub tools/ sau infrastructure/.

---

## Section 19: Metadata

- **Timp rulare:** ~5 secunde
- **Comanda:** `docker exec $CONT python3 /home/darkangel/.argos/argos-core/tools/audit/scripts/06_api_endpoints.py`
- **Linii output:** ~280
- **Erori:** 0
- **SQL adhoc executat:** 0
- **Fisiere citite manual:** 0
