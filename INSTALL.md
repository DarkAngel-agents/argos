# ARGOS Installation Guide

## Prerequisites

- Linux host (tested on Debian 13, NixOS 25.11)
- Docker Engine 24+ and Docker Compose v2
- Anthropic API key

## Standalone Setup

### 1. Clone

```bash
git clone git@github.com:DarkAngel-agents/argos.git
cd argos
```

### 2. Configure

```bash
cp env.example .argos.env
# Edit .argos.env with your API key and DB password
```

### 3. Start

```bash
docker compose -f docker/docker-compose-standalone.yml up -d
```

### 4. Access

```
http://localhost:666
```

## Swarm Setup (Multi-Node)

### Manager node

```bash
docker swarm init --advertise-addr <manager-ip>
docker stack deploy -c docker/swarm-stack.yml argos-swarm
```

### Worker node

```bash
docker swarm join --token <token> <manager-ip>:2377
```

### Heartbeat (each node)

```bash
export DB_PASSWORD=<password>
python3 argos-core/heartbeat.py &
```

## Troubleshooting

```bash
docker logs argos-app --tail 50
docker exec argos-db psql -U claude -d claudedb -c "SELECT 1;"
tail -f /tmp/heartbeat.log
```
