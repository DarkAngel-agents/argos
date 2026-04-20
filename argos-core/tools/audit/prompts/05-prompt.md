# AUDIT TASK 05 - Agent loop deep dive

Sesiune READ-ONLY pe ARGOS. Obiectiv: analiza profunda a agent loop-ului - structura, complexitate, phase transitions, verification chain, DB writes, side effects. Plus cross-reference cu agent_sessions failure pattern din task 04.

## REGULI STRICTE

1. **READ-ONLY.** Singurul fisier creat = raport MD.
2. **Zero comenzi adhoc.** O singura comanda - scriptul. Nu deschizi loop.py manual, nu faci grep, nu rulezi sql adhoc.
3. **Zero reasoning lung.** Citesc output, copiez date, aplic severity, scriu, stop.
4. **Time budget: 12 min max** (scriptul scoate output mai mare ca task 04).
5. **STOP dupa DONE.** `/exit` imediat.

## PASI

### Pas 1 - Ruleaza scriptul

    CONT=$(docker ps -q -f name=argos | head -1)
    docker exec $CONT python3 /home/darkangel/.argos/argos-core/tools/audit/scripts/05_agent_loop_deep.py

Output: 15 sectiuni (5.1 - 5.15), probabil 400-700 linii.

### Pas 2 - Nu faci alte comenzi

Toate datele vin din script. Nu deschizi cod sursa, nu interoghezi DB.

### Pas 3 - Scrii raportul

Fisier: `/home/darkangel/.argos/argos-core/tools/audit/reports/05-agent-loop-deep.md`

## SECTIUNI RAPORT

### Section 1: Rezumat executiv
3-5 propozitii. Numar functii in loop.py, cea mai lunga functie, complexitate generala, distributie phase, agent sessions failure pattern, observatie principala despre design.

### Section 2: Files overview
Copiezi sectiunea 5.1 ca tabel: fisier, lines, bytes.

### Section 3: loop.py structure
Copiezi sectiunea 5.2:
- Total lines
- Numar total functii
- **TOATE functiile sortate descrescator** (acesta e datele importante)

Pentru fiecare functie cu length >= 100 linii adauga marker:
- **[CRITICAL]** > 500 linii (decompose urgent)
- **[HIGH]** 200-500 linii
- **[MEDIUM]** 100-200 linii

### Section 4: loop.py complexity
Copiezi sectiunea 5.3 ca tabel cu coloanele Indicator / Count.

Adauga severity overall:
- **[CRITICAL]** if_statements > 200 sau nested_depth_max > 8
- **[HIGH]** if_statements 100-200 sau nested_depth_max 6-8  
- **[MEDIUM]** if_statements 50-100 sau nested_depth_max 4-6
- **[LOW]** sub aceste threshold-uri

Comenteaza pe tot ce sare in ochi (ex: "26 try_blocks intr-un singur fisier sugereaza error handling fragmentat").

### Section 5: Phase transitions
Copiezi sectiunea 5.4:
- Lista phase keywords cu count
- Lista phase change statements (primele 15)

Severity:
- **[INFO]** daca toate phase-urile esentiale apar (executing, verifying, fixing, complete, failed)
- **[MEDIUM]** daca lipseste vreuna semnificativa
- **[HIGH]** daca apar phase-uri necunoscute sau ambigue (ex: "active" si "complete" amestecate)

### Section 6: Critical branches  
Copiezi sectiunea 5.5 (retry, escalate, abort, fix_loop, iteration).

Pentru fiecare categorie:
- **[INFO]** count > 0 = present
- **[HIGH]** abort = 0 (nu exista cale de iesire forta)
- **[MEDIUM]** fix_loop = 0 (lipseste fix loop counter cap din skill 96)
- **[LOW]** retry = 0 (poate intentionat)

### Section 7: DB writes
Copiezi sectiunea 5.6:
- Total writes
- Distribution by operation (INSERT/UPDATE/DELETE)
- Lista primelor 20

Severity:
- **[INFO]** distributia normala (mostly INSERT pentru log + UPDATE pentru state)
- **[MEDIUM]** > 5 DELETE statements (suspect)
- **[HIGH]** orice DELETE pe agent_sessions sau messages (cleanup risc)

### Section 8: Subprocess / SSH calls
Copiezi sectiunea 5.7.

Severity:
- **[INFO]** functional (asa lucreaza)
- **[MEDIUM]** > 10 calls in loop.py (poate fi mutat in tools.py)

### Section 9: verification.py analysis
Copiezi sectiunea 5.8:
- Total lines
- Lista functii
- Pattern matching operators (ILIKE / ~* / re.search)

