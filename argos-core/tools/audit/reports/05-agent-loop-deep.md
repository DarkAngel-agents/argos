# AUDIT REPORT 05 - Agent Loop Deep Dive

**Generated:** 2026-04-14 20:40 UTC
**Target:** /home/darkangel/.argos/argos-core/agent/
**Auditor:** Claude Code (read-only audit)

---

## Section 1: Rezumat executiv

Agent loop-ul ARGOS contine **6 fisiere Python** cu un total de ~3110 linii. Fisierul principal `loop.py` are **1251 linii** si **14 functii**, dintre care `run_agent_loop()` cu **748 linii** este critica si necesita decompose urgent. Complexitatea este ridicata: **nested_depth_max = 9** si **56 if statements**. Failure rate din agent_sessions este **40%** (4/10 failed), cu majoritatea fail-urilor aparand in primele 2-4 iteratii. Design-ul are toate phase-urile esentiale prezente dar main function-ul este monolitic.

---

## Section 2: Files overview

| File | Lines | Size |
|------|-------|------|
| loop.py | 1251 | 50,557 bytes |
| prompts.py | 849 | 37,083 bytes |
| verification.py | 340 | 11,998 bytes |
| autonomy.py | 276 | 9,796 bytes |
| evidence.py | 254 | 7,006 bytes |
| tools.py | 140 | 5,411 bytes |
| **TOTAL** | **3110** | **121,851 bytes** |

---

## Section 3: loop.py structure

- **Total lines:** 1251
- **Functions defined:** 14

**All functions sorted by length (descending):**

| Lines | Location | Function | Severity |
|-------|----------|----------|----------|
| 748 | L504-1251 | `async run_agent_loop(session_id, clarification_answer)` | **[CRITICAL]** |
| 69 | L273-341 | `async _rebuild_messages_from_evidence(pool, session)` | |
| 68 | L429-496 | `async _load_context_for_request(pool, payload)` | |
| 40 | L226-265 | `async _check_pending_clarification(pool, session_id)` | |
| 32 | L163-194 | `async _mark_terminal(pool, session_id, phase...)` | |
| 30 | L630-659 | `_verif_to_dict(v)` | |
| 28 | L349-376 | `_extract_tool_use(content_blocks)` | |
| 27 | L197-223 | `async _pause_for_clarification(pool, session_id, question...)` | |
| 27 | L395-421 | `_content_blocks_to_serializable(content_blocks)` | |
| 22 | L109-130 | `async _load_session(pool, session_id)` | |
| 16 | L145-160 | `async _increment_iteration(pool, session_id)` | |
| 14 | L379-392 | `_detect_signal(command)` | |
| 13 | L94-106 | `async _build_pool()` | |
| 10 | L133-142 | `async _set_session_phase(pool, session_id, phase)` | |

**[CRITICAL]** `run_agent_loop()` cu 748 linii este de 3.7x mai mare decat threshold-ul de 200 linii. Necesita decompose urgent in phase handlers separati.

---

## Section 4: loop.py complexity

| Indicator | Count |
|-----------|-------|
| if_statements | 56 |
| for_loops | 8 |
| while_loops | 1 |
| try_blocks | 10 |
| await_calls | 77 |
| raise_statements | 0 |
| return_statements | 43 |
| continue_statements | 5 |
| break_statements | 2 |
| **nested_depth_max** | **9** |

**Overall Severity: [CRITICAL]**
- nested_depth_max = 9 depaseste threshold de 8
- 56 if_statements in range MEDIUM (50-100) dar combinat cu nesting-ul devine problematic

**Observatii:**
- 10 try_blocks intr-un singur fisier nu e excesiv dar combined cu 77 await_calls sugereaza error handling dispersat
- 0 raise_statements - erorile sunt gestionate prin phase transitions nu exceptions
- 43 return_statements in 14 functii = ~3 returns/functie (acceptabil)
- nested_depth 9 in run_agent_loop() face codul greu de urmarit

---

## Section 5: Phase transitions

**Phase keywords found:**

| Phase | Occurrences |
|-------|-------------|
| failed | 27 |
| executing | 21 |
| verifying | 5 |
| paused | 4 |
| complete | 3 |
| active | 2 |
| fixing | 2 |
| planning | 1 |

