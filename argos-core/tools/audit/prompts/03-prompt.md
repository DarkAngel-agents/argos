# AUDIT TASK 03 - Security & credentials

Sesiune de audit READ-ONLY pe ARGOS. Obiectiv: scan pentru expunere credentiale, permisiuni fisiere sensibile, patterns nesigure (shell=True, eval, backups cu secrete).

## REGULI STRICTE

1. **READ-ONLY.** Nu modifici nimic, nu schimbi permisiuni, nu muti fisiere. Singurul fisier pe care il creezi este raportul MD.
2. **Zero bash adhoc.** O singura comanda rulezi (scriptul de recon). Nu mai cauti alte chestii in cod.
3. **NICIODATA nu afisezi valori reale de credentiale.** Scriptul le masca automat, tu nu le include nici in raport nici in output.
4. **Zero reasoning lung.** Ruleaza scriptul, copiaza in raport, aplica severity, gata.
5. **Time budget: 10 minute max.**
6. **STOP dupa ce scrii fisierul.** Nu continui cu task 04. Dupa DONE, `/exit`.

## PASI

### Pas 1 - Ruleaza scriptul de recon

    CONT=$(docker ps -q -f name=argos | head -1)
    docker exec $CONT python3 /home/darkangel/.argos/argos-core/tools/audit/scripts/03_security_audit.py

Output-ul are ~150-250 linii cu 11 sectiuni (3.1 - 3.11). Citeste tot.

### Pas 2 - Nu faci alte comenzi

Scriptul iti da tot. Nu deschizi fisiere, nu faci grep, nu executi find suplimentar.

### Pas 3 - Scrii raportul

Fisier target: `/home/darkangel/.argos/argos-core/tools/audit/reports/03-security-audit.md`

## SECTIUNI RAPORT

### Section 1: Rezumat executiv
3-5 propozitii. Cate probleme CRITICAL, HIGH, MEDIUM ai gasit. Una-doua cele mai grave. Impresie generala: e ARGOS in regula security-wise sau nu?

### Section 2: Scope
Copiezi datele din output sectiunea 3.1: cate fisiere scanate, subdirs, argos root.

### Section 3: Credential patterns in source code
Copiezi sectiunea 3.2 din output. 

IMPORTANT: Daca au fost detectate patterns Anthropic/xAI/GitHub keys in .py files, marchezi:
- **[CRITICAL]** per fisier cu credential hardcoded in cod Python

NU scrii valoarea. Doar: "file X, line Y, pattern Z detected".

Daca scriptul zice [NONE]: "No credential patterns in source code - CONFIRMED [INFO]"

### Section 4: Hardcoded password/secret assignments  
Copiezi sectiunea 3.3 din output.

Pentru fiecare finding:
- Daca foloseste `getenv`/`environ` fallback = e OK (scriptul filtreaza oricum)
- Daca e hardcoded literal = **[CRITICAL]**
- Daca e in fisier de test sau exemplu = **[LOW]**

### Section 5: Logging leak potential
Copiezi sectiunea 3.4 din output.

Pentru fiecare print/log ce mentioneaza password/token/secret/api_key:
- **[HIGH]** daca afiseaza direct variabila credentialului
- **[MEDIUM]** daca e in context ambiguu (ex: debug log cu "password check failed")
- **[LOW]** daca e doar mesaj generic

### Section 6: Sensitive files on disk
Copiezi sectiunea 3.5 din output.

Pentru fiecare fisier listat:
- Marker pe baza mode/permisiuni (scriptul ti-l spune deja in output)
- **[CRITICAL]** world-writable
- **[HIGH]** world-readable private file
- **[MEDIUM]** mode non-strict (nu 600/400)
- **[INFO]** mode corect (600 sau 400)

### Section 7: config/.env specific
Copiezi sectiunea 3.6 din output.

Foarte important:
- **[CRITICAL]** daca mode != 600 si contine API keys
- **[HIGH]** daca exista duplicate .env la argos-core/ root (in afara de config/.env)
- Lista keys definite (NU valorile) - doar numele variabilelor

