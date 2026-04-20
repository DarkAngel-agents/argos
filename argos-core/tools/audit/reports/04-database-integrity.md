# AUDIT REPORT 04 - Database Integrity

**Generated:** 2026-04-14 20:38 UTC
**Target:** claudedb @ argos-db container
**Auditor:** Claude Code (read-only audit)

---

## Section 1: Rezumat executiv

Database claudedb contine **67 tabele** cu un total de **5425 rows** si dimensiune de **6.5 MB**. Cele mai mari tabele dupa row count: ha_entities (1617), debug_logs (1502), knowledge_base (666), reasoning_log (494). Problemele principale identificate: **18 orphan parent_paths in skills_tree** (tree integrity broken), **hermes heartbeat absent 6 zile** (nod potentially offline), si **messages/conversations fara indexuri pe foreign keys**.

---

## Section 2: Schema overview

| Table | Rows | Size | Severity |
|-------|------|------|----------|
| ha_entities | 1617 | 472.0 KB | [INFO] |
| debug_logs | 1502 | 576.0 KB | [INFO] |
| knowledge_base | 666 | 544.0 KB | [INFO] |
| reasoning_log | 494 | 216.0 KB | [INFO] |
| command_scores | 343 | 296.0 KB | [INFO] |
| skills_tree | 110 | 728.0 KB | [INFO] |
| messages | 106 | 168.0 KB | [INFO] |
| heartbeat_log | 60 | 88.0 KB | [INFO] |
| file_index | 48 | 192.0 KB | [INFO] |
| ha_automations | 44 | 48.0 KB | [INFO] |
| file_versions | 43 | 424.0 KB | [INFO] |
| error_codes | 40 | 96.0 KB | [INFO] |
| ha_scenes | 35 | 48.0 KB | [INFO] |
| settings | 34 | 64.0 KB | [INFO] |
| agent_verification_rules | 25 | 80.0 KB | [INFO] |

**Total:** 67 tables, 5425 rows, 6.5 MB

**[INFO]** Toate tabelele au row counts normale, niciuna nu depaseste 100k rows.

---

## Section 3: skills_tree integrity

### 3.1 General stats
- Total skills: **110**
- Verified: **110** (100%)
- Emergency: **10**

### 3.2 Duplicate paths / names
- Duplicate paths: **0** [INFO]
- Duplicate names: **0** [INFO]

### 3.3 Content anomalies

**Skills cu content < 300 chars: 11**
| ID | Length | Path |
|----|--------|------|
| 44 | 30 | debian/debian-haproxy-setup |
| 85 | 121 | network/synology-dsm-basics |
| 84 | 171 | network/mikrotik-routeros-basics |
| 41 | 191 | nixos/nixos-haproxy-configuration |
| 46 | 211 | debian/debian-postgresql-17-native |
| 70 | 224 | ssh/rsync-between-nodes |
| 39 | 241 | nixos/nixos-nfs-export |
| 19 | 260 | docker-swarm/docker-swarm-force-restart |
| 79 | 262 | skill-system/skill-import-system |
| 65 | 283 | home-assistant/home-assistant-ip-ban-reset |
| 20 | 284 | docker-swarm/docker-swarm-promote/demote-nodes |

**[MEDIUM]** 11 stubs detected (> 10 threshold)

**Skills cu content > 15000 chars: 1**
- id=90 len=22898 argos-core/argos-self-knowledge

**[INFO]** Single large skill, acceptable.

**Skills cu NULL/empty content: 0** [INFO]

### 3.4 Stale skills

**Skills never updated (updated_at IS NULL): 12**
| ID | Path |
|----|------|
| 93 | argos-meta/argos-skill-creation-protocol |
| 94 | argos-agent/verification-chain-design |
| 96 | argos-agent/fix-loop-counter-cap |
| 97 | postgresql/pattern-matching-operator-selection |
| 98 | argos-agent/pattern-a-prompt-caching |
| 99 | argos-core/text-design-before-code-protocol |
| 101 | argos-core/fastapi-router-modular-add |
| 102 | argos-core/idempotent-db-write-scripts |
| 105 | argos-core/alpine-htmx-no-build-ui |
| 107 | argos-core/sse-fastapi-polling-generator |
| 108 | argos-core/sse-eventsource-per-component-cleanup |
| 110 | argos-core/alpine-fragment-injection-replacenode |

**[MEDIUM]** 12 skills never updated (< 20 threshold dar aproape)

### 3.5 Unverified
**Unverified skills: 0** [INFO]

### 3.6 Distribution by parent_path

| Parent Path | Count |
|-------------|-------|
| argos-core | 22 |
| postgresql | 12 |
| argos-deploy | 11 |
| docker-swarm | 10 |
| home-assistant | 8 |
| nixos | 8 |
| argos-agent | 5 |
| argos-reasoning | 5 |
| github | 5 |
| skill-system | 4 |
| ssh | 4 |
| debian | 4 |
| file-ops | 3 |
| esp32-ble | 3 |
| network | 3 |