**Phase change statements (first 15):**

| Line | Statement |
|------|-----------|
| L218 | phase="executing" |
| L554 | phase="executing" |
| L584 | pool, session, phase="executing" |
| L592 | phase="executing" |
| L627 | current_phase = "executing" |
| L730 | phase="executing" |
| L748 | phase="executing" |
| L771 | phase="executing" |
| L867 | phase="executing" |
| L894 | phase="executing" |
| L940 | phase="executing" |
| L966 | phase="executing" |
| L1042 | phase="executing" |
| L1067 | current_phase = "verifying" |
| L1077 | phase="verifying", iteration=iteration |

**[INFO]** Toate phase-urile esentiale sunt prezente: executing, verifying, fixing, complete, failed, paused.

**Observatie:** "executing" apare de 21 ori vs "verifying" doar 5 ori - flow-ul este heavily execution-centric.

---

## Section 6: Critical branches

### retry
- **Occurrences:** 23
- **[INFO]** Present and implemented
- Retry logic la L1134-1151 cu max 2 retries per verification fail

### escalate
- **Occurrences:** 2
- **[INFO]** Present
- L1123: elif on_fail == "escalate" -> user review

### abort
- **Occurrences:** 4
- **[INFO]** Present
- L1113: if on_fail == "abort" -> terminal state

### fix_loop
- **Occurrences:** 1
- **[INFO]** Present
- L1207: "reason": "fix_loop_exhausted" - skill 96 implemented

### iteration
- **Occurrences:** 7
- **[INFO]** Present
- L677: if iteration >= max_iterations -> terminal
- max_iterations default = 50 (L616)

**Summary:** Toate branch-urile critice sunt prezente. Exit paths exista pentru abort, max_iterations, fix_loop_exhausted.

---

## Section 7: DB writes

- **Total writes in loop.py:** 0
- **Distribution by operation:** N/A

**[INFO]** loop.py nu face DB writes direct. Writes sunt delegate catre evidence.py si helper functions. Aceasta este o separare buna a responsabilitatilor.

---

## Section 8: Subprocess / SSH calls

- **Total in loop.py:** 0

**[INFO]** loop.py nu face subprocess/SSH direct. Calls sunt delegate catre tools.py via `tools.exec_tool()`. Design corect.

---

## Section 9: verification.py analysis

- **Total lines:** 340
- **Functions:** 8

| Lines | Function |
|-------|----------|
| 104 | `async run_verification_chain()` |
| 35 | `async check_safety_guards()` |
| 14 | `_check_exit_code()` |
| 12 | `_compute_effective_on_fail()` |
| 9 | `_check_grep()` |
| 9 | `_check_grep_not()` |
| 3 | `_check_deferred()` |
| 2 | `rank()` |

**Pattern matching operators:**

| Line | Usage |
|------|-------|
| L9 | `~*` POSIX ERE regex (documentation) |
| L140 | `~*` case-insensitive matching |
| L153 | `$1 ~* pattern` (SQL query) |
| L207 | `$1 ~* pattern` (SQL query) |

**[INFO]** verification.py foloseste `~*` (PostgreSQL POSIX ERE regex) corect, NU `ILIKE`. Bug-ul vechi din S4 este rezolvat.

---

## Section 10: evidence.py analysis

- **Total lines:** 254
- **Functions:** 7

| Lines | Function |
|-------|----------|
| 36 | `async _append_to_evidence_key()` |
| 36 | `async append_llm_call()` |
| 34 | `async append_command()` |
| 31 | `async append_verification()` |
| 28 | `async append_error()` |
| 28 | `async append_decision()` |
| 26 | `async update_session_totals()` |

**[INFO]** Toate functiile < 80 linii. Structura modulara si clara.

---

## Section 11: autonomy.py analysis

- **Total lines:** 276
- **Functions:** 5

| Lines | Function |
|-------|----------|
| 142 | `async check_session_autonomy()` |
| 23 | `_is_whitelisted_command()` |
| 13 | `__init__()` |
| 9 | `to_dict()` |
| 3 | `__repr__()` |

**[MEDIUM]** `check_session_autonomy()` cu 142 linii este aproape de threshold-ul de 150. Functia gestioneaza autonomy levels, whitelist checks, si authorization flow - complexitate justificata dar ar beneficia de refactoring.

