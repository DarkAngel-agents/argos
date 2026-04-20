# AUDIT TASK 02 - Code inventory + anti-patterns

Sesiune de audit READ-ONLY pe ARGOS. Obiectiv: scanezi codul Python (agent, api, llm, tools) si scrii raport cu inventarul + anti-patterns detectate de scriptul pre-scris.

## REGULI STRICTE

1. **READ-ONLY.** Nu modifici nimic. Singurul fisier pe care il creezi este raportul MD la sfarsit.
2. **Zero bash adhoc.** O singura comanda rulezi (scriptul de recon). Nu inventezi altceva.
3. **Zero reasoning lung.** Ruleaza scriptul, copiaza date in raport, adauga severity, gata. Fara analiza punct cu punct, fara "hmm poate ar trebui sa verific mai mult".
4. **Time budget: 10 minute max.** Daca dureaza mai mult, scrii ce ai si pleci.
5. **STOP dupa ce scrii fisierul.** Nu continui cu task 03. Cand ai terminat Pas 5, faci `echo "DONE"` si astepti.

## PASI CONCRETI

### Pas 1 - Ruleaza scriptul

Comanda exacta (ruleaza din directorul curent, unde ai fost lansat):

    CONT=$(docker ps -q -f name=argos | head -1)
    docker exec $CONT python3 /home/darkangel/.argos/argos-core/tools/audit/scripts/02_code_inventory.py

Output-ul are ~180 linii text structurate in 12 sectiuni (2.1 - 2.12). Citesti tot.

### Pas 2 - Nu mai faci alte comenzi

Ai toate datele din acest output. Nu deschizi fisiere, nu grep-uiesti altceva, nu verifici in DB. Toata munca de recon e facuta de script.

### Pas 3 - Scrii raportul

Fisier target: `/home/darkangel/.argos/argos-core/tools/audit/reports/02-code-inventory.md`

Structura OBLIGATORIE cu sectiunile de mai jos. Pentru fiecare element detectat adaugi un marker de severity din: CRITICAL, HIGH, MEDIUM, LOW, INFO.

## SECTIUNI DE INCLUS IN RAPORT

### Section 1: Rezumat executiv
3-5 propozitii. Numar total fisiere, LOC, top 3 probleme cele mai severe, impresie generala despre calitatea codului.

### Section 2: Inventory stats
Copiezi datele din output sectiunea 2.1 (Summary):
- Total files, total lines, total bytes
- Per dir: agent, api, llm, tools

### Section 3: Hotspots (cele mai mari fisiere)
Copiezi top 5 din sectiunea 2.2. Pentru fiecare, adaugi o observatie scurta gen "fisier principal, candidate pentru refactor" sau "mare dar specializat, acceptabil".

Marker severity per fisier:
- > 1000 linii = HIGH (candidate refactor urgent)
- 500-1000 linii = MEDIUM
- < 500 linii = LOW

### Section 4: Dead code suspects
Copiezi sectiunea 2.3. Daca e gol, scrii "No stub files detected [INFO]".

### Section 5: Technical debt markers
Copiezi sectiunea 2.4 (TODOs/FIXMEs). Pentru fiecare TODO, adaugi severity: LOW daca e comentariu de follow-up, MEDIUM daca pare amanare reala, HIGH daca mentioneaza "security" sau "broken".

### Section 6: Exception handling anti-patterns
Copiezi sectiunea 2.5 (bare except / except Exception: pass). 

Structureaza asa:
- **Total count:** X
- **Per-file grouping:** (numar per fisier sortat descrescator)
- **Top 3 fisiere cu problema:** numeste-le cu count

Marker severity:
- > 10 bare except intr-un fisier = HIGH
- 5-10 bare except = MEDIUM
- 1-4 bare except = LOW

### Section 7: Logging discipline
Copiezi sectiunea 2.6 (prints without marker). 

Structureaza:
- **Total bad prints:** X
- **Per-file grouping top 5**
- **Impact:** skill argos-output-patterns (id 91) cere marker [CATEG NNN] pe toate print-urile. Violatii = logging fragil, greu de filtrat, debug slower.