### 3.7 Orphan parent_paths

**[HIGH]** 18 orphan parent_paths detected (tree integrity broken):
- argos-agent
- argos-core
- argos-deploy
- argos-meta
- argos-reasoning
- debian
- docker-swarm
- esp32-ble
- file-ops
- github
- (+ 8 more)

Aceste parent_path-uri nu au un skill parinte in skills_tree. Fie sunt root categories (acceptabil) fie sunt truly orphan.

---

## Section 4: settings table

### 4.1 General
- Total entries: **34**
- Columns: key, value, updated_at, value_type, description, updated_by, auto_update, hint_query

### 4.2 Duplicates
**Duplicate keys: 0** [INFO]

### 4.3 NULL values
**Settings cu NULL/empty value: 0** [INFO]

### 4.4 Keys list

| Key | Value |
|-----|-------|
| api_mode | cloud |
| argos_autonomy_system | scout_engineer |
| argos_beasty_active | true |
| argos_bind_mount_deploy | true |
| argos_code_signing_active | false |
| argos_db_access_via | haproxy:5433 |
| argos_db_primary | beasty |
| argos_db_standby_active | false |
| argos_file_indexing_active | true |
| argos_heartbeat_daemon_beasty | true |
| argos_heartbeat_daemon_hermes | true |
| argos_heartbeat_unit_beasty | argos-heartbeat.service |
| argos_heartbeat_unit_hermes | argos-heartbeat.service |
| argos_hermes_active | true |
| argos_notes_handler_active | true |
| argos_notes_handler_version | 1 |
| argos_prompt_source | db |
| argos_reasoning_source | db |
| argos_skills_source | db |
| argos_swarm_leader | hermes |
| argos_swarm_mode | true |
| argos_swarm_replicas | 2 |
| argos_version | v5-dev |
| autonomy_level | 1 |
| claude_enabled | true |
| grok_enabled | false |
| last_morning_report | 2026-04-14 |
| local_enabled | true |
| reasoning_mode | full |
| skills_daily_limit | 5 |
| skills_generated_date | 2026-04-13 |
| skills_generated_today | 0 |
| unifi_cristin_token | 2rZ4...fuA9 (masked) |
| unifi_home_token | sZua...-3e8 (masked) |

**[INFO]** Sensitive values properly masked by script. No credentials exposed.

---

## Section 5: Agent sessions

- **Total sessions:** 10
- **Schema columns:** id, title, goal, phase, iteration, max_iterations, active, parent_session_id, started_at, last_active_at, completed_at, current_task, evidence, autonomy_level, llm_provider, total_tokens, total_cost_eur, created_by

**Recent 5 sessions:**
| ID | Phase | Iterations | Title (truncated) |
|----|-------|------------|-------------------|
| 10 | complete | 4/8 | CLI session: create empty... |
| 9 | failed | 0/3 | CLI session: execute command... |
| 8 | failed | 4/6 | CLI session: run echo hello... |
| 7 | failed | 2/10 | CLI session: run command... |
| 6 | failed | 2/8 | CLI session: run cat /tmp/... |

**[MEDIUM]** 4 din 5 recent sessions au failed. Pattern suspect pentru agent loop debugging.

---

## Section 6: Agent verification rules

- **Total rules:** 25
- **Active rules:** 25
- **Inactive rules:** 0

**By rule_type:**
| Type | Count |
|------|-------|
| exit_code | 16 |
| grep_not | 4 |
| grep | 3 |
| custom | 2 |

**By on_fail action:**
| Action | Count |
|--------|-------|
| fix | 11 |
| retry | 9 |
| escalate | 3 |
| abort | 2 |

**[INFO]** All essential actions present (fix, retry, escalate, abort).

**Rules with NULL/empty pattern: 0** [INFO]

---

## Section 7: Messages + conversations

| Metric | Value |
|--------|-------|
| Total messages | 106 |
| Total conversations | 4 |
| Avg messages per conv | 26.5 |
| Orphan messages | 0 |
| Pending messages | 0 |
| Messages last 24h | 6 |
| Messages last 7d | 6 |
| Empty conversations | 0 |

**Top conversations by message count:**
| Conv ID | Messages |
|---------|----------|
| 30 | 92 |
| 1 | 6 |
| 31 | 6 |
| 21 | 2 |

**[INFO]** No orphan messages, no pending backlog.
**[INFO]** Conversation 30 cu 92 messages e sub threshold de 500.

---

## Section 8: Heartbeat freshness

- **Total entries:** 60
- **Last 5 min:** 30
- **Last 1h:** 30
- **Last 24h:** 30
- **Latest entry:** 2026-04-14 20:37:44