---

## Section 12: tools.py analysis

- **Total lines:** 140
- **Functions:** 3

| Lines | Function |
|-------|----------|
| 72 | `async exec_tool()` |
| 19 | `_lazy_import_executor()` |
| 10 | `list_known_machines()` |

**Tool dispatch patterns:** Nu s-au gasit patterns explicite (TOOLS dict / register_tool).

**[INFO]** tools.py este minimal si focused. exec_tool() face dispatch catre executor module. Nu exista if/elif chain pentru tools - dispatch-ul este in alta parte (probabil in loop.py sau executor).

---

## Section 13: prompts.py top functions

- **Total lines:** 849
- **Functions:** 15

| Lines | Function | Severity |
|-------|----------|----------|
| 160 | `build_iteration_message()` | **[LOW]** |
| 87 | `async _select_dynamic_skills()` | |
| 69 | `async build_session_context()` | |
| 57 | `async _load_fixed_skills()` | |
| 52 | `_format_verification_section()` | |
| 46 | `_score_skill()` | |
| 43 | `_enforce_budget()` | |
| 39 | `_build_execute_command_tool()` | |
| 17 | `_extract_keywords()` | |
| 15 | `_truncate_middle()` | |

**[LOW]** `build_iteration_message()` cu 160 linii este sub threshold-ul de 200 pentru prompt building. Acceptabil dat fiind complexitatea prompt construction.

---

## Section 14: Agent sessions failure pattern

### Distribution by phase

| Phase | Count |
|-------|-------|
| complete | 6 |
| failed | 4 |

### Failure rate calculation

- **Total sessions:** 10
- **Failed sessions:** 4
- **Failure rate:** **40%**

**[MEDIUM]** Failure rate 40% este in range 20-50%.

### Failed sessions iteration stats

| Metric | Value |
|--------|-------|
| Count | 4 |
| Min iterations | 0 |
| Max iterations | 4 |
| Avg iterations | 2 |

### Last 10 sessions detail

| ID | Phase | Iter | Tokens | Duration | Provider |
|----|-------|------|--------|----------|----------|
| 10 | complete | 4/8 | 34,850 | 519s | claude |
| 9 | **failed** | 0/3 | 6,529 | 3s | claude |
| 8 | **failed** | 4/6 | 36,351 | 19s | claude |
| 7 | **failed** | 2/10 | 21,683 | 13s | claude |
| 6 | **failed** | 2/8 | 21,032 | 11s | claude |
| 5 | complete | 1/5 | 13,385 | 7s | claude |
| 4 | complete | 2/3 | 20,167 | 11s | claude |
| 3 | complete | 0/5 | 13,850 | 8s | claude |
| 2 | complete | 1/5 | 14,033 | 6s | claude |
| 1 | complete | 1/5 | 13,243 | 6s | claude |

**Analiza:**
- **LLM provider:** 100% claude (nu grok, nu local)
- **Pattern:** Failed sessions 6-9 sunt consecutive, followed by success pe 10
- **Session 9:** Failed la iteration 0 (3 secunde) - probabil eroare imediata
- **Sessions 6-8:** Failed la iteration 2-4, nu au atins max_iterations - ceva a cauzat abort/fail
- **Observation:** Sessions 1-5 (older) au 80% success rate, sessions 6-10 (recent) au 40% success - potential regression

---

## Section 15: Evidence growth

| ID | Phase | Iter | Evidence Size |
|----|-------|------|---------------|
| 10 | complete | 4 | 3.6 KB |
| 9 | failed | 0 | 737 B |
| 8 | failed | 4 | 3.4 KB |
| 7 | failed | 2 | 2.9 KB |
| 6 | failed | 2 | 2.7 KB |
| 5 | complete | 1 | 1.4 KB |
| 4 | complete | 2 | 1.7 KB |
| 3 | complete | 0 | 1.5 KB |
| 2 | complete | 1 | 2.2 KB |
| 1 | complete | 1 | 1.0 KB |

**[INFO]** Toate evidence sizes < 5 KB. Nu exista runaway accumulation. Evidence growth este proportional cu iteration count (~0.8-1 KB per iteration).

---

## Section 16: Verification rules referenced

- **Total rules in DB:** 25
- **verification.py references:** 47 linii relevante

