# argos-infrastructure
version: 5.0
os: any
loaded_when: any task related to ARGOS system, infrastructure status, failover, replication, recovery

## ARGOS — Autonomous Resilient Guardian Orchestration System
Creator: DarkAngel (the father of ARGOS)

## Swarm Architecture Rule
- Hermes = permanent Swarm Leader (stable Debian VM on dedicated server)
- Beasty = Swarm worker (can be rebooted/rebuilt anytime without affecting Swarm)
- If ARGOS runs on a single machine: that machine is master
- If Hermes is added: Hermes is automatically adopted as master
- Swarm decisions (deploy, scale, update) always run from Hermes

## Current Infrastructure
| Host | IP | OS | Role |
|------|----|----|------|
| Beasty | 11.11.11.111 | NixOS 25.11 | Swarm worker, RTX 3080, primary compute |
| Hermes | 11.11.11.98 | Debian 13 | Swarm Leader (permanent), standby |
| Zeus | 11.11.11.11 | Proxmox VE | Hypervisor |
| master | 11.11.11.201 | HAOS | Home Assistant Brain |
| argos-proxy | 11.11.11.137 | Debian 13 | nginx SSL proxy port 41337 |
| UDM Pro home | 10.0.10.1 | UniFi OS 10.x | Router |

Cristin: UDMPro 192.168.1.1, Ares Proxmox 192.168.1.2, iDRAC T440 10.0.20.20

## Docker Stack
| Container | Image | Port | Node |
|-----------|-------|------|------|
| argos-swarm_argos.1 | 11.11.11.111:5000/argos:latest | 666->8000 | Beasty |
| argos-swarm_argos.2 | 11.11.11.111:5000/argos:latest | 666->8000 | Hermes |
| argos-db | postgres:17 | 5432 | Beasty |
| argos-ollama | ollama/ollama GPU | 11435->11434 | Beasty |
| argos-registry | registry:2 | 5000 | Beasty |

Stack file: ~/.argos/docker/swarm-stack.yml (on Beasty)
DB_HOST=11.11.11.111 (real IP, Swarm overlay)
OLLAMA_URL=http://172.17.0.1:11435 (bridge network)
env_file: /root/.argos.env (per node, not shared)

## External Services
| Service | URL | Role |
|---------|-----|------|
| LightRAG | http://11.11.11.74:9621 | Graph RAG, 87 skills indexed |
| n8n | http://11.11.11.95:5678 | Workflow automation |
| Ollama | http://172.17.0.1:11435 | qwen3:14b GPU local inference |
| Vikunja | http://11.11.11.53:3456 | Project management, API v1 |

## Key Paths
```
~/.argos/
├── argos-core/          — application code (NFS exported ro to Hermes)
│   ├── api/             — FastAPI endpoints
│   ├── skills/          — 25 skill files (.md) IN ENGLISH
│   ├── config/.env      — API keys
│   ├── config/system_prompt.txt
│   └── ui/index.html
├── docker/
│   ├── Dockerfile
│   ├── swarm-stack.yml
│   └── docker-compose.yml
└── backups/db/          — DB backups
```

## Status Commands (run from Hermes for Swarm commands)
```bash
# Health
curl -s http://11.11.11.111:666/health

# Swarm status (from Hermes)
ssh root@11.11.11.98 "docker node ls"
ssh root@11.11.11.98 "docker stack ps argos-swarm"
ssh root@11.11.11.98 "docker service ls"

# Force restart (from Hermes)
ssh root@11.11.11.98 "docker service update --force argos-swarm_argos"
```

## Build + Deploy New Version
```bash
# Build on Beasty
cd ~/.argos && docker build -t argos:latest -f docker/Dockerfile .
docker tag argos:latest 11.11.11.111:5000/argos:latest
docker push 11.11.11.111:5000/argos:latest

# Deploy from Hermes
ssh root@11.11.11.98 "docker service update --image 11.11.11.111:5000/argos:latest argos-swarm_argos"
```

## Replication Architecture
```
Beasty (primary data)               Hermes (standby)
  argos-db (PG17) --streaming-->  postgresql-17
  argos-core/     --NFS ro----->  /home/darkangel/.argos/argos-core (fstab, _netdev)
  argos-core/     --rsync 5min-> /home/darkangel/.argos/argos-core (systemd timer)
  registry:5000   <-----------   pulls images from
```

## NFS on Hermes
```bash
# fstab entry (persistent):
11.11.11.111:/home/darkangel/.argos/argos-core /home/darkangel/.argos/argos-core nfs ro,sync,_netdev 0 0

# Docker waits for NFS at boot:
/etc/systemd/system/docker.service.d/nfs-wait.conf:
  [Unit]
  After=remote-fs.target
  Wants=remote-fs.target

# Manual remount if needed:
mount 11.11.11.111:/home/darkangel/.argos/argos-core /home/darkangel/.argos/argos-core
```

