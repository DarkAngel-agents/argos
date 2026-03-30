# ARGOS — Installation Guide

## Before you start

ARGOS needs API keys to work. For a first test, you don't need to spend much:
- **Claude API** (Anthropic) — ~3€ is more than enough to test everything. Get it at: https://platform.anthropic.com
- **Grok API** (xAI) — optional but recommended, ~2€ for testing. Get it at: https://console.x.ai

Why Claude? It's the reasoning engine. ARGOS uses it to think, plan, and execute.
Why Grok? Secondary reasoning, web search fallback. Optional but makes ARGOS smarter.

---

## Requirements

- Linux machine (tested on Fedora 42, Fedora 44, Debian 13)
- Docker + Docker Swarm (setup.sh installs Docker if missing)
- Minimum 4GB RAM, 20GB disk
- GPU optional (Ollama runs on CPU too, just slower)

---

## Quick Install

**Step 1 — Clone the repo:**
```bash
git clone https://github.com/DarkAngel-agents/argos.git ~/.argos/argos-core
```

**Step 2 — Copy and fill the config:**
```bash
mkdir -p ~/.argos/config
cp ~/.argos/argos-core/argos-setup.yaml.example ~/.argos/config/argos-setup.yaml
nano ~/.argos/config/argos-setup.yaml
```

Fill in at minimum:
- `username` — your Linux username
- `claude_token` — your Anthropic API key
- `db_password` — choose any strong password
- `hostname` — this machine's hostname

**Step 3 — Run setup:**
```bash
bash ~/.argos/argos-core/setup.sh
```

That's it. setup.sh handles everything:
- Installs Docker if missing
- Detects GPU and configures Ollama accordingly
- Creates PostgreSQL database with full schema
- Builds and deploys ARGOS

**Step 4 — Open ARGOS:**
```
http://localhost:666
```

---

## What setup.sh does (in order)

1. Validates your config file
2. Installs Docker if not present (Fedora/Debian/Ubuntu)
3. Removes podman-docker conflicts if found
4. Initializes Docker Swarm
5. Starts PostgreSQL 17 container
6. Creates full database schema
7. Writes settings from your config into DB
8. Detects GPU/VRAM → selects Ollama model automatically
9. Starts Ollama (GPU or CPU)
10. Configures local Docker registry
11. Builds ARGOS image and deploys stack
12. Saves your config as `argos-private.yaml`, deletes the original

---

## Known gotchas

- **Fedora only:** remove `podman-docker` before installing `docker-ce` — setup.sh does this automatically
- **GPU:** if you have an NVIDIA GPU, install `nvidia-container-toolkit` before running setup.sh
- **Two nodes:** setup.sh configures a single node by default. Two-node Swarm setup documented separately (coming soon)

---

## After install

ARGOS opens at `http://YOUR_IP:666`

First message: ask ARGOS what it can do. It will tell you exactly what tools and skills are loaded.

---

## Troubleshooting

**API returns 500:**
```bash
curl -s http://YOUR_MACHINE_IP:666/health
```
If `prompt_modules: 0` → restart the service:
```bash
docker service update --force argos-swarm_argos
```

**DB connection failed:**
```bash
docker ps | grep argos-db
docker start argos-db
```

---

*If something is broken or unclear — open an issue. This is v1, things will improve fast.*
