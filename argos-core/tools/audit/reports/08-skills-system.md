# AUDIT REPORT 08 - Skills System Deep Audit

**Generated:** 2026-04-15 00:16 UTC
**Target:** skills_tree + skills tables, chat.py, prompts.py
**Auditor:** Claude Code (read-only audit)

---

## Section 1: Rezumat executiv

Skills system contine **110 skills** in `skills_tree` cu lungime medie de **2540 chars** si total **279KB content**. **11 stubs** (< 300 chars) reprezinta 10% - sub threshold problematic. **12 skills nu au fost niciodata actualizate** (toate create pe 7 aprilie intr-un batch). **4 emergency skills au updated_at=NULL** - problematic pentru skills critice. Tabela legacy `skills` contine 25 rows separate - sistem diferit bazat pe OS detection. Toate cele 9 skill IDs referenced in cod exista in DB.

---

## Section 2: skills_tree overview

| Metric | Value |
|--------|-------|
| Total skills | 110 |
| Min length | 30 chars |
| Max length | 22,898 chars |
| Avg length | 2,540 chars |
| Total content | 279,377 chars (~273 KB) |

**Columns:** id, path, parent_path, name, tags, source, emergency, usage_count, last_used, created_at, content, verified, verified_at, verified_by, updated_at

---

## Section 3: Length distribution

```
tiny <100             1  #
stub 100-300         10  ##########
short 300-500        28  ############################
medium 500-1k        30  ##############################
long 1k-3k           16  ################
large 3k-8k          12  ############
huge >8k             13  #############
```

| Bucket | Count | % |
|--------|-------|---|
| tiny (<100) | 1 | 0.9% |
| stub (100-300) | 10 | 9.1% |
| short (300-500) | 28 | 25.5% |
| medium (500-1k) | 30 | 27.3% |
| long (1k-3k) | 16 | 14.5% |
| large (3k-8k) | 12 | 10.9% |
| huge (>8k) | 13 | 11.8% |

**[INFO]** Distributie sanatoasa. Stubs (< 300) = 11 skills = 10% - sub threshold de 15%.

---

## Section 4: Stubs detail

**Total stubs:** 11

| ID | Len | Path | Category | Severity |
|----|-----|------|----------|----------|
| 44 | 30 | debian/debian-haproxy-setup | REDIRECT | **[LOW]** |
| 85 | 121 | network/synology-dsm-basics | INCOMPLETE | **[MEDIUM]** |
| 84 | 171 | network/mikrotik-routeros-basics | INCOMPLETE | **[MEDIUM]** |
| 41 | 191 | nixos/nixos-haproxy-configuration | REDIRECT | **[LOW]** |
| 46 | 211 | debian/debian-postgresql-17-native | INCOMPLETE | **[MEDIUM]** |
| 70 | 224 | ssh/rsync-between-nodes | COMPLETE | **[INFO]** |
| 39 | 241 | nixos/nixos-nfs-export | INCOMPLETE | **[MEDIUM]** |
| 19 | 260 | docker-swarm/docker-swarm-force-restart | COMPLETE | **[INFO]** |
| 79 | 262 | skill-system/skill-import-system | INCOMPLETE | **[MEDIUM]** |
| 65 | 283 | home-assistant/home-assistant-ip-ban-reset | COMPLETE | **[INFO]** |
| 20 | 284 | docker-swarm/docker-swarm-promote/demote-nodes | COMPLETE | **[INFO]** |

### Analiza per stub:

**REDIRECT (placeholder intentional):**
- **#44** (30 chars): "# See Skill 32 for full config" - **[LOW]** redirect valid
- **#41** (191 chars): "# See Skill 31 for full HAProxy config" - **[LOW]** redirect cu notes

**INCOMPLETE (lipsa explicatii):**
- **#85** (121 chars): Synology - doar comenzi SSH fara context - **[MEDIUM]**
- **#84** (171 chars): MikroTik - doar comenzi RouterOS fara explicatii - **[MEDIUM]**
- **#46** (211 chars): PostgreSQL 17 - doar install + paths, fara config - **[MEDIUM]**
- **#39** (241 chars): NFS export - doar snippet config, fara context - **[MEDIUM]**
- **#79** (262 chars): Import system - lipsa detalii despre format .argosdb - **[MEDIUM]**

