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