## DB Operations
```bash
# Access
docker exec -it argos-db psql -U claude -d claudedb

# Backup manual
docker exec argos-db pg_dump -U claude claudedb | gzip > ~/.argos/backups/db/claudedb-$(date +%Y%m%d-%H%M).sql.gz

# Restore
gunzip -c <backup.sql.gz> | docker exec -i argos-db psql -U claude -d claudedb

# Check replication
docker exec argos-db psql -U claude -d claudedb -c "SELECT client_addr, state, sent_lsn, write_lsn FROM pg_stat_replication;"

# Replication user
docker exec argos-db psql -U claude -d claudedb -c "CREATE USER replicator WITH REPLICATION ENCRYPTED PASSWORD '<pass>';"
# pg_hba.conf entry:
# host replication replicator 11.11.11.98/32 scram-sha-256
```

## RECOVERY PROCEDURES

### Scenario 1: Beasty rebooted/rebuilt (Hermes Leader survives)
```bash
# Swarm continues on Hermes automatically
# After Beasty comes back:
1. Verify NFS export still active on Beasty
2. docker stack ps argos-swarm  # from Hermes — should show Beasty rejoined
3. If Beasty lost worker status: docker swarm join --token <token> 11.11.11.98:2377
4. Recover token: ssh root@11.11.11.98 "docker swarm join-token worker"
5. Redeploy: ssh root@11.11.11.98 "docker service update --force argos-swarm_argos"
6. Restart DB container if needed: docker start argos-db argos-ollama argos-registry
```

### Scenario 2: Hermes down (Beasty worker only — NO Swarm manager)
```bash
# Argos app continues on Beasty (already running container)
# BUT: no Swarm manager = cannot deploy/update/scale
# Fix: promote Beasty to manager temporarily
docker node promote k5xdx2a23fq0hpf79vdd6l89a  # run from Beasty if it was demoted
# Or force new cluster if Hermes is completely dead:
docker swarm init --force-new-cluster --advertise-addr 11.11.11.111
docker stack deploy -c ~/.argos/docker/swarm-stack.yml argos-swarm
# When Hermes recovers: rejoin and re-promote
ssh root@11.11.11.98 "docker swarm join --token <token> 11.11.11.111:2377"
ssh root@11.11.11.98 "docker node promote yzamvplsoidf1biwna0xyvilg"
docker node demote k5xdx2a23fq0hpf79vdd6l89a
```

### Scenario 3: Both nodes down
```bash
# On Beasty (first to recover):
docker start argos-db argos-ollama argos-registry
docker swarm init --force-new-cluster --advertise-addr 11.11.11.111
docker stack deploy -c ~/.argos/docker/swarm-stack.yml argos-swarm
# Argos available on port 666
# When Hermes recovers: follow Scenario 2 Hermes rejoin steps
```

### Scenario 4: DB container dead on Beasty
```bash
docker start argos-db
# If volume corrupted, restore from backup:
docker stop argos-db
docker rm argos-db
docker volume rm argos-db-data
docker run -d --name argos-db --restart unless-stopped   -e POSTGRES_USER=claude -e POSTGRES_PASSWORD=<pass> -e POSTGRES_DB=claudedb   -v argos-db-data:/var/lib/postgresql/data -p 5432:5432 postgres:17
gunzip -c ~/.argos/backups/db/claudedb-current.sql.gz | docker exec -i argos-db psql -U claude -d claudedb
# Recreate replication user and pg_hba entry (see DB Operations above)
```

### Scenario 5: NFS not mounted on Hermes after reboot
```bash
ssh root@11.11.11.98 "mount 11.11.11.111:/home/darkangel/.argos/argos-core /home/darkangel/.argos/argos-core"
ssh root@11.11.11.98 "docker service update --force argos-swarm_argos"
# from Hermes:
ssh root@11.11.11.98 "docker service update --force argos-swarm_argos"
```

## Node IDs (for Swarm commands)
- Beasty: k5xdx2a23fq0hpf79vdd6l89a
- Hermes: yzamvplsoidf1biwna0xyvilg

## Boot Sequence (normal)
1. Beasty boots -> Docker starts -> argos-db, argos-ollama, argos-registry start
2. argos systemd service -> docker service update --force argos-swarm_argos
3. Hermes boots -> NFS mounts (fstab _netdev) -> Docker starts (after remote-fs.target) -> Swarm worker rejoins
4. Hermes is Leader -> distributes replicas on both nodes