**COMPLETE (scurt dar functional):**
- **#70** (224 chars): rsync command complet cu flags - **[INFO]**
- **#19** (260 chars): force restart cu verify - **[INFO]**
- **#65** (283 chars): ip ban reset cu comanda clara - **[INFO]**
- **#20** (284 chars): promote/demote cu node IDs - **[INFO]**

---

## Section 5: Never updated

**Total:** 12 skills (updated_at IS NULL)

| ID | Len | Path | Created |
|----|-----|------|---------|
| 93 | 9,418 | argos-meta/argos-skill-creation-protocol | 2026-04-07 22:39 |
| 94 | 7,207 | argos-agent/verification-chain-design | 2026-04-07 23:33 |
| 96 | 5,506 | argos-agent/fix-loop-counter-cap | 2026-04-07 23:33 |
| 97 | 6,271 | postgresql/pattern-matching-operator-selection | 2026-04-07 23:33 |
| 98 | 7,426 | argos-agent/pattern-a-prompt-caching | 2026-04-07 23:33 |
| 99 | 7,646 | argos-core/text-design-before-code-protocol | 2026-04-07 23:33 |
| 101 | 8,356 | argos-core/fastapi-router-modular-add | 2026-04-07 23:41 |
| 102 | 8,617 | argos-core/idempotent-db-write-scripts | 2026-04-07 23:41 |
| 105 | 9,259 | argos-core/alpine-htmx-no-build-ui | 2026-04-07 23:48 |
| 107 | 10,512 | argos-core/sse-fastapi-polling-generator | 2026-04-07 23:48 |
| 108 | 10,304 | argos-core/sse-eventsource-per-component-cleanup | 2026-04-07 23:48 |
| 110 | 5,790 | argos-core/alpine-fragment-injection-replacenode | 2026-04-08 00:53 |

**[MEDIUM]** 12 skills never updated - toate create pe 7-8 aprilie intr-un batch de import. Cauza probabila: trigger `updated_at` nu se aplica la INSERT, doar la UPDATE. Toate sunt skills mari (5-10k chars), nu stubs.

---

## Section 6: Emergency skills

**Total emergency:** 10

| ID | Len | Updated | Path | Status |
|----|-----|---------|------|--------|
| 88 | 2,234 | 2026-04-13 14:33 | argos-deploy/argos-api-redeploy | **[INFO]** OK |
| 89 | 1,932 | 2026-04-13 12:52 | nixos/nixos-systemd-path-gotcha | **[INFO]** OK |
| 90 | 22,898 | 2026-04-12 22:34 | argos-core/argos-self-knowledge | **[INFO]** OK |
| 91 | 7,725 | 2026-04-07 08:53 | argos-core/argos-output-patterns | **[INFO]** OK |
| 92 | 11,663 | 2026-04-07 08:53 | argos-agent/argos-agent-loop-architecture | **[INFO]** OK |
| 93 | 9,418 | **NULL** | argos-meta/argos-skill-creation-protocol | **[HIGH]** |
| 94 | 7,207 | **NULL** | argos-agent/verification-chain-design | **[HIGH]** |
| 95 | 7,096 | 2026-04-14 13:33 | argos-agent/safety-guards-pre-execution | **[INFO]** OK |
| 97 | 6,271 | **NULL** | postgresql/pattern-matching-operator-selection | **[HIGH]** |
| 98 | 7,426 | **NULL** | argos-agent/pattern-a-prompt-caching | **[HIGH]** |

