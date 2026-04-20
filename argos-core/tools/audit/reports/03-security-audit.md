# AUDIT REPORT 03 - Security & Credentials

**Data:** 2026-04-14
**Auditor:** Claude Opus 4.5
**Status:** COMPLETED

---

## Section 1: Rezumat executiv

Scanat 28 fisiere Python din ARGOS core. Am identificat **1 CRITICAL**, **2 HIGH**, **0 MEDIUM**, **1 LOW** findings. Cea mai grava problema: pattern de credential detectat in `api/chat.py` L1089. A doua: backup `.env.bak-20260414-1200` care poate contine credentiale vechi. In general, permisiunile pe fisierele sensibile sunt corecte (600), dar exista un `.env` duplicat in root pe langa `config/.env` care trebuie clarificat.

---

## Section 2: Scope

- **Python files scanned:** 28
- **Subdirs:** agent, api, llm, tools
- **Argos root:** /home/darkangel/.argos

---

## Section 3: Credential patterns in source code

**Total matches:** 1

| File | Line | Pattern | Severity |
|------|------|---------|----------|
| api/chat.py | L1089 | Known password pattern | **[CRITICAL]** |

---

## Section 4: Hardcoded password/secret assignments

**Total hardcoded assignments (non-env):** 1

| File | Line | Type | Severity |
|------|------|------|----------|
| api/iso_builder.py | L176 | password assignment | **[HIGH]** |

Nota: Valoarea a fost detectata ca hardcoded literal, nu din env/environ fallback.

---

## Section 5: Logging leak potential

**Total suspicious prints:** 1

| File | Line | Keyword | Context | Severity |
|------|------|---------|---------|----------|
| api/chat.py | L1064 | token | "tokeni estimati, comprim..." | **[LOW]** |

Nota: Acest print afiseaza numarul de tokens LLM, nu o credentiala. Keyword match fals pozitiv pe "tokeni" (romana).

---

## Section 6: Sensitive files on disk

**Total found:** 3

| Path | Mode | Severity |
|------|------|----------|
| /home/darkangel/.argos/argos-core/.env | 0o600 | **[INFO]** |
| /home/darkangel/.argos/argos-core/.env.bak-20260414-1200 | 0o600 | **[INFO]** |
| /home/darkangel/.argos/argos-core/config/.env | 0o600 | **[INFO]** |

Permisiuni corecte pe toate fisierele sensibile.

---

## Section 7: config/.env specific

**Primary config/.env:**
- Path: `/home/darkangel/.argos/argos-core/config/.env`
- Mode: `0o600` - **[INFO]** corect
- World-readable: False
- World-writable: False
- Total lines: 7
- Keys defined: 7
- **Keys:** ANTHROPIC_API_KEY, CLAUDE_TOKEN, GROK_API_KEY, XAI_API_KEY, DB_PASSWORD, DB_USER, DB_NAME

**[HIGH]** Secondary .env gasit la `/home/darkangel/.argos/argos-core/.env`
- Mode: 0o600
- Posibil duplicat sau leftover - de verificat daca e folosit undeva

---

## Section 8: Backup files

**Total backup files:** 14

### .env backups (risc credentiale):
| Path | Mode | Severity |
|------|------|----------|
| .env.bak-20260414-1200 | 0o600 | **[HIGH]** |

### Alte backup-uri (primele 10):
| Path | Severity |
|------|----------|
| setup.sh.bak | **[LOW]** |
| heartbeat.py.bak-20260406-034924 | **[LOW]** |
| api/main.py.bak | **[LOW]** |
| api/chat.py.bak | **[LOW]** |
| api/chat.py.bak-20260406-010617 | **[LOW]** |
| ui/new/modules/chats.html.bak | **[LOW]** |
| ui/new/modules/jobs.html.bak | **[LOW]** |
| ui/new/modules/fleet.html.bak | **[LOW]** |
| ui/new/modules/reasoning.html.bak | **[LOW]** |
| ui/new/modules/health.html.bak | **[LOW]** |

Plus 3 altele.

---

## Section 9: SSH keys

**[INFO]** /home/darkangel/.ssh not accessible from container (normal - bind-mounted read-only sau inexistent in container)

Nu se poate audita din container. Verificare manuala recomandata pe host.

---

## Section 10: Git repo

**[INFO]** No .git directory detected in argos root din container.

Git repo este probabil la nivel de host, nu bind-mounted in container. Nu se poate verifica .gitignore din acest context.

---

## Section 11: Dangerous subprocess patterns

**[INFO]** No shell=True usage detected - CONFIRMED

Zero riscuri de command injection prin subprocess.

---

## Section 12: eval/exec usage

**[INFO]** No eval/exec usage detected - CONFIRMED

Zero riscuri de arbitrary code execution prin eval/exec.

---

## Section 13: Top findings cross-cutting

1. **[CRITICAL]** api/chat.py L1089 - credential pattern detected in source code
2. **[HIGH]** .env.bak-20260414-1200 - backup file may contain old credentials
3. **[HIGH]** api/iso_builder.py L176 - hardcoded password assignment
4. **[HIGH]** Secondary .env in argos-core/ root - duplicate config file
5. **[LOW]** api/chat.py L1064 - print statement with "token" keyword (false positive - token count)
6. **[LOW]** 13 backup files (.bak) in codebase - potential code leaks

---

## Section 14: Observatii colaterale

- **[FOR-TASK-4 DATABASE]** DB_PASSWORD definit in .env - de verificat ca nu e expus in loguri
- **[FOR-TASK-5 AGENT LOOP]** ANTHROPIC_API_KEY, GROK_API_KEY, XAI_API_KEY in .env - de verificat ca nu apar in prompts/outputs
- **[FOR-TASK-7 INFRASTRUCTURE]** Multiple .bak files sugereaza editing manual frecvent - de considerat git versioning proper

---

## Section 15: Recomandari prioritare

1. **Verifica api/chat.py L1089** - identifica ce credential pattern e si elimina/muta in .env
2. **Sterge .env.bak-20260414-1200** dupa ce confirmi ca nu mai e necesar
3. **Clarifica rolul .env din root** vs config/.env - elimina duplicatul
4. **Verifica api/iso_builder.py L176** - muta password in env var daca e folosit real
5. **Curata .bak files** - muta in git history sau sterge

---

## Section 16: Metadata

- **Timp rulare script:** < 5 secunde
- **Comanda rulata:** `docker exec $CONT python3 /home/darkangel/.argos/argos-core/tools/audit/scripts/03_security_audit.py`
- **Linii output script:** ~80
- **Erori:** None

---

*Report generated by Claude Opus 4.5 - ARGOS Security Audit Task 03*
