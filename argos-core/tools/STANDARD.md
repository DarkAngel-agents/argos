# ARGOS tools/ - STANDARD

Scop: Folder pentru scripturi Python de diagnostic, inspectie si analiza pe
infrastructura ARGOS. NU e folder pentru production code (ala merge in api/),
NU e folder pentru executabile shell (ala merge in bin/).

Tools din acest folder sunt create de DarkAngel + Claude + ARGOS insusi
pe masura ce nevoile apar. In timp, unele tools vor deveni automate (chemate
de ARGOS la evenimente specifice: fail de send, schema change, etc).

## STRUCTURA OBLIGATORIE A UNUI TOOL

Fiecare fisier .py din tools/ trebuie sa respecte urmatoarele reguli.

### 1. Shebang si docstring header

```python
#!/usr/bin/env python3.13
"""
[TOOL_ID] nume_tool.py - descriere scurta

SCOP: Ce rezolva tool-ul, in 1-2 propozitii.

UTILIZARE:
    python3.13 /home/darkangel/.argos/argos-core/tools/nume_tool.py [args]

OUTPUT:
    [CODE001] descriere output
    [CODE002] ...

MODIFICARI: (read-only sau write)
    READ-ONLY: nu scrie nimic
    SAU
    WRITE: modifica X, Y, Z (cu backup + rollback)

ISTORIC:
    YYYY-MM-DD: initial - context / motiv
    YYYY-MM-DD: update - ce s-a schimbat
"""
```

TOOL_ID e numeric secvential (TOOL001, TOOL002, ...) pentru identificare
unica. Vezi lista TOOL_IDs la sfarsitul acestui document.

### 2. Debug codes standardizate

REGULA CHEIE: Orice log, warning sau error trebuie sa fie gasibil prin grep.
Toate mesajele critice folosesc format:

```python
print(f"[CATEGORIE NNN] short descr: detail", flush=True)
```

Exemple:
- `[SCAN001]` - scanner AST cod
- `[DB ERROR]` - eroare DB
- `[REQ ERROR]` - eroare request HTTP
- `[SEND ERROR]` - eroare pipeline send message
- `[KB000]` - knowledge base log
- `[SKILL010]` - generare skill automat
- `[WM ERROR]` - working_memory error
- `[FIX OK]` / `[FIX FAIL]` - status fix aplicat

Categoriile sunt libere - fiecare tool isi defineste categoriile sale in
docstring-ul de sus. Dar FORMATUL trebuie sa fie constant:
`[CATEGORIE NNN] text` sau `[COMPONENT-ERROR] text`.

Niciodata mesaje generice de tipul `"eroare"` sau `"am facut X"` fara marker.

### 3. Idempotenta - OBLIGATORIU pentru tools care scriu

Orice tool care modifica fisiere / DB / config TREBUIE sa fie idempotent:
rularea de 2 ori in aceleasi conditii nu face de 2 ori aceeasi modificare.

Pattern: folosesc un marker clar (comentariu in cod, tag in DB, fisier
sentinel) si verific marker-ul inainte sa modific. Daca e prezent, exit
[SKIP] fara eroare.

```python
MARKER = "@fix:nume-bug-YYYYMMDD"
if MARKER in content:
    print(f"[SKIP] marker {MARKER} deja prezent")
    sys.exit(0)
```

### 4. Backup + rollback pentru tools care modifica fisiere

Orice modificare pe disc TREBUIE:
1. Sa creeze backup cu timestamp: `fisier.bak.YYYYMMDD-HHMMSS`
2. Sa verifice syntax dupa modificare cu `python3.13 -m py_compile`
3. Sa fac rollback automat daca syntax fail
4. Sa afiseze clar comanda de rollback manual la final

```python
from datetime import datetime
import shutil, subprocess, sys

TS = datetime.now().strftime("%Y%m%d-%H%M%S")
backup = target.parent / f"{target.name}.bak.{TS}"
shutil.copy2(target, backup)
print(f"[BACKUP] {backup.name}")

# ... modificari ...
target.write_text(new_content)

# syntax check
r = subprocess.run(
    ["python3.13", "-m", "py_compile", str(target)],
    capture_output=True, text=True
)
if r.returncode != 0:
    print(f"[SYNTAX FAIL] {r.stderr}")
    print(f"[ROLLBACK] restoring {backup.name}")
    shutil.copy2(backup, target)
    sys.exit(3)
print(f"[SYNTAX OK]")

# la final
print(f"Rollback manual: cp {backup} {target}")
```