**[HIGH]** 4 emergency skills au updated_at=NULL (#93, #94, #97, #98). Emergency skills ar trebui sa fie mereu tracked cu updated_at pentru audit trail.

---

## Section 7: Top largest skills

| ID | Emergency | Len | Path | Severity |
|----|-----------|-----|------|----------|
| 90 | YES | 22,898 | argos-core/argos-self-knowledge | **[MEDIUM]** |
| 86 | NO | 14,242 | misc/agent-orcha-multi-agent-framework | **[INFO]** |
| 111 | NO | 12,587 | argos-deploy/openclaw-vm-setup | **[INFO]** |
| 92 | YES | 11,663 | argos-agent/argos-agent-loop-architecture | **[INFO]** |
| 107 | NO | 10,512 | argos-core/sse-fastapi-polling-generator | **[INFO]** |
| 108 | NO | 10,304 | argos-core/sse-eventsource-per-component-cleanup | **[INFO]** |
| 103 | NO | 10,197 | argos-core/vikunja-task-api-patterns | **[INFO]** |
| 93 | YES | 9,418 | argos-meta/argos-skill-creation-protocol | **[INFO]** |
| 105 | NO | 9,259 | argos-core/alpine-htmx-no-build-ui | **[INFO]** |
| 102 | NO | 8,617 | argos-core/idempotent-db-write-scripts | **[INFO]** |

**[MEDIUM]** Skill #90 (argos-self-knowledge) cu 22,898 chars depaseste threshold de 20,000. Ar putea fi impartit in 2-3 skills mai mici pentru maintainability.

---

## Section 8: Recently updated

**Total updated last 7 days:** 29 skills

| ID | Updated | Len | Path |
|----|---------|-----|------|
| 109 | 2026-04-14 13:33 | 8,397 | argos-core/secret-redaction-defense-in-depth |
| 75 | 2026-04-14 13:33 | 726 | github/github-pre-push-security-scanner |
| 95 | 2026-04-14 13:33 | 7,096 | argos-agent/safety-guards-pre-execution |
| 12 | 2026-04-14 12:08 | 3,130 | argos-reasoning/argos-reasoning---infrastructure |
| 83 | 2026-04-14 12:00 | 375 | network/cisco-ios-basics |
| 111 | 2026-04-14 11:42 | 12,587 | argos-deploy/openclaw-vm-setup |
| 2 | 2026-04-14 11:29 | 308 | argos-core/argos-service-restart-correct-method |
| 49 | 2026-04-14 11:09 | 611 | argos-deploy/argos-setup.sh-sql-schema |
| 104 | 2026-04-14 11:09 | 7,843 | postgresql/audit-columns-updated-at-trigger |
| 51 | 2026-04-14 11:09 | 1,869 | argos-deploy/argos-skills-tree-table |

**[INFO]** 29 skills actualizate in ultimele 7 zile - sistem activ cu dezvoltare continua.

---

## Section 9: Legacy skills table

**Total rows:** 25 (separate from skills_tree)

**Columns:** id, name, filename, os_type, version, keywords, loaded_when, created_at

| ID | Name | Filename | OS Type |
|----|------|----------|---------|
| 1 | linux-generic | linux-generic.md | linux |
| 2 | nixos-25.11 | nixos-25.11.md | nixos |
| 3 | proxmox-8 | proxmox-8.md | proxmox |
| 5 | debian-12 | debian-12.md | debian |
| 6 | haos-2024 | haos-2024.md | haos |
| 10 | grok-api | grok-api.md | any |
| 11 | claude-api | claude-api.md | any |
| 12 | ollama-local | ollama-local.md | any |
| 16 | cisco-ios | cisco-ios.md | cisco |
| 17 | mikrotik-routeros | mikrotik-routeros.md | mikrotik |

**Analiza:**
- Tabela `skills` este un **sistem diferit** de `skills_tree`
- Referentiaza fisiere `.md` externe (filename column)
- Are OS-based detection (os_type, version columns)
- Folosit probabil pentru auto-loading skills based on detected OS
- **NU sunt duplicate** - sunt complementare

**[MEDIUM]** Doua sisteme de skills paralele pot cauza confuzie. Documentatie necesara despre cand se foloseste fiecare.

---

## Section 10: Content patterns

| Pattern | Count | % |
|---------|-------|---|
| Markdown headers (#) | 107 | 97% |
| Bullets (- / *) | 73 | 66% |
| Paths mentioned | 33 | 30% |
| References other skills | 24 | 22% |
| Code blocks (```) | 18 | 16% |
| Bash code blocks | 4 | 4% |

**[INFO]** Majoritatea skills sunt structurate cu headers si bullets. 16% au code blocks explicite - acceptabil pentru skills procedurale.

---

## Section 11: Categories

| Category | Count | Avg Len | Stale (no update) |
|----------|-------|---------|-------------------|
| argos-core | 22 | 6,108 | 7 (32%) |
| postgresql | 12 | 1,633 | 1 (8%) |
| argos-deploy | 11 | 2,461 | 0 (0%) |
| docker-swarm | 10 | 443 | 0 (0%) |
| home-assistant | 8 | 621 | 0 (0%) |
| nixos | 8 | 616 | 0 (0%) |
| argos-agent | 5 | 7,780 | 3 (60%) |
| argos-reasoning | 5 | 1,475 | 0 (0%) |
| github | 5 | 515 | 0 (0%) |
| ssh | 4 | 411 | 0 (0%) |
| skill-system | 4 | 373 | 0 (0%) |
| debian | 4 | 316 | 0 (0%) |
| network | 3 | 222 | 0 (0%) |

**[MEDIUM]** argos-agent cu 60% stale (3/5 never updated). Skills critice despre agent ar trebui mentinute.

**[MEDIUM]** network cu avg 222 chars - cluster de stubs.

---

## Section 12: Skill loading in chat.py

### Skill-related functions

| Line | Function |
|------|----------|
| L1206 | `_detect_and_load_skills()` |
| L1259 | `_detect_os_and_load_skill()` |
| L1386 | `_grok_search_for_skill()` |
| L1432 | `_check_skill_limit()` |
| L1446 | `_increment_skill_counter()` |
| L1452 | `_generate_skill_from_web()` |
| L1467 | `_generate_skill_from_web_impl()` |

### Hardcoded skill references

| Skill | Mentions | Context |
|-------|----------|---------|
| #10 | 1 | argos-notes-and-roadmap |
| #11 | 1 | argos-reasoning---debugging-order |
| #12 | 1 | argos-reasoning---infrastructure |

**[INFO]** Doar 3 hardcoded skill references in chat.py - acceptabil pentru skills critice always-needed.

---

## Section 13: Skill loading in prompts.py

### Skill-related functions

| Line | Function |
|------|----------|
| L169 | `_score_skill()` |
| L217 | `_load_fixed_skills()` |
| L276 | `_select_dynamic_skills()` |
| L492 | `_format_skill_section_full()` |
| L502 | `_format_skill_section_truncated()` |

### DB queries on skills_tree

| Line | Query Pattern |
|------|---------------|
| L232 | `FROM skills_tree` - bulk load |
| L241 | `SELECT id, path, name, content FROM skills_tree WHERE id = $1` - single load |
| L311 | `FROM skills_tree` - dynamic selection |

**[INFO]** prompts.py are logica de scoring (`_score_skill`) si selectie dinamica. Queries sunt structurate corect.

---

## Section 14: Skills referenced in code vs DB

**Total unique skill IDs referenced:** 9
**All exist in DB:** YES

| Skill ID | Path | Referenced In |
|----------|------|---------------|
| #1 | argos-core/argos-health-check-and-status | api/debug.py:L7 |
| #2 | argos-core/argos-service-restart-correct-method | api/debug.py:L7 |
| #10 | argos-core/argos-notes-and-roadmap | api/chat.py:L1476 |
| #11 | argos-reasoning/argos-reasoning---debugging-order | api/chat.py:L1541 |
| #12 | argos-reasoning/argos-reasoning---infrastructure | api/chat.py:L1474 |
| #42 | nixos/nixos-firewall-ports | agent/loop.py:L434 |
| #90 | argos-core/argos-self-knowledge | agent/prompts.py:L164,166 |
| #92 | argos-agent/argos-agent-loop-architecture | agent/prompts.py:L37,40 |
| #93 | argos-meta/argos-skill-creation-protocol | tools/audit/scripts/... |

**[INFO]** Zero missing skills. Toate referenced IDs exista in DB.

---

## Section 15: Skill creation protocol (#93)

- **ID:** 93
- **Path:** argos-meta/argos-skill-creation-protocol
- **Length:** 9,418 chars
- **Updated:** NULL (never updated since creation)

### Content analysis (first 30 lines):

Protocol-ul defineste:
1. **REGULA ZERO:** Verifica daca exista skill similar inainte de creare
2. **NAMING CONVENTION:** lowercase, hyphen-separated, path unique
3. **CONTENT STRUCTURE:** Title, REGULA ZERO, SCOP, PATTERN sections
4. **Query pentru verificare:** `SELECT ... WHERE path ILIKE '%keyword%'`

**[INFO]** Protocol clar si detaliat cu pasi concreti. Include queries de verificare si naming conventions explicite.

---

## Section 16: Skill settings

| Setting | Value |
|---------|-------|
| argos_skills_source | db |
| skills_daily_limit | 5 |
| skills_generated_date | 2026-04-13 |
| skills_generated_today | 0 |

**[INFO]** Settings consistente cu observed behavior. skills_daily_limit=5 limiteaza auto-generarea pentru a preveni spam.

---

## Section 17: Top 15 findings cross-cutting

1. **[HIGH]** 4 emergency skills (#93, #94, #97, #98) au updated_at=NULL - critice fara audit trail
2. **[MEDIUM]** Skill #90 cu 22,898 chars - poate fi impartit in skills mai mici
3. **[MEDIUM]** 12 skills never updated - trigger updated_at nu se aplica la INSERT
4. **[MEDIUM]** argos-agent category cu 60% stale (3/5 never updated)
5. **[MEDIUM]** Doua sisteme de skills paralele (skills_tree + skills) - confuzie potentiala
6. **[MEDIUM]** network category cu avg 222 chars - cluster de stubs
7. **[MEDIUM]** 5 stubs incomplete (#85, #84, #46, #39, #79) - lipsa explicatii
8. **[LOW]** 2 stubs redirect (#44, #41) - intentional, dar ar putea fi merged
9. **[INFO]** 110 skills total, avg 2540 chars - size sanatos
10. **[INFO]** 29 skills updated in ultimele 7 zile - sistem activ
11. **[INFO]** 97% skills au markdown headers - structurate bine
12. **[INFO]** Zero missing skills in code references
13. **[INFO]** Skill creation protocol (#93) clar si complet
14. **[INFO]** skills_daily_limit=5 previne spam auto-generare
15. **[INFO]** prompts.py are scoring logic pentru dynamic selection

---

## Section 18: Observatii colaterale

- **[FOR-TASK-99 SYNTHESIS]** Pattern cross-cutting: updated_at=NULL apare si la skills (12) si la hermes heartbeat (task 07). Trigger-ul updated_at nu se aplica consistent la INSERT in toate tabelele.

- **[FOR-TASK-99 SYNTHESIS]** Doua sisteme paralele (skills_tree si skills) sugereaza evolutie incrementala fara cleanup. Similar cu chat.py care face prea multe (task 06).

- **[FOR-TASK-05 AGENT LOOP]** Skills #92 (agent-loop-architecture) si #94 (verification-chain-design) sunt emergency skills despre agent loop - documentatie critica dar #94 never updated.

- **[FOR-TASK-06 API]** chat.py contine 7 functii skill-related (L1206-1467) - skill management ar trebui mutat in modul separat.

---

## Section 19: Recomandari prioritare

1. **Fix updated_at trigger** - asigura ca INSERT seteaza updated_at = created_at pentru audit trail consistent

2. **Update emergency skills** - #93, #94, #97, #98 necesita updated_at setat (chiar si manual) pentru tracking

3. **Expand stubs incomplete** - prioritate pe #85 (Synology), #84 (MikroTik), #46 (PostgreSQL 17) care sunt incomplete

4. **Documenta diferenta skills_tree vs skills** - clarifica cand se foloseste fiecare sistem

5. **Refactor skill #90** - impartit argos-self-knowledge (22k chars) in 2-3 skills: self-knowledge-core, self-knowledge-infrastructure, self-knowledge-protocols

---

## Section 20: Metadata

- **Timp rulare:** ~5 secunde
- **Comanda:** `docker exec $CONT python3 /home/darkangel/.argos/argos-core/tools/audit/scripts/08_skills_system.py`
- **Linii output:** ~280
- **Erori:** 0
- **SQL adhoc:** 0
