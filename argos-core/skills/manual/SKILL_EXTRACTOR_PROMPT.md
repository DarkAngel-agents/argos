# ARGOS SKILL EXTRACTOR PROMPT

You are helping extract verified skills from this conversation to save for ARGOS (Autonomous Resilient Guardian Orchestration System).

## YOUR TASK
1. Read the entire conversation
2. Extract ALL commands/procedures that were verified as working (confirmed with OK, success output, or explicit confirmation)
3. Group them logically into skill blocks
4. Write a single .argosdb file

## OUTPUT FILE
Save to: /home/darkangel/.argos/argos-core/skills/import/import_YYYYMMDD_HHMM.argosdb
(replace YYYYMMDD_HHMM with current date/time)

## FILE FORMAT
Each skill block is separated by ---SKILL---
Keep it simple — ARGOS will decide path/tags/categorization at import time.
```
---SKILL---
title: Short descriptive title in English
context: One line describing when this is useful
content: |
  # verified commands only, with brief comments
  command1
  command2
  # gotcha or note if relevant
---SKILL---
title: Next skill title
context: When to use this
content: |
  command1
  command2
```

## RULES
- English only
- Only include commands that produced successful output in this conversation
- Do NOT include commands that failed or were replaced by better alternatives
- Do NOT include debugging/investigation commands unless they are part of a procedure
- Each skill should be atomic — one specific task
- Minimum 2 commands per skill, maximum 20
- Add brief comments for non-obvious commands
- If a procedure has gotchas discovered in this conversation, include them as comments
- You can create 1 to 20 skills from a single conversation

## SAVE COMMAND
```bash
mkdir -p /home/darkangel/.argos/argos-core/skills/import
cat > /home/darkangel/.argos/argos-core/skills/import/import_YYYYMMDD_HHMM.argosdb << 'EOF'
---SKILL---
title: ...
...
EOF
```

## VERIFY
```bash
ls -la /home/darkangel/.argos/argos-core/skills/import/
cat /home/darkangel/.argos/argos-core/skills/import/import_YYYYMMDD_HHMM.argosdb
```