Severity:
- **[CRITICAL]** daca apare `ILIKE` cu pattern regex (bug-ul vechi din S4 - trebuia ~*)
- **[HIGH]** daca lipseste pattern matching deloc (verification trivial)
- **[INFO]** daca foloseste ~* sau re.search

### Section 10: evidence.py analysis
Copiezi sectiunea 5.9.

Severity bazata pe complexitate:
- **[INFO]** functii < 80 lines fiecare
- **[MEDIUM]** orice functie > 100 lines

### Section 11: autonomy.py analysis
Copiezi sectiunea 5.10.

Severity:
- **[INFO]** structura clara cu functii < 150 linii
- **[MEDIUM]** functii mari sau lipsa explicita a check-urilor de autonomy

### Section 12: tools.py analysis
Copiezi sectiunea 5.11:
- Total lines + functii
- Tool dispatch patterns

Severity:
- **[INFO]** dispatch pattern clar (TOOLS dict / register_tool)
- **[MEDIUM]** dispatch ad-hoc cu if/elif chain

### Section 13: prompts.py top functions
Copiezi sectiunea 5.12.

Severity per functie >= 80 linii:
- **[MEDIUM]** > 200 linii
- **[LOW]** 80-200 linii (acceptabil pentru prompt building)

### Section 14: Agent sessions failure pattern
Copiezi sectiunea 5.13:
- Distribution by phase
- Failed sessions iteration stats
- Last 10 sessions detail

ANALIZA OBLIGATORIE:
- Calculeaza % failure rate (failed / total)
- **[CRITICAL]** failure rate > 70%
- **[HIGH]** failure rate 50-70%
- **[MEDIUM]** failure rate 20-50%
- Observa daca failed sessions au max iterations atinse sau abort-ate prematur
- Observa LLM provider folosit (claude vs grok vs local)

### Section 15: Evidence growth
Copiezi sectiunea 5.14.

Severity:
- **[INFO]** evidence < 100KB per session
- **[MEDIUM]** evidence > 500KB (memory pressure)
- **[HIGH]** evidence > 5MB (runaway accumulation)

### Section 16: Verification rules referenced
Copiezi sectiunea 5.15:
- Total rules
- Liniile din verification.py care refera tabela / coloane

Severity:
- **[INFO]** verification.py refera explicit la tabele/coloane DB
- **[HIGH]** verification.py face hardcoded logic, nu citeste din DB (rules dead)

### Section 17: Top 15 findings cross-cutting
Sortate CRITICAL -> HIGH -> MEDIUM -> LOW -> INFO. Format:

    1. [CRITICAL] agent/loop.py run_agent_loop() = 747 lines - decompose into phase handlers
    2. [HIGH] loop.py: 26 try blocks suggest fragmented error handling
    ...

### Section 18: Observatii colaterale
Markeri [FOR-TASK-N]:
- [FOR-TASK-6 API] daca observi probleme care vin din chat.py call site-uri
- [FOR-TASK-7 INFRASTRUCTURE] daca observi probleme legate de subprocess/ssh
- [FOR-TASK-8 SKILLS] daca prompt building face referinta hardcodata la skill-uri
- [FOR-TASK-9 UI] daca apar referinte la componente UI

Max 8 bullets.

### Section 19: Recomandari prioritare
Top 5 actiuni concrete:

Exemplu:
    1. Decompose run_agent_loop() in 4-5 phase handlers (executing, verifying, fixing, evidence)
    2. Add fix_loop counter cap if missing (referencing skill 96)
    3. Move subprocess/ssh calls from loop.py to tools.py
    4. Refactor large prompts.py functions if any > 200 linii
    5. Investigate failure pattern - reproduce 1 failed session

### Section 20: Metadata
- Timp rulare
- Comanda
- Linii output
- Erori

## PASUL 4 - DONE

    echo "DONE TASK 05"
    wc -l /home/darkangel/.argos/argos-core/tools/audit/reports/05-agent-loop-deep.md

## STOP

Dupa DONE, `/exit`. NU continui cu task 06.

## SUCCES

- Toate sectiunile 1-20 prezente
- Severity markers aplicate consecvent
- Top 15 findings sortate corect
- Cel putin 3 markeri [FOR-TASK-N]
- Failure rate calculat in section 14
- Nimic modificat

## ESEC

- Lipsesc sectiuni
- Failure rate ne-calculat
- Reasoning > 3 minute
- Comenzi adhoc rulate in afara scriptului
