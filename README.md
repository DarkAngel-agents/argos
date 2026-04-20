# ARGOS

**Autonomous Resilient Guardian Orchestration System**

ARGOS is a self-hosted AI infrastructure agent that monitors, manages, and operates your entire server fleet through natural language. Built for sysadmins who want AI assistance without cloud dependency.

## What it does

- **Chat interface** -- talk to your infrastructure in natural language. ARGOS executes commands, reads files, manages services across all your machines via SSH.
- **Fleet management** -- unified view of all systems (physical, VMs, containers). Real-time online/offline detection via heartbeat + ping.
- **Health monitoring** -- CPU, memory, DB latency, container status. Live SSE activity stream.
- **Job system** -- multi-step operations with risk assessment and approval workflow. Critical operations require explicit authorization.
- **Agent loop (Commander)** -- autonomous task execution with phase state machine (executing/verifying/fixing), safety guards, and fix loop counter.
- **Skills system** -- 110+ skills loaded contextually via BM25 scoring. Auto-learns new systems via web search.
- **Multi-LLM** -- Claude (primary), Ollama (local fallback). Provider abstraction layer.

## Architecture

```
Browser (Alpine.js + htmx)
    |
    v  SSE + REST
ARGOS API (FastAPI, port 666)
    |
    +---> PostgreSQL (40+ tables)
    +---> SSH to all fleet nodes
    +---> Claude API / Ollama
```

- **Frontend**: Alpine.js 3.14 + htmx 2.0 + SSE. Zero build pipeline.
- **Backend**: Python 3.13, FastAPI, asyncpg, Anthropic SDK.
- **Database**: PostgreSQL 16.
- **Deployment**: Docker Swarm (production) or Docker Compose (single-node).

## Quick Start

See [INSTALL.md](INSTALL.md) for detailed instructions.

```bash
git clone git@github.com:DarkAngel-agents/argos.git
cd argos
cp env.example .argos.env   # edit with your API keys
docker compose -f docker/docker-compose-standalone.yml up -d
# Open http://localhost:666
```

## Requirements

- Docker + Docker Compose
- Anthropic API key
- PostgreSQL 16 (included in standalone compose)

## Project Structure

```
argos/
+-- argos-core/
|   +-- api/          # FastAPI endpoints
|   +-- agent/        # Commander agent loop
|   +-- llm/          # LLM provider abstraction
|   +-- skills/       # Contextual skill files
|   +-- tools/        # Audit tools
|   +-- ui/           # Frontend
|   +-- heartbeat.py  # Node health daemon
+-- docker/           # Docker configs
+-- argos-nanite/     # Bootable agent ISO (WIP)
```

## Status

**Alpha** -- functional for single-user self-hosted use.

## License

Apache License 2.0 -- see [LICENSE](LICENSE)

## Author

Built by [DarkAngel](https://github.com/DarkAngel-agents) -- 20+ years sysadmin, based in France.