### Section 8: Backup files
Copiezi sectiunea 3.7 din output.

- **[HIGH]** orice .env.bak* gasit (acestea sunt probleme reale - backup-uri cu credentiale vechi)
- **[MEDIUM]** orice .bak de cod care ar putea contine comentarii/strings sensibile
- **[LOW]** alte backups

### Section 9: SSH keys
Copiezi sectiunea 3.8 din output.

- **[CRITICAL]** private key (id_rsa, id_ed25519 etc.) cu mode incorect
- **[CRITICAL]** private key world-readable
- **[INFO]** keys cu permisiuni corecte (600)

### Section 10: Git repo
Copiezi sectiunea 3.9 din output.

- **[CRITICAL]** daca .env NU e in .gitignore (risc commit accidental)
- **[HIGH]** daca nu exista .gitignore deloc
- **[INFO]** daca toate sunt ok

### Section 11: Dangerous subprocess patterns
Copiezi sectiunea 3.10 din output (shell=True).

- **[HIGH]** pentru fiecare shell=True cu variabila user (f-string sau concatenare)
- **[MEDIUM]** shell=True cu string literal hardcoded
- **[INFO]** daca zero usage

### Section 12: eval/exec usage
Copiezi sectiunea 3.11 din output.

- **[HIGH]** eval() sau exec() cu input user
- **[MEDIUM]** eval/exec cu string literal (mai putin periculos dar cod smell)
- **[INFO]** daca zero usage

### Section 13: Top findings cross-cutting
Top 10 gasite, ordonate CRITICAL -> HIGH -> MEDIUM -> LOW -> INFO. Format:

    1. [CRITICAL] config/.env is world-readable - fix: chmod 600
    2. [HIGH] .env.bak-20260414-1200 contains old credentials
    3. [HIGH] api/backup.py L159 hardcoded IP in SSH connect
    ...

Daca ai mai putin de 10, lasa cat ai.

### Section 14: Observatii colaterale
Lucruri pe care le-ai vazut dar nu sunt in scope. Marcheaza [FOR-TASK-N] pentru task-urile urmatoare:
- [FOR-TASK-4 DATABASE] daca ai vazut parole DB in code
- [FOR-TASK-5 AGENT LOOP] daca ai vazut credentiale in prompts
- [FOR-TASK-7 INFRASTRUCTURE] daca ai vazut issues de network/swarm

Maximum 8 bullets.

### Section 15: Recomandari prioritare
Top 5 actiuni de facut imediat (nu acum, in faze viitoare). Format scurt, actionabil.

Exemplu:
    1. Roteste toate credentialele expuse public in chat-urile de debug
    2. Muta .env in Docker secrets (swarm secrets)
    3. chmod 600 pe config/.env si .env.bak
    4. Adauga .env in .gitignore daca lipseste
    5. Sterge .env duplicate in argos-core/ root

### Section 16: Metadata
- Timp rulare
- Comanda rulata
- Linii output script
- Erori (daca vreuna)

## PASUL 4 - DONE

Dupa ce ai scris fisierul:

    echo "DONE TASK 03"
    wc -l /home/darkangel/.argos/argos-core/tools/audit/reports/03-security-audit.md

## STOP

Dupa DONE te opresti. NU continui cu task 04. NU deschizi tangente. STOP. `/exit` sau astepti urmatorul prompt.

## SUCCES

- Fisierul MD exista
- Toate sectiunile 1-16 sunt prezente
- Severity markers aplicate per item
- NICIO valoare reala de credential in raport (doar pattern names si masks)
- Section 13 are findings sortate corect
- Nu ai modificat nimic
- Nu ai rulat comenzi extra

## ESEC

- Lipseste raportul
- Ai inclus valori reale de credentiale in raport
- Ai modificat permisiuni sau fisiere
- Ai intrat in reasoning > 3 minute
- Ai rulat find/grep/cat ad-hoc in loc de scriptul dat