### 5. Read-only first, write second

Un tool care cititeste + analizeaza e mai sigur decat un tool care modifica.
Preferati read-only tools cand e posibil. Cand nu se poate, separati faza
de analiza (read) de faza de modificare (write), cu confirmare explicita
intre ele.

### 6. No hardcoded paths (relatv, dar cu fallback rezonabil)

Folositi Path("...") cu default la `/home/darkangel/.argos/argos-core/...`
(layout-ul ARGOS e fix). Daca exista alte locatii posibile, verificati cu
`.exists()` si aveti fallback la default.

### 7. Verificare dependente la inceput

Daca tool-ul are nevoie de un modul / container / serviciu (docker exec
argos-db, ssh root@hermes, connection to API), verificati disponibilitatea
la inceput si iesiti cu mesaj clar daca lipseste. Nu crash-uiti in mijloc.

### 8. Documentare in docstring

Docstring-ul de sus e sursa de adevar pentru ce face tool-ul. El trebuie
sa fie suficient ca un chat nou sau ARGOS sa inteleaga ce tool e fara sa
citeasca codul.

Secțiuni obligatorii in docstring:
- SCOP
- UTILIZARE (cu exemplu comanda)
- OUTPUT (ce debug codes afiseaza)
- MODIFICARI (read-only sau write + ce modifica)
- ISTORIC (versiuni in timp)

### 9. Exit codes clari

- 0: success
- 1: argumente invalide / precondition fail
- 2: pattern nu a fost gasit (fix-ul nu poate fi aplicat)
- 3: syntax fail dupa modificare
- 4: AST verification fail
- 5+: specific tool-ului, documentat in docstring

ARGOS (cand va automatiza tools) va folosi exit codes pentru a decide
urmatorii pasi.

### 10. No heredoc in docker exec, no sed multiline

Reguli fixe pentru ARGOS (din skill argos-core/argos-output-patterns):

- SQL multiline: `docker cp file.sql argos-db:/tmp/ && docker exec argos-db
  psql -f /tmp/file.sql` - NICIODATA heredoc cu docker exec
- Python file editing: read-modify-write cu `Path.read_text()` si
  `Path.write_text()` - NICIODATA sed pentru multiline
- Sir in Python: triple-quoted `'''...'''` pentru continut cu
  `"""..."""`, invers daca continut are `'''`

## LISTA TOOL_IDs (sa nu reutilizati)

| TOOL_ID | Nume                      | Data initial | Scop                                    |
|---------|---------------------------|--------------|-----------------------------------------|
| TOOL001 | scan_chat_structure.py    | 2026-04-13   | AST analyze chat.py send_message bugs   |

Adaugati TOOL_ID-ul urmator in lista cand creati un tool nou.

## EXEMPLE DE TOOLS VIITOARE PROPUSE

Pentru inspiratia chaturilor viitoare, iata idei de tools care ar fi utile:

- `db_schema_check.py` - verifica ca toate tabelele DB au coloanele asteptate
- `log_tail_filtered.py` - tail docker service logs cu filtre prebuilt
  (send errors, DB errors, specific conversation)
- `backup_cleanup.py` - arhiveaza backup-urile .bak.* mai vechi de N zile
- `skill_audit.py` - verifica integritatea skills_tree (duplicate, orfane,
  verified flag vs content)
- `vikunja_sync.py` - sync state ARGOS cu task-uri Vikunja bidirectional
- `haproxy_health.py` - verifica backend status HAProxy
- `conversation_sanity.py` - verifica ca nu exista tool_use orfan in
  format Anthropic API in conversations_messages cu content JSON

Unele vor deveni parte din workflow automat ARGOS in timp.

## REFERINTE

- Skill #90 argos-core/argos-self-knowledge - arhitectura ARGOS
- Skill #91 argos-core/argos-output-patterns - patternuri Python/SQL
- Skill #88 argos-deploy/argos-api-redeploy - cum se redeploy
- Task Vikunja #197 - ALPHA RELEASE CHECKLIST
- Task Vikunja #228 - Pause/Resume with urgency (context authorization
  care se leaga de tools automate)

## CHANGELOG acest STANDARD.md

- 2026-04-13: initial - creat in contextul fix tool_results orfan in
  chat.py. Primul tool adaugat: scan_chat_structure.py
