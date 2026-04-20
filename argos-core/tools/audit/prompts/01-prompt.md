# AUDIT TASK 01 - Self-knowledge vs Reality

Esti intr-o sesiune de audit READ-ONLY pentru sistemul ARGOS. Obiectivul: verifica daca skill-urile de self-knowledge ale ARGOS (id 90, 91, 92, 93) reflecta realitatea actuala a sistemului.

## REGULI STRICTE

1. READ-ONLY. Nu modifici absolut nimic. Nu rulezi UPDATE/INSERT/DELETE/CREATE. Nu modifici fisiere. Nu repornesti servicii. Singurul fisier pe care il CREEZI este raportul MD final.

2. Zero bash adhoc. Nu inventezi comenzi. Folosesti STRICT scripturile pre-scrise din /home/darkangel/.argos/argos-core/tools/audit/scripts/ sau comenzile listate explicit in acest prompt.

3. Zero investigatie dincolo de scope. Daca gasesti ceva interesant in alta arie, il notezi scurt in sectiunea "Observatii colaterale" si continui. Nu deschizi tangente.

4. Time budget. Maximum 15 minute pentru tot task-ul. Daca dureaza mai mult, scrii ce ai si pleci.

5. Fara gandire excesiva. Nu sta 30 de minute intr-un reasoning block. Actioneaza, citeste, scrie, next.

## CE FACI - pasi concreti

### Pas 1 - Ruleaza scriptul de recon (odata, nu de mai multe ori)

Comanda:
    cd /home/darkangel/.argos/argos-core
    CONT=$(docker ps -q -f name=argos | head -1)
    docker exec $CONT python3 /home/darkangel/.argos/argos-core/tools/audit/scripts/01_load_skills_reality.py

Output-ul este text structurat cu sectiuni 1.1 pana la 3.1. Citeste tot.

### Pas 2 - Ruleaza verificarile Docker de pe host

Pe Beasty direct:
    docker ps --filter name=argos --format "{{.Names}} {{.Status}} {{.Ports}}"
    docker images --filter reference=*argos* --format "{{.Repository}}:{{.Tag}} {{.Size}}"

Pe Hermes (swarm manager):
    ssh root@11.11.11.98 "docker service ls | grep argos"
    ssh root@11.11.11.98 "docker service ps argos-swarm_argos --no-trunc | head -10"

### Pas 3 - Citeste skill-ul argos-self-knowledge COMPLET din DB

Scriptul iti arata primele 3000 chars. Vrei tot. Ruleaza un docker exec python3 intr-un fisier temp /tmp/read_skill_90.py care conecteaza asyncpg la host=11.11.11.111 port=5433 user=claude password=$DB_PASSWORD database=claudedb, face SELECT content FROM skills_tree WHERE id = 90, printeaza rezultatul. Dupa il rulezi cu docker cp + docker exec.

Citeste cu atentie ce declara skill-ul despre:
- Noduri fizice (Beasty, Hermes, Zeus)
- Unde traieste codul
- DB schema + tabele
- Paths fisiere cheie
- Docker setup

### Pas 4 - Verifica punct cu punct ce zice skill-ul vs realitate

Pentru fiecare afirmatie in skill #90, stabileste una din:
- CONFIRMED - skill-ul si realitatea se potrivesc
- STALE - skill-ul e outdated (fisier mutat, path schimbat, setting diferit)
- WRONG - skill-ul e complet gresit
- UNVERIFIABLE - nu poti verifica din scriptul de recon

Scriptul a aratat deja cateva discrepante clare:
- Skill-ul pomeneste /home/darkangel/.argos/docker/swarm-stack.yml - scriptul raporteaza MISSING
- Skill-ul pomeneste /home/darkangel/.argos/docker/Dockerfile - scriptul raporteaza MISSING

Aprofundezi pe astea. Gasesti unde SUNT de fapt:
    find /home/darkangel -name "swarm-stack*" -o -name "Dockerfile*" 2>/dev/null

### Pas 5 - Scrii raportul

Fisier: /home/darkangel/.argos/argos-core/tools/audit/reports/01-self-knowledge-vs-reality.md

Sectiuni OBLIGATORII:

Section 1: Rezumat executiv (3-5 propozitii)
Section 2: Skill-uri verificate (cate un subcapitol per skill 90, 91, 92, 93 cu dimensiune, data update, verdict general CONFIRMED/STALE/BROKEN)
Section 3: Discrepante detectate (D1, D2, D3... fiecare cu: Severity CRITICAL/HIGH/MEDIUM/LOW, Skill id, Ce zice skill-ul, Ce e in realitate, Impact, Fix sugerat)
Section 4: Confirmari (lista scurta cu ce e corect, cel putin 5 itemi)
Section 5: Observatii colaterale (max 10 bullets, cu marker [FOR-TASK-N] unde N e task-ul care ar trebui sa le aprofundeze)
Section 6: Propuneri update skill (ce sectiuni din skill ai rescrie concret)
Section 7: Metadata (timp rulare, comenzi rulate, erori intampinate)

### Pas 6 - Afiseaza in terminal

    echo "DONE - report scris"
    wc -l /home/darkangel/.argos/argos-core/tools/audit/reports/01-self-knowledge-vs-reality.md

Apoi STOP. Nu continui cu alte task-uri. Nu deschizi tangente. Task 01 DONE.

## SUCCES vs ESEC

SUCCES:
- Fisierul MD exista si are 200-500 linii
- Toate sectiunile 1-7 sunt prezente
- Discrepantele cunoscute (swarm-stack.yml, Dockerfile MISSING) sunt captate
- Cel putin 3 discrepante notate
- Confirmari cel putin 5 itemi
- Nu ai modificat nimic din sistem

ESEC:
- Lipseste fisierul MD
- Lipseste o sectiune
- Ai modificat fisiere/DB/servicii
- Ai rulat 50 de bash commands ad-hoc
- Ai petrecut ore intr-un reasoning block
- Ai inceput task 02 fara instructiuni
