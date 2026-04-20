# AUDIT REPORT 02 - Code Inventory + Anti-patterns

**Data:** 2026-04-14
**Scope:** agent/, api/, llm/, tools/
**Status:** READ-ONLY audit

---

## Section 1: Rezumat executiv

Codebase-ul ARGOS contine **28 fisiere Python** cu un total de **8687 linii de cod**. Principalele probleme identificate: (1) functia `run_agent_loop()` cu 747 linii este CRITICAL pentru refactorizare, (2) `api/chat.py` are 1550 linii si 8 bare except patterns, (3) 27 instante de exception swallowing distribuite in 9 fisiere. Codul parseaza corect si nu are SQL injection patterns detectabile, dar exception handling si logging discipline necesita atentie.

---

## Section 2: Inventory stats

| Metric | Value |
|--------|-------|
| Total Python files (in scope) | 28 |
| Total lines | 8687 |
| Total bytes | 343338 |

**Per directory:**

| Directory | Files | Lines |
|-----------|-------|-------|
| agent | 7 | 3110 |
| api | 18 | 5282 |
| llm | 2 | 147 |
| tools | 1 | 148 |

---

## Section 3: Hotspots (cele mai mari fisiere)

| # | File | Lines | Bytes | Severity | Observatie |
|---|------|-------|-------|----------|------------|
| 1 | api/chat.py | 1550 | 68773 | **[HIGH]** | Fisier principal chat, candidate urgent pentru refactor |
| 2 | agent/loop.py | 1251 | 50557 | **[HIGH]** | Core agent loop, contine run_agent_loop 747 lines - CRITICAL |
| 3 | agent/prompts.py | 849 | 37083 | **[MEDIUM]** | Prompt building, mare dar specializat |
| 4 | api/iso_builder.py | 630 | 25230 | **[MEDIUM]** | ISO generation, complex dar self-contained |
| 5 | api/main.py | 432 | 17347 | **[LOW]** | FastAPI entry point, acceptabil |

---

## Section 4: Dead code suspects

No stub files detected **[INFO]**

Script-ul nu a gasit fisiere sub 20 linii care ar indica cod mort sau stubs abandonate.

---

## Section 5: Technical debt markers

**Total TODOs/FIXMEs found:** 1

| File | Line | Content | Severity |
|------|------|---------|----------|
| api/dashboard.py | L82 | `# TODO Pas 3 SSE: union pe sessions/jobs/fleet/chats cu timestamp.` | **[MEDIUM]** - amanare reala pentru feature SSE |

---

## Section 6: Exception handling anti-patterns

**Total count:** 27

**Per-file grouping (descrescator):**

| File | Count | Severity |
|------|-------|----------|
| api/chat.py | 8 | **[HIGH]** |
| api/executor.py | 6 | **[MEDIUM]** |
| api/vms.py | 4 | **[LOW]** |
| api/backup.py | 4 | **[LOW]** |
| agent/loop.py | 1 | **[LOW]** |
| api/iso_builder.py | 1 | **[LOW]** |
| api/nanite.py | 1 | **[LOW]** |
| api/jobs.py | 1 | **[LOW]** |
| api/code_runner.py | 1 | **[LOW]** |

**Top 3 fisiere cu problema:**
1. **api/chat.py** - 8 instante (4x `except Exception: pass`, 4x bare except)
2. **api/executor.py** - 6 instante (toate bare except)
3. **api/vms.py** - 4 instante (toate `except Exception: pass`)

**Detalii:**
```
api/chat.py L220: except Exception: pass
api/chat.py L335: bare except:
api/chat.py L369: bare except:
api/chat.py L479: bare except:
api/chat.py L728: except Exception: pass
api/chat.py L751: except Exception: pass
api/chat.py L816: bare except:
api/chat.py L839: except Exception: pass
api/executor.py L70, L202, L224, L229, L234, L239: bare except:
api/backup.py L59, L132, L173, L200: bare except:
api/vms.py L47, L77, L119, L134: except Exception: pass
```

---

## Section 7: Logging discipline

**Total bad prints:** 44 **[MEDIUM]**

**Per-file grouping top 5:**

| File | Count |
|------|-------|
| tools/scan_chat_structure.py | 20 |
| agent/loop.py | 9 |
| agent/prompts.py | 5 |
| api/main.py | 4 |
| llm/providers.py | 3 |

**Impact:** Skill argos-output-patterns (id 91) cere marker `[CATEG NNN]` pe toate print-urile. Violatii = logging fragil, greu de filtrat, debug slower.

**Nota:** `tools/scan_chat_structure.py` este tool de audit, nu production code - acceptable. Problematic sunt `agent/loop.py` si `agent/prompts.py` care sunt core.

---

## Section 8: Hardcoded values

**Total IPs hardcoded:** 19 in 5 fisiere

| File | Lines | IPs | Severity |
|------|-------|-----|----------|
| api/executor.py | L13-23 | 11.11.11.111, 11.11.11.98, 11.11.11.201, 11.11.11.113, 11.11.11.11 | **[LOW]** - machine mapping expected |
| api/code_runner.py | L22, L35, L85-87 | 11.11.11.111, 127.0.0.1, 11.11.11.11, 11.11.11.201 | **[LOW]** - machine mapping expected |
| agent/loop.py | L99 | 11.11.11.111 | **[MEDIUM]** - DB_HOST fallback, ar trebui doar env var |
| api/main.py | L158-266 | 11.11.11.111, 172.17.0.1 | **[MEDIUM]** - DB connection fallbacks |
| api/backup.py | L159, L187 | 11.11.11.111 | **[HIGH]** - SSH connection hardcoded fara env var |

