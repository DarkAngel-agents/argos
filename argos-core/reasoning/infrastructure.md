# ARGOS Infrastructure Reasoning
# Domain: Docker, Swarm, PostgreSQL, Proxmox, backups
# NEVER auto-modified. Edit manually only.

## DOCKER SWARM
- Leader: Hermes (11.11.11.98) - permanent, never change
- Worker: Beasty (11.11.11.111) - GPU node
- Stack deploy always from Leader: ssh root@11.11.11.98 'docker stack deploy ...'
- Never deploy stack from Beasty directly

## POSTGRESQL
- Primary: argos-db container on Beasty port 5432
- Standby: streaming replication on Hermes
- Access via HAProxy port 5433 on Hermes (always use this, not direct 5432)
- Credentials: claude / $DB_PASSWORD / claudedb
- SQL files via: docker cp file.sql argos-db:/tmp/ && docker exec argos-db psql -U claude -d claudedb -f /tmp/file.sql
- NEVER heredoc with docker exec, NEVER sed for multiline

## BACKUP
- Command: argos-backup (bash alias on Beasty)
- Location: ~/.argos/backups/
- Before ANY major change: run argos-backup first
- Last known good: argos-backup-20260329-2206

## PROXMOX
- LXC containers on Zeus node
- Debian 12 base for all new LXC
- Docker inside LXC: use --user 0:0 if uid namespace issues

## GITHUB
- Remote: git@github.com:DarkAngel-agents/argos.git (SSH only, never HTTPS)
- Push alias: argos-push
- Never push: credentials, Romanian text, private IPs in code

## ERROR PATTERN
STATUS: FAIL
CAUSE: container X not starting
ACTION: docker logs X --tail 50, check volume mounts, check port conflicts with ss -tlnp
