# AUDIT TASK 04 - Database integrity

Sesiune READ-ONLY pe ARGOS DB. Obiectiv: verifica integritatea structurala + datele in claudedb, cu focus pe skills_tree, settings, agent sessions, verification rules, messages.

## REGULI STRICTE

1. **READ-ONLY.** Zero INSERT/UPDATE/DELETE/CREATE/DROP/ALTER. Singurul fisier pe care il creezi este raportul MD.
2. **Zero SQL adhoc.** Toate interogarile le face scriptul pre-scris. Nu deschizi psql, nu rulezi docker exec python3 inline.
3. **NICIODATA nu scrii valori de credentiale** in raport. Scriptul mascheaza deja - tu le lasi mascate.
4. **Zero reasoning lung.** Ruleaza scriptul, copiaza datele, aplica severity, stop.
5. **Time budget: 10 min max.**
6. **STOP dupa DONE.** `/exit` imediat.

## PASI

### Pas 1 - Ruleaza scriptul

    CONT=$(docker ps -q -f name=argos | head -1)
    docker exec $CONT python3 /home/darkangel/.argos/argos-core/tools/audit/scripts/04_database_integrity.py

Output-ul are 10 sectiuni (4.1 - 4.10), probabil 300-500 linii.

### Pas 2 - Nu faci alte comenzi

Scriptul iti da tot ce trebuie.

### Pas 3 - Scrii raportul

Fisier: `/home/darkangel/.argos/argos-core/tools/audit/reports/04-database-integrity.md`

## SECTIUNI RAPORT

### Section 1: Rezumat executiv
3-5 propozitii. Cate tabele, total rows, dimensiunea DB, cele mai mari tabele, probleme de integritate majore gasite.

### Section 2: Schema overview
Copiezi sectiunea 4.1 ca tabel markdown. Include top 15 tabele dupa row count.

Severity per tabel:
- **[INFO]** tabele cu row counts normale
- **[MEDIUM]** tabele > 100k rows (verifica daca e runaway growth)
- **[HIGH]** tabele > 1M rows sau > 1GB size

### Section 3: skills_tree integrity
Copiezi sectiunea 4.2 organizat pe subsectiuni:

**3.1 General stats:** total, verified, emergency

**3.2 Duplicate paths / names:**
- **[HIGH]** orice duplicate path (path ar trebui sa fie unique)
- **[MEDIUM]** duplicate names (acceptabil dar confuz)

**3.3 Content anomalies:**
- Skills cu content < 300 chars: lista lor
  - **[MEDIUM]** daca sunt > 10 stubs
  - **[LOW]** daca sunt < 10 (acceptabil, poate placeholders)
- Skills cu content > 15000 chars: lista
  - **[INFO]** informativ, nu problema per se
- **[HIGH]** skills cu NULL/empty content

**3.4 Stale skills:**
- Skills cu updated_at IS NULL: lista primelor 15
- **[MEDIUM]** daca sunt > 20 skills never updated

**3.5 Unverified:**
- **[MEDIUM]** orice skill unverified
- **[INFO]** daca 0

**3.6 Distribution by parent_path:** copiezi sectiunea ca referinta

**3.7 Orphan parent_paths:**
- **[HIGH]** orice orphan parent (tree integrity broken)

### Section 4: settings table
Copiezi sectiunea 4.3:

- **4.1 General:** total entries, columns
- **4.2 Duplicates:** **[HIGH]** orice duplicate key
- **4.3 NULL values:** **[MEDIUM]** count
- **4.4 Keys list:** copiezi lista completa cu valori mascate pentru sensitive

**IMPORTANT:** Keys care contin api_key/token/password/secret trebuie sa apara mascate in raport. Daca vreun pattern sensitive apare NEMASCATA in output-ul scriptului, raporteaza ca **[CRITICAL]** security leak din script.

### Section 5: Agent sessions
Copiezi sectiunea 4.4:
- Total sessions
- Schema columns
- Recent 5 sessions (compact)
- Severity: INFO daca totul e normal