---

## Section 9: Long functions

**Total functions >= 80 lines:** 18

| Function | File | Lines | Severity |
|----------|------|-------|----------|
| run_agent_loop() | agent/loop.py L504 | 747 | **[CRITICAL]** |
| send_message() | api/chat.py L250 | 336 | **[HIGH]** |
| _execute_tool() | api/chat.py L731 | 271 | **[HIGH]** |
| stream_activity() | api/stream.py L22 | 204 | **[HIGH]** |
| event_generator() | api/stream.py L36 | 180 | **[MEDIUM]** |
| build_iteration_message() | agent/prompts.py L690 | 159 | **[MEDIUM]** |
| build_iso() | api/iso_builder.py L260 | 153 | **[MEDIUM]** |
| check_session_autonomy() | agent/autonomy.py L135 | 141 | **[MEDIUM]** |
| _generate_nix_config() | api/iso_builder.py L128 | 129 | **[MEDIUM]** |
| test_iso() | api/iso_builder.py L416 | 122 | **[MEDIUM]** |
| list_fleet() | api/fleet.py L14 | 117 | **[MEDIUM]** |
| dashboard_summary() | api/dashboard.py L12 | 113 | **[MEDIUM]** |
| run_verification_chain() | agent/verification.py L175 | 103 | **[MEDIUM]** |
| call_claude() | llm/providers.py L48 | 99 | **[LOW]** |
| lifespan() | api/main.py L153 | 97 | **[LOW]** |
| compress_conversation() | api/compress.py L40 | 88 | **[LOW]** |
| _select_dynamic_skills() | agent/prompts.py L276 | 86 | **[LOW]** |
| _generate_skill_from_web_impl() | api/chat.py L1467 | 83 | **[LOW]** |

---

## Section 10: Security quick check

No SQL injection patterns detected via f-string scan **[INFO]**

---

## Section 11: Global state

**Total global statements:** 5

| File | Line | Statement | Severity |
|------|------|-----------|----------|
| api/main.py | L98 | `global pool` | **[LOW]** - acceptable in lifespan |
| api/main.py | L154 | `global pool, system_prompt` | **[LOW]** - acceptable in lifespan |
| api/main.py | L255 | `global pool` | **[LOW]** - acceptable pattern |
| agent/tools.py | L42 | `global _exec_ssh_by_name, _known_hosts` | **[MEDIUM]** - poate fi smell, de investigat |
| api/debug.py | L20 | `global _pool` | **[LOW]** - debug module, acceptable |

---

## Section 12: Syntax check

All files parse cleanly **[INFO]**

---

## Section 13: Documentation

**Files without module docstring:** 7 **[INFO]**

- api/chat.py
- api/main.py
- api/executor.py
- api/jobs.py
- api/compress.py
- api/vms.py
- api/local_executor.py

Nice-to-have, nu critical.

---

## Section 14: Top 10 findings cross-cutting

1. **[CRITICAL]** agent/loop.py `run_agent_loop()` = 747 lines - decompose in phases
2. **[HIGH]** api/chat.py = 1550 lines total - refactor needed
3. **[HIGH]** api/chat.py `send_message()` = 336 lines - break into smaller functions
4. **[HIGH]** api/chat.py `_execute_tool()` = 271 lines - decompose by tool type
5. **[HIGH]** api/chat.py: 8 bare except / except Exception: pass - add proper error handling
6. **[HIGH]** api/stream.py `stream_activity()` = 204 lines - refactor
7. **[HIGH]** api/backup.py L159,L187: SSH IP hardcoded fara env var - security concern
8. **[MEDIUM]** api/executor.py: 6 bare except patterns - swallows errors silently
9. **[MEDIUM]** agent/loop.py L99: DB_HOST fallback hardcoded - should use env only
10. **[MEDIUM]** api/main.py L158-266: multiple DB fallback IPs hardcoded

---

## Section 15: Observatii colaterale pentru task-uri urmatoare

- **[FOR-TASK-3 SECURITY]** api/backup.py L159,L187 are SSH connections cu `client_keys` - verifica permisiuni si daca keys sunt in repo
- **[FOR-TASK-3 SECURITY]** api/executor.py KNOWN_HOSTS dict contine toate IP-urile infrastructurii - verifica daca e expus
- **[FOR-TASK-4 DATABASE]** agent/loop.py L99 si api/main.py au multiple DB connection patterns - unifica intr-un singur modul
- **[FOR-TASK-5 AGENT LOOP]** run_agent_loop() 747 linii - necesita analiza profunda a structurii si flow-ului
- **[FOR-TASK-5 AGENT LOOP]** agent/tools.py L42 foloseste global pentru SSH - investigheaza daca e necesar sau poate fi refactorizat
- **[FOR-TASK-6 API]** api/chat.py send_message() 336 linii + _execute_tool() 271 linii - candidate pentru decomposition

---

## Section 16: Metadata

- **Timp rulare:** ~2 minute
- **Comanda rulata:** `docker exec $CONT python3 /home/darkangel/.argos/argos-core/tools/audit/scripts/02_code_inventory.py`
- **Linii output script:** ~182
- **Erori intampinate:** None

---

*Report generated by ARGOS Audit Task 02*
