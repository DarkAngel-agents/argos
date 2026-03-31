# ARGOS — Autonomous Resilient Guardian Orchestration System

> This whole insane ride started because I was sick and tired of NixOS headaches.
> Because I didn't like some comment on the NixOS forum, I decided to build this as Docker Swarm
> instead of flake.nix — to keep it compatible with as many people as possible.
> If starting fresh, I'd recommend Fedora with Plasma 6.

---

## What is ARGOS?

ARGOS is a self-hosted autonomous AI assistant built for real infrastructure management.
Not a chatbot wrapper. Not a demo. A system that runs your homelab.

It handles Docker Swarm, NixOS configuration, PostgreSQL replication with automatic failover,
disaster recovery, a skill tree with 100+ verified procedures, error pattern learning,
and talks directly to Proxmox, UniFi, Home Assistant, and pretty much anything else in your homelab.

---

## Architecture

- **2-node Docker Swarm** — permanent leader + worker
- **PostgreSQL 17** with streaming replication and HAProxy auto-failover < 3 seconds
- **Ollama** (local GPU) for free operations — Claude for reasoning
- **skills_tree** — 100+ verified procedures loaded dynamically per context
- **DEFCON monitor** — automatic DB promotion on node failure
- **error_patterns** — learns from repeated errors, activates error codes after 10 occurrences

---

## What's public here

This repo contains safe public templates only:

- `setup.sh` — bootstrap template for new nodes
- `docker/` — Swarm stack + Dockerfile templates
- `skills/` — generic whitelisted skills (NixOS, Debian, Docker)
- `argos-setup.yaml.example` — configuration template

The full ARGOS core (API, chat engine, UI, tools) is still in active development.

---

## Status

Actively developed. Already running 24/7 on real infrastructure.
See [ROADMAP.md](ROADMAP.md) for what's coming.

---

## Requirements

- Docker + Docker Swarm
- PostgreSQL 17 (via Docker)
- Claude API key (Anthropic)
- Grok API key (optional but recommended)
- Ollama (optional, for local model)

---

*Made with love, spite, and pure determination.*



---

## Hardware Requirements

### Minimum — untested, theoretical baseline
- CPU: 4+ cores x86_64
- RAM: 8GB
- Storage: 40GB
- GPU: not required (Ollama skipped, API-only mode)
- OS: Fedora 42+, Debian 12+, Ubuntu 22.04+

*Not yet tested at this spec. At minimum config, ARGOS relies entirely on Claude/Grok API.
No local inference. Everything else should work — in theory.*

### Entry level — tested, works well
- CPU: Intel Core i7 6th gen or equivalent
- RAM: 32GB
- Storage: 60GB SSD
- GPU: NVIDIA RTX 2060 (6GB VRAM)
- OS: Fedora 44, Debian 13

Ollama runs smaller local models at this spec. Good enough for daily use and testing.
This is the laptop/workstation tier — solid for development and light production.

### Recommended — production, tested daily
- CPU: 8+ cores (Ryzen/Intel 10th gen+)
- RAM: 32GB+
- Storage: 100GB+ SSD
- GPU: NVIDIA RTX 3080 10GB VRAM
- OS: NixOS 25.11 or Fedora 44

Runs qwen3:14b locally without breaking a sweat. This is what ARGOS was built and tested on.
Local inference handles all read-only ops, health checks, and routine tasks for free.

### Two-node setup — what runs 24/7 here
- Node 1 (Beasty): NixOS 25.11, RTX 3080, primary compute + DB + registry
- Node 2 (Hermes): Debian 13 VM on dedicated server, permanent Swarm Leader
- PostgreSQL streaming replication with HAProxy auto-failover < 3 seconds
- DEFCON monitoring on both nodes with automatic failover

### Future — full local autonomous (no external API)
Truly autonomous operation without Claude/Grok API requires a large local model capable of
multi-step reasoning, tool use, and infrastructure decisions without hallucinating.
Think RTX 6000 Ada (48GB VRAM) or a multi-GPU setup.

*I am quite attached to both my kidneys, so this remains a future plan.*

---

## Status — v1 Alpha

This is v1 alpha. It works. It runs real infrastructure 24/7.
But it is not polished, not sanitized for every environment, and v2 will bring radical changes.

**What changes in v2:** complete knowledge architecture redesign (Bubble DB), security compartmentalization with local GPU-only processing for sensitive data, encryption between containers, advanced reasoning engine, PWA mobile app, and full database restructure.

If you install v1 now — migration tools will be provided for v2. No data loss.

---

## Development Notes

This release was developed and tested on a private network (11.11.11.x range) with username `darkangel`.
Some paths and IPs are hardcoded in templates — replace with your own before deploying.

**v1 = working, tested, real infrastructure. Not sanitized for generic use yet.**
**v2 will have fully dynamic configuration with no hardcoded values.**

If you see `11.11.11.111` or `darkangel` in any file — that's a placeholder for your own values.