## Environment Variables
- ANTHROPIC_API_KEY — Claude API
- GROK_API_KEY — Grok API
- OLLAMA_URL=http://172.17.0.1:11435
- DB_HOST=11.11.11.111
- DB_PORT=5432, DB_USER=claude, DB_NAME=claudedb

## HAProxy DB Failover
```bash
# Status on Beasty
systemctl status haproxy
journalctl -u haproxy -n 10 --no-pager

# Status on Hermes
ssh root@11.11.11.98 "systemctl status haproxy"

# Test failover
docker stop argos-db && sleep 3 && curl -s http://11.11.11.111:666/health
docker start argos-db

# HAProxy config Beasty (configuration.nix):
# services.haproxy = { enable = true; config = '...' }
# frontend bind *:5433
# server beasty 11.11.11.111:5432 check inter 3s fall 2 rise 2
# server hermes 11.11.11.98:5432 check inter 3s fall 2 rise 2 backup

# HAProxy config Hermes (/etc/haproxy/haproxy.cfg):
# server hermes 127.0.0.1:5432 check inter 3s fall 2 rise 2
# server beasty 11.11.11.111:5432 check inter 3s fall 2 rise 2 backup
```

## Skill System v2
```bash
# Import .argosdb files interactively
argos-import-skills

# Directories
# ~/.argos/argos-core/skills/           - classic .md skills (25)
# ~/.argos/argos-core/skills/manual/    - YAML manual sub-skills
# ~/.argos/argos-core/skills/import/    - .argosdb import queue
# ~/.argos/argos-core/skills/import/done/ - imported files

# Key scripts
# skill_selector.py        - auto-selects sub-skills per message
# skill_importer.py        - imports YAML from manual/
# argos_skill_importer.py  - imports .argosdb with Claude categorization
```



## Heartbeat System (v2 - April 2026)

### Architecture
- Beasty: runs as host process (not in container), needs nix-store Python path
  - Start: DB_PASSWORD='...' nohup /nix/store/yf4nfs51z4ibzbv3pi20dz5spmdjdqcw-python3-3.13.12-env/bin/python3 ~/.argos/argos-core/heartbeat.py > /tmp/heartbeat_beasty.log 2>&1 &
- Hermes: runs from /opt/argos/heartbeat.py (copy via scp, NOT NFS)
  - Start: DB_PASSWORD='...' nohup /usr/bin/python3 /opt/argos/heartbeat.py > /tmp/heartbeat.log 2>&1 &
- Both need DB_PASSWORD env var set explicitly

### Key features
- _bin() function: auto-detect NixOS vs Debian binary paths
- /proc/stat CPU: no dependency on top command or locale
- ping_fleet: Beasty pings all system_profiles IPs every 30s, updates online status
- Skip container check on hermes (NODE != 'hermes') - swarm manager has 0 containers
- Updates system_profiles.online + last_seen on every heartbeat

### Restart procedure
```bash
# Beasty
kill $(pgrep -f 'python3.*heartbeat.py')
DB_PASSWORD='...' nohup /nix/store/...-python3-env/bin/python3 ~/.argos/argos-core/heartbeat.py > /tmp/heartbeat_beasty.log 2>&1 &
# Hermes (copy first if code changed)
scp ~/.argos/argos-core/heartbeat.py root@11.11.11.98:/opt/argos/heartbeat.py
ssh root@11.11.11.98 "kill $(pgrep -f 'python3.*heartbeat.py') 2>/dev/null; DB_PASSWORD='...' nohup /usr/bin/python3 /opt/argos/heartbeat.py > /tmp/heartbeat.log 2>&1 &"
```

## Fleet System
- system_profiles table: known machines (beasty, hermes, zeus, master, ares-cristin)
- nanite_nodes table: nanite agents (announced/installing/installed)
- API: GET /api/fleet (combined list), DELETE /api/fleet/known/{id}, DELETE /api/fleet/nanite/{node_id}
- Online detection: heartbeat direct (beasty/hermes) + ping_fleet (zeus/master/ares-cristin)

## Container Patterns (CRITICAL)
- ARGOS runs IN container - ~ = /home/argos/, NOT /home/darkangel/
- LOCAL_MACHINES = [] - NEVER execute locally, ALWAYS SSH to 11.11.11.111 for beasty commands
- Use absolute paths: /home/darkangel/.argos/... not ~/.argos/...
- Container ID changes on every redeploy - use name filter: docker ps -f name=argos-swarm_argos
- docker logs needs explicit container ID, not $(docker ps -q) when multiple containers match
- After code change: ssh root@11.11.11.98 "docker service update --force argos-swarm_argos"
- Heartbeat processes on host need manual restart (kill + nohup) after code change