**By node:**
| Node | Count | Last Seen |
|------|-------|-----------|
| beasty | 30 | 2026-04-14 20:37:44 |
| hermes | 30 | 2026-04-08 21:35:24 |

**[INFO]** beasty heartbeat healthy (entries in last 5 min).
**[HIGH]** hermes heartbeat ultima data vazut acum 6 zile! Nodul poate fi offline sau daemon-ul stopped.

---

## Section 9: Index coverage

| Table | Index Count | Indexes |
|-------|-------------|---------|
| skills_tree | 5 | pkey, path (unique), parent_path, path, tags |
| settings | 1 | pkey only |
| messages | 1 | pkey only |
| conversations | 1 | pkey only |
| agent_sessions | 5 | pkey, active_phase, parent, last_active, evidence_gin |
| agent_verification_rules | 4 | pkey, active_prio, type, unique pattern |
| reasoning_log | 2 | pkey, conv_ts |
| heartbeat_log | 2 | pkey, node_ts |

**[MEDIUM]** messages table cu doar primary key index. Lipsa index pe conversation_id va cauza slow queries pe JOIN-uri.
**[MEDIUM]** conversations table cu doar primary key index.
**[INFO]** skills_tree, agent_sessions bine indexate.

---

## Section 10: Database stats

| Metric | Value |
|--------|-------|
| PostgreSQL version | 17.9 (Debian) |
| claudedb total size | 20.7 MB |
| Active connections | 6 |
| Replication slots | 0 |

**[INFO]** Active connections normale (6 < 50).
**[INFO]** Replication slots 0 - consistent cu argos_db_standby_active=false din settings.

---

## Section 11: Orphaned/log tables

| Table | Rows | Size |
|-------|------|------|
| error_history | 0 | 16.0 KB |
| heartbeat_log | 60 | 88.0 KB |
| reasoning_log | 494 | 216.0 KB |
| lab_changelog | 0 | 24.0 KB |

**[INFO]** Log tables au row counts mici, nu necesita cleanup inca.

---

## Section 12: Top findings cross-cutting

1. **[HIGH]** hermes heartbeat: ultima intrare 2026-04-08 (6 zile ago) - nod offline sau daemon stopped
2. **[HIGH]** skills_tree: 18 orphan parent_paths detected (tree integrity concern)
3. **[MEDIUM]** messages: doar primary key index, lipsa index pe conversation_id
4. **[MEDIUM]** conversations: doar primary key index
5. **[MEDIUM]** skills_tree: 11 skills cu content < 300 chars (stubs)
6. **[MEDIUM]** skills_tree: 12 skills never updated (updated_at IS NULL)
7. **[MEDIUM]** agent_sessions: 4/5 recent sessions failed
8. **[INFO]** Toate tabelele sub 100k rows, dimensiuni sanatoase
9. **[INFO]** Zero orphan messages, zero pending backlog
10. **[INFO]** Credentials properly masked in settings output

---

## Section 13: Observatii colaterale

- **[FOR-TASK-5 AGENT LOOP]** 4 din 5 recent agent sessions au status "failed". Pattern-ul sugereaza probleme in verification chain sau command execution flow. Necesita investigare agent loop logic.

- **[FOR-TASK-7 INFRASTRUCTURE]** hermes heartbeat absent 6 zile. Fie nodul e offline, fie argos-heartbeat.service nu ruleaza pe hermes. Settings indica argos_heartbeat_daemon_hermes=true deci e asteptat sa ruleze.

- **[FOR-TASK-8 SKILLS]** 11 skills au content sub 300 chars si 12 nu au fost niciodata actualizate. Skills audit ar putea identifica care sunt placeholder vs incomplete.

- **[FOR-TASK-7 INFRASTRUCTURE]** Orphan parent_paths ar putea fi root categories intentionale (argos-core, docker-swarm, etc.) sau tree structure issues. Necesita clarificare design.

---

## Section 14: Recomandari prioritare

1. **Investigate hermes heartbeat** - verifica daca nodul e online si daca argos-heartbeat.service ruleaza
2. **Clarify orphan parent_paths** - decide daca sunt root categories sau necesita skills parinte create
3. **Add index pe messages(conversation_id)** - va imbunatati performanta JOIN-urilor
4. **Review failed agent sessions** - pattern de 4/5 failed sugereaza bug in agent loop
5. **Expand stub skills** - cele 11 skills cu < 300 chars ar putea necesita content

---

## Section 15: Metadata

- **Timp rulare:** ~3 secunde
- **Comanda:** `docker exec $CONT python3 /home/darkangel/.argos/argos-core/tools/audit/scripts/04_database_integrity.py`
- **Linii output:** ~230
- **Erori:** 0
- **SQL adhoc executat:** 0 (conform protocol)
- **Modificari DB:** 0 (read-only audit)