Marker severity: MEDIUM global.

### Section 8: Hardcoded values
Copiezi sectiunea 2.7 (IPs + ports). 

Lista fisierelor cu IPs hardcoded. Marker:
- IPs in executor.py, code_runner.py (machine mapping) = LOW (expected, e harta masinilor)
- IPs in agent/loop.py, api/main.py (database) = MEDIUM (ar trebui doar DB_HOST env var)
- IPs in orice alt fisier = HIGH

### Section 9: Long functions
Copiezi sectiunea 2.8 (long functions).

Marker per functie:
- > 500 linii = CRITICAL (ex: `run_agent_loop 747 lines` = CRITICAL)
- 200-500 linii = HIGH
- 100-200 linii = MEDIUM
- 80-100 linii = LOW

### Section 10: Security quick check
Copiezi sectiunea 2.9 (SQL f-strings). Daca e gol, scrii "No SQL injection patterns detected via f-string scan [INFO]".

### Section 11: Global state
Copiezi sectiunea 2.10 (global statements).

Marker severity:
- global in module init (ex: `global pool` in lifespan) = LOW (acceptable pattern)
- global in agent/tools.py = MEDIUM (poate e smell, de investigat)

### Section 12: Syntax check
Copiezi sectiunea 2.11. Daca e [none] scrii "All files parse cleanly [INFO]".

### Section 13: Documentation
Copiezi sectiunea 2.12 (files without docstring).

Marker: INFO. E nice-to-have, nu critical.

### Section 14: Top 10 findings cross-cutting
Ordoneaza toate findings-urile din sectiunile 3-13 dupa severity (CRITICAL primul, apoi HIGH, MEDIUM, LOW). Extrage top 10 si pune-le aici cu o linie fiecare.

Format:
    1. [CRITICAL] agent/loop.py run_agent_loop() = 747 lines - decompose in phases
    2. [HIGH] api/chat.py = 1550 lines total - refactor needed
    3. [HIGH] api/chat.py: 8 bare except / except Exception: pass
    ...

### Section 15: Observatii colaterale pentru task-uri urmatoare
Lucruri care sar in ochi dar nu sunt in scope-ul task 02. Marcheaza cu [FOR-TASK-N] unde N e task-ul care ar trebui sa le aprofundeze.

Exemple posibile:
- [FOR-TASK-3 SECURITY] api/backup.py are SSH hardcoded cu client_keys, verifica permisiuni keys
- [FOR-TASK-4 DATABASE] verifica ce queries concrete sunt in agent/loop.py
- [FOR-TASK-5 AGENT LOOP] run_agent_loop() are 747 linii, aprofundeaza structura

### Section 16: Metadata
- **Timp rulare:** X minute
- **Comanda rulata:** docker exec ... python3 ... 02_code_inventory.py
- **Linii output script:** ~182
- **Erori intampinate:** [daca vreuna]

## PASUL 4 - Afiseaza DONE

Dupa ce ai scris fisierul, ruleaza exact:

    echo "DONE TASK 02"
    wc -l /home/darkangel/.argos/argos-core/tools/audit/reports/02-code-inventory.md

## STOP

Cand ai afisat DONE TASK 02 si wc -l, te opresti. Nu continui cu alte task-uri. Nu faci analiza suplimentara. Nu "hai sa mai verific ceva". STOP. Astepti urmatorul prompt.

## SUCCES

- Fisierul MD exista la path-ul corect
- Toate sectiunile 1-16 sunt prezente
- Severity markers sunt aplicate per item
- Section 14 are exact 10 findings sortate by severity
- Cel putin 3 markeri [FOR-TASK-N] in section 15
- Total ~300-500 linii in raport
- Nu ai modificat nimic in sistem
- Nu ai rulat alte comenzi in afara scriptului + wc + echo

## ESEC

- Lipseste fisierul MD
- Lipsesc sectiuni
- Ai modificat fisiere in sistem
- Ai rulat grep/find/cat ad-hoc
- Ai intrat in reasoning > 3 minute
- Ai inceput task 03 fara instructiuni
