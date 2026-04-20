# ARGOS SKILL CREATOR PROMPT
# Use this prompt in any Claude chat to create manual sub-skills for ARGOS

---

You are helping create a manual sub-skill for ARGOS (Autonomous Resilient Guardian Orchestration System).
Owner: DarkAngel.

## YOUR TASK
Based on the current conversation context, create a YAML sub-skill file and save it to:
/home/darkangel/.argos/argos-core/skills/manual/

## RULES
- NEVER overwrite existing files — always generate a new unique 8-digit ID
- Check if file exists before writing
- ID must be 8 digits, random, unique (generate randomly, verify not in use)
- path uses / as separator, lowercase, no spaces (e.g. docker/postgres/restart)
- tags: lowercase, relevant keywords only, minimum 3
- emergency: true only if skill is needed when DB is unavailable
- source: always "manual" for skills created this way
- content: in English, concise, only verified commands from current conversation
- Do NOT include commands that failed or were not tested

## FILE FORMAT (YAML)
```yaml
id: 47392816
path: category/subcategory/specific-task
parent_path: category/subcategory
name: Short descriptive name
tags: [tag1, tag2, tag3]
source: manual
emergency: false
usage_count: 0
content: |
  # verified commands only
  command1
  command2
  # notes about gotchas
```

## SAVE COMMAND
After creating the YAML content, save it with:
```bash
cat > /home/darkangel/.argos/argos-core/skills/manual/<id>_<slug>.yaml << 'SKILL'
<yaml content>
SKILL
```
Where slug = path with / replaced by _ (e.g. docker_postgres_restart)

## VERIFY
After saving:
```bash
ls -la /home/darkangel/.argos/argos-core/skills/manual/
cat /home/darkangel/.argos/argos-core/skills/manual/<filename>
```

## WHAT TO EXTRACT
Look at the current conversation and extract:
- Commands that worked (exit 0, explicit success confirmation)
- Gotchas discovered during the session
- Config snippets that were applied successfully
- Procedures that were tested end-to-end

## WHAT TO SKIP
- Commands that failed
- Workarounds that were later replaced
- Temporary debug commands
- Anything not verified in this conversation

## EXAMPLE
If conversation was about restarting PostgreSQL in Docker:
```yaml
id: 83920471
path: docker/postgres/restart
parent_path: docker/postgres
name: Restart PostgreSQL container and verify
tags: [docker, postgres, restart, database, health]
source: manual
emergency: false
usage_count: 0
content: |
  # Restart postgres container
  docker restart argos-db
  # Verify it is up
  docker exec argos-db pg_isready -U claude -d claudedb
  # If restart fails, stop and start:
  docker stop argos-db && docker start argos-db
  # Check logs if still failing:
  docker logs argos-db --tail 20
```
