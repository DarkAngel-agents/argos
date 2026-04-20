# AUDIT TASK 08 - Skills system deep audit

Sesiune READ-ONLY pe ARGOS DB + cod. Obiectiv: analiza profunda skills_tree (110 skills), tabela legacy `skills`, content quality, skill loading flow in chat.py si prompts.py, cross-reference skills referenced in code vs DB.

## REGULI STRICTE

1. **READ-ONLY.**
2. **Zero comenzi adhoc.**
3. **Time budget: 12 min max.**
4. **STOP dupa DONE.** `/exit`.

## PASI

### Pas 1 - Ruleaza scriptul

    CONT=$(docker ps -q -f name=argos | head -1)
    docker exec $CONT python3 /home/darkangel/.argos/argos-core/tools/audit/scripts/08_skills_system.py

Output: 15 sectiuni (8.1 - 8.15), probabil 400-600 linii.

### Pas 2 - Nu faci alte comenzi.

### Pas 3 - Scrii raportul

Fisier: `/home/darkangel/.argos/argos-core/tools/audit/reports/08-skills-system.md`

## SECTIUNI RAPORT

### Section 1: Rezumat executiv
3-5 propozitii. Numar total skills, distribution length, cati stubs, cati never updated, observatie principala.

### Section 2: skills_tree overview
Copiezi sectiunea 8.1.

### Section 3: Length distribution
Copiezi sectiunea 8.2 - histograma in buckets.

Severity:
- **[INFO]** distributie sanatoasa (multe skills 500-3000 chars)
- **[MEDIUM]** > 15% stubs (skills < 300 chars)
- **[HIGH]** > 25% stubs

### Section 4: Stubs detail
Copiezi sectiunea 8.3 - lista detaliata stubs cu preview content.

ANALIZA per stub:
- **[LOW]** Stub care e PLACEHOLDER intentional (ex: "TODO: document this")
- **[MEDIUM]** Stub care pare INCOMPLET (incepe cu titlu si comand singura, fara explicatie)
- **[HIGH]** Stub care e GRESIT sau LIPSA INFO critica

Pentru fiecare stub identifica categoria.

### Section 5: Never updated
Copiezi sectiunea 8.4.

Severity:
- **[MEDIUM]** > 10 skills never updated (lipsa trigger update_at sau insert fara UPDATE)
- **[INFO]** putine si recente (acceptabil daca e creat azi)

Note: `updated_at IS NULL` poate fi cauzat fie de:
1. Skill creat fara trigger care seteaza updated_at
2. Trigger exista dar nu e fired la INSERT
3. Bug in scriptul de insert

### Section 6: Emergency skills
Copiezi sectiunea 8.5.

ANALIZA: Sunt skill-urile critice "always loaded" + acoperite + actualizate?

Severity:
- **[HIGH]** orice emergency skill cu updated_at NULL
- **[MEDIUM]** orice emergency skill < 500 chars (prea scurt pentru ceva critic)
- **[INFO]** emergency skills mari si recent updated

### Section 7: Top largest skills
Copiezi sectiunea 8.6.

Severity:
- **[INFO]** skills mari sunt acceptabile pentru self-knowledge / protocol
- **[MEDIUM]** orice skill > 20000 chars (prea mare, posibil de impartit)

### Section 8: Recently updated
Copiezi sectiunea 8.7. Activitate ultimele 7 zile.

### Section 9: Legacy skills table
Copiezi sectiunea 8.8 - tabela `skills` separata de `skills_tree`.

ANALIZA:
- Sunt cele 25 rows din tabela legacy migrate sau orfane?
- Apar in `skills_tree` sau sunt complet separate?

Severity:
- **[HIGH]** tabela `skills` activa cu rows ne-migrate in `skills_tree`
- **[MEDIUM]** tabela legacy abandoned dar nu sterssa
- **[INFO]** tabela goala sau migrare clara

### Section 10: Content patterns
Copiezi sectiunea 8.9. Cati au cod, headers, refs.

Severity:
- **[INFO]** majoritatea structurate
- **[MEDIUM]** > 50% lipsa code blocks (prea generale)

### Section 11: Categories
Copiezi sectiunea 8.10.

Per categorie:
- **[MEDIUM]** categorie cu > 50% never_updated
- **[HIGH]** categorie cu < 200 avg length (stubs cluster)

### Section 12: Skill loading in chat.py
Copiezi sectiunea 8.11:
- Functii skill-related
- DB queries pe skills_tree
- Hardcoded skill references

Severity:
- **[MEDIUM]** > 5 hardcoded skill #N references in cod
- **[HIGH]** queries pe skills_tree fara ORDER BY priority/score
- **[CRITICAL]** orice INSERT/UPDATE pe skills_tree din chat.py (skills should be managed elsewhere)

### Section 13: Skill loading in prompts.py
Copiezi sectiunea 8.12.

Verificari:
- Functii _select_dynamic_skills, _load_fixed_skills, _score_skill (din task 05) sunt acolo
- Cum citesc din DB
- Au logica de scoring

### Section 14: Skills referenced in code vs DB
Copiezi sectiunea 8.13. Lista completa skill IDs referenced + status.

Severity per missing:
- **[CRITICAL]** skill referenced in cod care nu exista in DB - bug

### Section 15: Skill creation protocol (#93)
Copiezi sectiunea 8.14 - skill #93 meta-skill content preview.

ANALIZA: Protocol clar definit? Are pasi concreti?

### Section 16: Skill settings
Copiezi sectiunea 8.15 - flags `skills_*` din settings.

Severity:
- **[INFO]** consistent cu observed behavior
- **[MEDIUM]** flags care nu se reflecta in cod (dead settings)

### Section 17: Top 15 findings cross-cutting
Sortat CRITICAL -> HIGH -> MEDIUM -> LOW -> INFO.

ATENTIE LA URMATOARELE FINDINGS ASTEPTATE:
- 11 stubs (din task 04) - acum cu detail
- 12 never updated (din task 04) - acum cu cauze posibile
- 1 huge skill (#90 self-knowledge ~22k chars)
- Legacy table `skills` (25 rows) - status unknown
- Skills referenced in cod care exista/lipsesc

### Section 18: Observatii colaterale
Markeri [FOR-TASK-99 SYNTHESIS]:
- Pattern cross-cutting cu rapoartele anterioare
- Probleme arhitecturale care apar peste tot

### Section 19: Recomandari prioritare
Top 5 actiuni concrete pe skills:

Exemplu:
    1. Expand stubs prioritare (debian-haproxy-setup 30 chars, etc)
    2. Run trigger update_at pe cele 12 skills never_updated
    3. Investigate legacy 'skills' table - migrate or drop
    4. Refactor #90 (22k chars) in 2-3 skills mai mici
    5. Add skill loading metrics (hit rate, latency)

### Section 20: Metadata

## PASUL 4 - DONE

    echo "DONE TASK 08"
    wc -l /home/darkangel/.argos/argos-core/tools/audit/reports/08-skills-system.md

## STOP

Dupa DONE, `/exit`.