**Key references:**
- L148-152: Query `agent_verification_rules` pentru safety guards (priority=1, rule_type='custom')
- L202-208: Query rules pentru verification chain (priority > 1)
- L227-245: Dispatch per rule_type (exit_code, grep, grep_not, file_exists, http_200)
- L329-340: `_compute_effective_on_fail()` cu ON_FAIL_PRECEDENCE

**[INFO]** verification.py citeste rules din DB si face dispatch corect. Nu are hardcoded logic - rules sunt dinamice.

---

## Section 17: Top 15 findings cross-cutting

1. **[CRITICAL]** agent/loop.py `run_agent_loop()` = 748 lines - decompose urgent in phase handlers
2. **[CRITICAL]** loop.py nested_depth_max = 9 - depaseste threshold 8, reduce nesting
3. **[MEDIUM]** Failure rate 40% (4/10 sessions) - investigate recent regression (sessions 6-9)
4. **[MEDIUM]** autonomy.py `check_session_autonomy()` = 142 lines - aproape de threshold 150
5. **[MEDIUM]** Session 9 failed la iteration 0 in 3s - eroare imediata, needs investigation
6. **[LOW]** prompts.py `build_iteration_message()` = 160 lines - acceptabil dar monitorizare
7. **[INFO]** verification.py foloseste ~* corect (nu ILIKE) - bug S4 rezolvat
8. **[INFO]** All essential phases present: executing, verifying, fixing, complete, failed
9. **[INFO]** Evidence sizes < 5KB - no runaway accumulation
10. **[INFO]** DB writes delegated to evidence.py - good separation
11. **[INFO]** Subprocess calls delegated to tools.py - good separation
12. **[INFO]** All critical branches present: retry, escalate, abort, fix_loop
13. **[INFO]** fix_loop counter cap implemented (skill 96 applied)
14. **[INFO]** 100% sessions use claude provider
15. **[INFO]** verification rules loaded from DB, not hardcoded

---

## Section 18: Observatii colaterale

- **[FOR-TASK-7 INFRASTRUCTURE]** Failure pattern pe sessions 6-9 ar putea fi corelat cu hermes heartbeat absent (din task 04). Daca agent sessions rulau pe hermes sau depindeau de el, absenta nodului poate fi cauza.

- **[FOR-TASK-6 API]** Sessions 6-9 failed consecutive sugereaza un posibil bug introdus in API layer. Verificare necesara in chat.py pentru call site-uri catre agent loop.

- **[FOR-TASK-8 SKILLS]** prompts.py face skill loading dinamic via `_select_dynamic_skills()` si `_load_fixed_skills()`. Nu sunt hardcoded skill references vizibile in output.

- **[FOR-TASK-9 UI]** Nu s-au gasit referinte la componente UI in agent/ directory.

- **[FOR-TASK-6 API]** Session 9 failed in 3 secunde la iteration 0 - probabil eroare in API call sau payload validation, nu in agent logic.

---

## Section 19: Recomandari prioritare

1. **Decompose `run_agent_loop()`** in 4-5 phase handlers separati: `_handle_executing()`, `_handle_verifying()`, `_handle_fixing()`, `_handle_terminal()`. Reduce din 748 linii la ~150/handler.

2. **Investigate session 9 failure** - failed la iteration 0 in 3s sugereaza eroare imediata (payload issue, DB connection, sau exception la start).

3. **Reduce nesting depth** in run_agent_loop() - extract conditii complexe in helper functions pentru a aduce nested_depth sub 6.

4. **Correlate failure pattern cu hermes absence** - verifica daca sessions 6-9 aveau dependente pe hermes sau au fost afectate de infrastructure issues din perioada 04-08 aprilie.

5. **Add regression tests** pentru agent loop - failure rate 40% pe recent sessions vs 20% pe older sessions sugereaza potential regression.

---

## Section 20: Metadata

- **Timp rulare:** ~4 secunde
- **Comanda:** `docker exec $CONT python3 /home/darkangel/.argos/argos-core/tools/audit/scripts/05_agent_loop_deep.py`
- **Linii output:** ~250
- **Erori:** 0
- **SQL adhoc executat:** 0
- **Fisiere citite manual:** 0 (conform protocol)
