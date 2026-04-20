# AUDIT TASK 07 - Infrastructure investigation

Sesiune READ-ONLY pe ARGOS infrastructure. Obiectiv: stare reala docker swarm, postgres, haproxy, ollama, systemd, network. **Focus principal: Hermes heartbeat investigation** - de ce heartbeat_log are last entry 2026-04-08 si daca asta corelat cu agent session failure cluster id 6-9.

## REGULI STRICTE

1. **READ-ONLY.** Singurul fisier creat = raport MD.
2. **Zero comenzi adhoc.** Doar scriptul.
3. **Time budget: 12 min max.**
4. **STOP dupa DONE.** `/exit`.

## DIFFERENT FATA DE ALTE TASK-URI

Scriptul ruleaza **PE HOST Beasty**, NU in container. Foloseste local subprocess pentru docker, systemctl, ssh root@hermes, df, du, etc. Comanda de lansare e diferita.

## PASI

### Pas 1 - Ruleaza scriptul (DIRECT pe host, nu in container)

    python3 /home/darkangel/.argos/argos-core/tools/audit/scripts/07_infrastructure.py

NU `docker exec`! Direct python3.

Output: 20 sectiuni (7.1 - 7.20).

### Pas 2 - Nu faci alte comenzi.

### Pas 3 - Scrii raportul

Fisier: `/home/darkangel/.argos/argos-core/tools/audit/reports/07-infrastructure.md`

## SECTIUNI RAPORT

### Section 1: Rezumat executiv
3-5 propozitii. Stare swarm, replica health, postgres status, **VEREDICT principal despre Hermes heartbeat** (ipoteza din task 04: heartbeat dead 6 zile, posibila cauza session failure cluster).

### Section 2: Node identity
Copiezi sectiunea 7.1.

### Section 3: Docker basics
Copiezi sectiunea 7.2.

Severity:
- **[INFO]** swarm state = active si node ID prezent
- **[HIGH]** swarm state = inactive sau pending

### Section 4: Argos containers local
Copiezi sectiunea 7.3.

Severity per container:
- **[INFO]** Status = "Up X minutes/hours/days" (healthy)
- **[HIGH]** Status contine "Restarting" sau "unhealthy"
- **[CRITICAL]** Status = "Exited" sau missing

### Section 5: Swarm services via Hermes
Copiezi sectiunea 7.4.

Severity:
- **[CRITICAL]** SSH FAIL la Hermes (nu putem manage swarm)
- **[INFO]** Services listate cu replicas X/X

### Section 6: Swarm tasks for argos service
Copiezi sectiunea 7.5.

Severity:
- **[CRITICAL]** orice task in state "Rejected" sau "Failed"
- **[HIGH]** tasks "Shutdown" recente in mod neasteptat
- **[INFO]** tasks "Running" stable

### Section 7: Service constraints
Copiezi sectiunea 7.6.

### Section 8: PostgreSQL local
Copiezi sectiunea 7.7.

Severity:
- **[INFO]** version + size + connections normale
- **[HIGH]** connections > 50 (pool leak)

### Section 9: PostgreSQL replication
Copiezi sectiunea 7.8.

Severity:
- **[CRITICAL]** WAL config dezactivat (wal_level=minimal) cand era asteptat replication
- **[HIGH]** zero replication slots cand `argos_db_standby_active=true` in settings (confirmare task 04)
- **[INFO]** replication intentional dezactivat (consistent cu settings)

### Section 10: HAProxy
Copiezi sectiunea 7.9.

Severity:
- **[HIGH]** haproxy NOT active dar settings zice argos_db_access_via=haproxy:5433
- **[INFO]** haproxy active si listen pe port asteptat

### Section 11: Ollama instances
Copiezi sectiunea 7.10.

Severity per instance:
- **[INFO]** raspunde si are model qwen3:14b sau similar
- **[MEDIUM]** UNREACHABLE (poate nu e fol acum)
- **[HIGH]** UNREACHABLE dar settings zice local_enabled=true

### Section 12: Hermes connectivity
Copiezi sectiunea 7.11.

Severity:
- **[CRITICAL]** ping FAIL la Hermes (nod offline)
- **[CRITICAL]** SSH FAIL la Hermes
- **[INFO]** Hermes raspunde

### Section 13: HERMES HEARTBEAT INVESTIGATION (sectiune principala)
Copiezi sectiunea 7.12 INTEGRAL. Aceasta este cea mai importanta sectiune din raport.

ANALIZA OBLIGATORIE:
- Citeste output-ul systemctl status pentru argos-heartbeat.service
- Citeste journalctl ultime 20 entries
- Determina:
  - **Daca serviciul exista** (poate fi missing din systemd)
  - **Daca e activ** (active/inactive/failed)
  - **Daca e enabled** (auto start dupa reboot)
  - **Cand a rulat ultima data** (din journalctl)
  - **Ce eroare a aparut** (daca a esuat)

