# AUDIT TASK 06 - API endpoints + middleware deep dive

Sesiune READ-ONLY. Obiectiv: inventariere completa endpoints FastAPI, middleware, error handling, dependinte cross-module, focus pe chat.py si main.py. Plus aprofundarea markerilor [FOR-TASK-6] din rapoartele 02 si 05.

## REGULI STRICTE

1. **READ-ONLY.** Singurul fisier creat = raport MD.
2. **Zero comenzi adhoc.** Doar scriptul.
3. **Zero reasoning lung.**
4. **Time budget: 12 min max.**
5. **STOP dupa DONE.** `/exit`.

## PASI

### Pas 1 - Ruleaza scriptul

    CONT=$(docker ps -q -f name=argos | head -1)
    docker exec $CONT python3 /home/darkangel/.argos/argos-core/tools/audit/scripts/06_api_endpoints.py

Output: 14 sectiuni (6.1 - 6.14), probabil 400-700 linii.

### Pas 2 - Nu faci alte comenzi.

### Pas 3 - Scrii raportul

Fisier: `/home/darkangel/.argos/argos-core/tools/audit/reports/06-api-endpoints.md`

## SECTIUNI RAPORT

### Section 1: Rezumat executiv
3-5 propozitii. Numar total endpoints, top file cu cele mai multe, distribution methods, middleware count, observatie principala despre design.

### Section 2: Files overview (api/)
Copiezi sectiunea 6.1 ca tabel sortat dupa lines descrescator.

Severity per file:
- **[CRITICAL]** > 1500 linii (chat.py se incadreaza)
- **[HIGH]** 500-1500 linii
- **[MEDIUM]** 200-500 linii  
- **[LOW]** sub 200 linii

### Section 3: Endpoints inventory
Copiezi sectiunea 6.2:
- Total endpoints
- Distribution by HTTP method
- Lista per fisier cu method + path + func

Severity:
- **[INFO]** structura clara
- **[MEDIUM]** > 50 endpoints in chat.py (centralizare excesiva)
- **[HIGH]** > 100 endpoints intr-un singur file

### Section 4: Middleware stack
Copiezi sectiunea 6.3.

Severity:
- **[INFO]** middleware-uri prezente (catch_db_errors, etc)
- **[MEDIUM]** zero middleware (lipsa global error handler)
- **[HIGH]** middleware care suprascriu silentios erorile

### Section 5: Router includes
Copiezi sectiunea 6.4. Lista routers inclusi in main app.

Severity:
- **[INFO]** modular cu router includes
- **[MEDIUM]** totul intr-un singur main.py

### Section 6: Pydantic models
Copiezi sectiunea 6.5:
- Lista per fisier
- Total models

Severity: **[INFO]** la nivel de design

### Section 7: HTTPException usage
Copiezi sectiunea 6.6:
- Distribution by status code
- Per file count

Severity:
- **[INFO]** distributie normala (400/404/500 dominante)
- **[MEDIUM]** mult 500 (errors generic in loc de specific)
- **[HIGH]** zero HTTPException intr-un fisier mare (lipsa error handling)

### Section 8: Authentication / Authorization
Copiezi sectiunea 6.7.

Severity:
- **[CRITICAL]** zero auth patterns in api/ (toate endpoints publice)
- **[HIGH]** doar 1-2 fisiere folosesc Depends/auth
- **[INFO]** auth pe majoritatea endpoint-urilor

### Section 9: CORS
Copiezi sectiunea 6.8.

Severity:
- **[CRITICAL]** allow_origins=["*"] (deschis catre tot internetul)
- **[HIGH]** lipseste CORS deloc daca UI e separat
- **[INFO]** CORS configurat cu origins specifice

### Section 10: chat.py deep
Copiezi sectiunea 6.9:
- Total lines
- Top 15 functions sorted by length
- Anthropic call sites
- DB access count

Pentru top functions:
- **[CRITICAL]** > 300 linii
- **[HIGH]** 200-300
- **[MEDIUM]** 100-200

Pentru Anthropic calls:
- **[INFO]** Anthropic SDK folosit clean (un singur point de instantiere)
- **[MEDIUM]** instantiere multipla a clientului per request

### Section 11: main.py lifespan
Copiezi sectiunea 6.10:
- Total lines
- Lifecycle functions
- DB pool init
- Globals

Severity:
- **[INFO]** lifespan structurat cu pool init
- **[MEDIUM]** > 5 globals (state management slab)
- **[HIGH]** zero lifespan (no startup hook)

### Section 12: Streaming endpoints
Copiezi sectiunea 6.11.

Severity: **[INFO]** SSE folosit (modern UI pattern)

### Section 13: Cross-module dependencies
Copiezi sectiunea 6.12. Care fisiere api/ importa din agent/llm/tools/reasoning.

Severity:
- **[INFO]** dependinte clare si limitate
- **[MEDIUM]** chat.py importa din toate modulele (god file)

### Section 14: executor.py + backup.py + code_runner.py
Copiezi sectiunea 6.13. Functions per file.

Severity per file:
- Aprobi observatiile din task 02 si 03 despre IPs hardcoded SSH

### Section 15: Endpoint complexity summary
Copiezi sectiunea 6.14.

### Section 16: Top 15 findings cross-cutting
Sortate CRITICAL -> HIGH -> MEDIUM -> LOW -> INFO.

ATENTIE LA URMATOARELE FINDINGS ASTEPTATE:
- chat.py 1550+ linii (CRITICAL)
- send_message 336 linii (HIGH din task 02)  
- _execute_tool 271 linii (HIGH din task 02)
- Lipsa auth patterns probabil pe majoritatea endpoints (CRITICAL daca asa e)
- 8 bare exceptions in chat.py (HIGH din task 02 - daca apar in DB queries de-aici)

Format:
    1. [CRITICAL] api/chat.py = 1550 lines, 18+ functions - urgent decompose
    2. [CRITICAL] zero auth on all endpoints - exposed API
    3. [HIGH] send_message() = 336 lines mixing LLM call + tool dispatch + DB write
    ...

### Section 17: Observatii colaterale
Markeri [FOR-TASK-N]:
- [FOR-TASK-7 INFRASTRUCTURE] daca observi probleme legate de SSH/network in api/
- [FOR-TASK-8 SKILLS] daca observi referinte hardcoded skills
- [FOR-TASK-9 UI] daca observi cuplaj prea strans cu UI specific
- [FOR-TASK-99 SYNTHESIS] cross-cutting issues care apar in mai multe rapoarte

### Section 18: Recomandari prioritare
Top 5 actiuni concrete:

Exemplu:
    1. Decompose chat.py prin extragere modules: chat_send.py, chat_tools.py, chat_compress.py
    2. Add minimal auth middleware (API key in header) before exposing externally
    3. Refactor send_message in 4-5 functii: build_messages, call_llm, dispatch_tool, save_message
    4. Restrict CORS allow_origins din wildcard daca e cazul
    5. Move SSH operations from api/backup.py si api/code_runner.py to dedicated executor module

### Section 19: Metadata
- Timp rulare
- Comanda
- Linii output
- Erori

## PASUL 4 - DONE

    echo "DONE TASK 06"
    wc -l /home/darkangel/.argos/argos-core/tools/audit/reports/06-api-endpoints.md

## STOP

Dupa DONE, `/exit`. NU continui cu task 07.