### Section 6: Agent verification rules
Copiezi sectiunea 4.5:
- Total rules
- Distribution by action
- First 30 rules compact

Severity:
- **[HIGH]** daca exista rules cu action NULL sau "unknown"
- **[MEDIUM]** daca una din actiunile esentiale (allow/deny/needs_more_context) lipseste din distributie

### Section 7: Messages + conversations
Copiezi sectiunea 4.6:
- Total messages, conversations, avg per conv
- Top 10 conversations by count
- Orphan messages
- Pending messages
- Recent activity 24h/7d
- Empty conversations

Severity:
- **[HIGH]** orice orphan messages > 0 (foreign key violation)
- **[MEDIUM]** > 1000 pending messages (backlog)
- **[MEDIUM]** runaway conversation (> 500 messages e suspect)
- **[LOW]** multe empty conversations (cleanup necesar)

### Section 8: Heartbeat freshness
Copiezi sectiunea 4.7:
- Total entries
- Last 5min / 1h / 24h counts
- Latest entry timestamp

Severity:
- **[CRITICAL]** zero entries in ultimele 5 minute (heartbeat e stopped!)
- **[HIGH]** zero entries in ultima ora
- **[INFO]** heartbeat pare sanatos

### Section 9: Index coverage
Copiezi sectiunea 4.8:
- Per tabel: count indexuri + lista scurta

Severity:
- **[MEDIUM]** hot table (skills_tree, messages) cu doar 1 index (primary key)
- **[INFO]** 2+ indexuri

### Section 10: Database stats
Copiezi sectiunea 4.9:
- PostgreSQL version
- claudedb total size
- Active connections
- Replication status

Severity:
- **[HIGH]** zero replication slots (HA broken, daca era asteptat)
- **[MEDIUM]** > 50 active connections (potential pool leak)

### Section 11: Orphaned/log tables
Copiezi sectiunea 4.10

Severity:
- **[MEDIUM]** log tables > 100k rows (cleanup retention needed)

### Section 12: Top findings cross-cutting
Top 10 sortate CRITICAL -> HIGH -> MEDIUM -> LOW -> INFO.

Format:
    1. [CRITICAL] heartbeat_log: zero entries in 5min - daemon stopped
    2. [HIGH] orphan messages: X rows with no conversation
    3. [HIGH] skills_tree: Y duplicate paths detected
    ...

Daca ai < 10, lasa cat ai.

### Section 13: Observatii colaterale
Markeri [FOR-TASK-N]:
- [FOR-TASK-5 AGENT LOOP] - daca agent_sessions sau verification rules au patterns suspecte
- [FOR-TASK-6 API] - daca messages/conversations au issues care sugereaza bugs in API
- [FOR-TASK-7 INFRASTRUCTURE] - daca replication/connections indica probleme infra
- [FOR-TASK-8 SKILLS] - daca skills_tree are probleme de content quality care merita audit profund

Max 8 bullets.

### Section 14: Recomandari prioritare
Top 5 actiuni concrete pentru DB:

Exemplu:
    1. Fix orphan parent_paths in skills_tree (rebuild tree integrity)
    2. Add retention policy pe log tables (clean entries > 90 zile)
    3. Investigate pending messages backlog
    4. Add index pe messages(conversation_id, created_at)
    5. ...

### Section 15: Metadata
- Timp rulare
- Comanda
- Linii output
- Erori

## PASUL 4 - DONE

    echo "DONE TASK 04"
    wc -l /home/darkangel/.argos/argos-core/tools/audit/reports/04-database-integrity.md

## STOP

Dupa DONE, `/exit`. NU continui cu task 05.

## SUCCES

- Fisier MD exista
- Toate sectiunile 1-15 prezente
- Severity markers aplicate
- Zero valori credentials expuse
- Top findings sortate corect
- Nu ai modificat DB
- Nu ai rulat SQL adhoc

## ESEC

- Lipseste raportul
- Ai rulat INSERT/UPDATE/DELETE/CREATE
- Ai expus valori credentials in raport
- Ai intrat in reasoning > 3 minute
- Ai rulat alte comenzi in afara scriptului