Severity in functie de ce gasesti:
- **[CRITICAL]** Service exista, e enabled, dar inactive/failed
- **[CRITICAL]** Service exista dar journalctl arata erori clare
- **[HIGH]** Service NU exista pe Hermes (deinstalat sau niciodata creat)
- **[HIGH]** Service activ dar nu mai scrie in DB (probabil DB connection broken)
- **[INFO]** Service e ok dar simplu nu rula in perioada respectiva (manual stop?)

VERDICT: **Confirmi sau infirmi ipoteza din task 04** ca heartbeat e cauza failure cluster.

### Section 14: Beasty heartbeat (control)
Copiezi sectiunea 7.13.

Comparatie cu Hermes - daca Beasty merge ok dar Hermes nu, asta confirma ca e problema DOAR pe Hermes.

### Section 15: All argos systemd units
Copiezi sectiunea 7.14.

Severity:
- **[INFO]** toate active
- **[HIGH]** orice unit failed

### Section 16: Disk usage
Copiezi sectiunea 7.15.

Severity:
- **[CRITICAL]** > 90% pe partitii critice
- **[HIGH]** > 80%
- **[MEDIUM]** > 70%
- **[INFO]** sub 70%

### Section 17: Network connectivity to nodes
Copiezi sectiunea 7.16.

Severity:
- **[CRITICAL]** Hermes FAIL
- **[HIGH]** Vikunja, Zeus, sau alte servicii FAIL
- **[INFO]** toate OK

### Section 18: Listening ports
Copiezi sectiunea 7.17.

Verifica daca porturile asteptate sunt prezente:
- 666 (argos UI)
- 5433 (postgres via HAProxy)
- 11434/11435 (ollama)
- 5000 (registry)

### Section 19: DB heartbeat age cross-ref
Copiezi sectiunea 7.18.

Comparatie cu task 04 (acolo am vazut Hermes 6 zile vechi). Acum ar trebui sa fie aceeasi situatie SAU Hermes are entries noi (in cazul in care daemon-ul a fost restartat).

### Section 20: Recent journalctl errors
Copiezi sectiunea 7.19.

Severity:
- **[INFO]** zero erori in ultima ora
- **[MEDIUM]** < 20 errors
- **[HIGH]** > 20 errors (ceva e rupt acum)

### Section 21: Argos state settings
Copiezi sectiunea 7.20.

Cross-ref cu realitatea verificata in sectiunile anterioare:
- argos_beasty_active=true → confirmat by 7.4 daca Beasty are tasks Running
- argos_hermes_active=true → CONFLICT daca Hermes nu raspunde
- argos_heartbeat_daemon_hermes=true → CONFLICT daca service nu ruleaza

Marker [CRITICAL] pentru fiecare conflict descoperit.

### Section 22: Top 15 findings cross-cutting
Sortat CRITICAL -> HIGH -> MEDIUM -> LOW -> INFO.

ATENTIE LA URMATOARELE FINDINGS ASTEPTATE:
- Hermes heartbeat status (CRITICAL daca confirmi ipoteza)
- Conflict settings vs realitate (CRITICAL)
- Replication intentional dezactivat vs settings inconsistente

### Section 23: Observatii colaterale
Markere [FOR-TASK-N] sau [FOR-TASK-99 SYNTHESIS]:
- Cross-cutting issues care apar in mai multe rapoarte
- Probleme de design care nu sunt scope-ul task 07 dar le-ai observat

### Section 24: VERDICT FINAL ipoteza task 04+05
Sectiune speciala. Raspunde direct la intrebarea:

> "Este Hermes heartbeat dead cauza failure cluster sessions id 6-9 din task 05?"

Optiuni:
- **CONFIRMED** - Hermes daemon e oprit/eronat, sessions failed in aceeasi perioada
- **PARTIALLY CONFIRMED** - Hermes are probleme dar nu suficient sa explice toate failures
- **REJECTED** - Hermes e ok, alta cauza pentru session failures
- **UNCLEAR** - nu se poate determina din datele scriptului

Justificare scurta cu evidence concret.

### Section 25: Recomandari prioritare
Top 5 actiuni concrete pentru infrastructure.

### Section 26: Metadata
- Timp rulare
- Comanda
- Linii output
- Erori

## PASUL 4 - DONE

    echo "DONE TASK 07"
    wc -l /home/darkangel/.argos/argos-core/tools/audit/reports/07-infrastructure.md

## STOP

Dupa DONE, `/exit`. NU continui cu task 08.

## SUCCES

- Toate sectiunile 1-26 prezente
- Section 13 (Hermes investigation) detaliata
- Section 24 (VERDICT) cu evidence concret
- Severity markers consecvent
- Cross-references cu task 04 si 05

## ESEC

- Lipseste section 13 sau 24
- Verdict ambiguu fara evidence
- Reasoning > 3 minute
- Comenzi adhoc rulate
