# ARGOS

**Autonomous Resilient Guardian Orchestration System**

An AI infrastructure agent that orchestrates LLMs to do real sysadmin work — diagnose problems, apply fixes, verify results, and keep going when things break.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Status: Public Alpha](https://img.shields.io/badge/status-public%20alpha-orange.svg)](#status)

---

## What is this

ARGOS is what happens when you stop treating LLMs as chatbots and start treating them as operators. It runs on your infrastructure, watches your services, and when something breaks it doesn't just write you a polite explanation — it tries to fix it, verifies the fix worked, and writes down what it learned.

Single-sentence version: **an LLM-driven agent loop with skills, verification chains, and safety guards, designed to live in production homelab environments and not pretend everything is fine when it isn't.**

## About this project

ARGOS is a fragment of the work I do daily. I've reached the point where I can't orchestrate the whole project alone anymore — too many moving parts, too much context, too many decisions per day. So I'm publishing the part that can stand on its own, and it does not include personal scripts, automations, or other private pieces — nor does it include other capabilities the system can have (smart-home integrations, infrastructure-specific orchestration, custom reverse-engineering tooling, and so on).

If parts of the documentation feel AI-written, that's because they are. I'm not a native English speaker, and I'd rather write correctly with help than write badly without it. The code is mine; the prose is co-written.

The current public version is the codebase without my personal skills and without the memory ARGOS has built up around my infrastructure. As-is, it would be impossible for me to operate it at the level where I can keep adding new functional features. The next milestone is finishing the autonomous reverse-engineering layer — once that lands, the public version becomes self-sufficient enough that someone else could actually use it. Targeting roughly one month from now.

## Status

This is a **public alpha**. Be honest about what that means:

- **It is real production code.** Deployed on the author's homelab. Two-node Docker Swarm, PostgreSQL with streaming replication, Redis-backed rate limiting, heartbeat sync, body size middleware, the works. It runs.
- **It is also volatile.** APIs change. Internal architecture evolves between sessions. Rough edges everywhere. Bugs that have been on the backlog for weeks. Code that needs refactoring (looking at you, `chat.py`).
- **It is reference-grade material.** Even if you never deploy it, the architecture decisions are documented honestly — including the wrong ones we made and reverted. Read the commit history, not just the success stories.

I've recently changed my development process to add explicit verification steps and protocols, because I noticed the AI-assisted parts of the workflow occasionally drop things they shouldn't — wrong function names, missed dependencies, forgotten edge cases. The verification chain is the response to that, not a feature I designed for elegance.

The remaining piece before this codebase becomes truly autonomous is the reverse-engineering layer. I'm hoping to land that within a month. After that, this can run as a self-sufficient unit; right now, the public version is real but incomplete.

You can use it. You can fork it. You can learn from it. Just don't bet your company's prod on it yet.

## Architecture (short version)

```
┌─────────────────────────────────────────────────────────────┐
│                      External LLMs                          │
│           (Anthropic, xAI — pluggable providers)            │
└────────────────────────┬────────────────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │   ARGOS Commander   │  ← agent loop, verification chain
              │   (FastAPI + UI)    │     phase transitions, safety guards
              └──────────┬──────────┘
                         │
       ┌─────────────────┼─────────────────┐
       │                 │                 │
   ┌───▼────┐      ┌─────▼─────┐    ┌──────▼──────┐
   │ Skills │      │ Heartbeat │    │  Executor   │
   │  (DB)  │      │  (cross-  │    │  (subprocess│
   │        │      │   node)   │    │   sandbox)  │
   └────────┘      └───────────┘    └─────────────┘
                         │
              ┌──────────▼──────────┐
              │   Postgres + Redis  │  ← state, rate limits, heartbeat log
              │   HAProxy failover  │
              └─────────────────────┘
```

Two-node Docker Swarm by default. Can run single-node. State persists. Rate limiting works across replicas (Redis-backed slowapi). When DB primary dies, HAProxy fails over in <3 seconds. Heartbeats prove both nodes are alive every 2 seconds.

## Getting it running

> **Heads up:** the simplest path is single-node Docker Compose. The full HA setup (Swarm + replication + HAProxy) is documented but assumes you have already run a homelab cluster before.

```bash
# Clone
git clone https://github.com/<TODO-darkangel>/argos.git
cd argos

# Configure (copy template, fill in your keys)
cp config/argos.env.example config/argos.env
$EDITOR config/argos.env

# Build + run (single-node)
docker compose up -d

# Smoke test
curl http://localhost:666/health
```

You'll need at minimum:
- An Anthropic API key (or xAI key — the agent works with either)
- Docker + Docker Compose
- ~4GB RAM for the basics, more if you run local Ollama alongside

For the full Swarm + HA setup, see [`docs/deploy/swarm-ha.md`](docs/deploy/swarm-ha.md). _(TODO before final release.)_

## What's actually here

| Component | What it does |
|-----------|--------------|
| `argos-core/api/` | FastAPI app — chat endpoints, approvals, streaming, executor proxy |
| `argos-core/agent/` | The agent loop. Phase transitions, verification, prompts, evidence, autonomy controls, tools |
| `argos-core/heartbeat.py` | Standalone systemd daemon. Writes `(node, ts)` to Postgres every 2s. Cross-node aware via env-overridable URLs |
| `argos-core/ui/v2/` | Web UI. Alpine.js + htmx, no SPA framework, server-rendered with progressive enhancement |
| `argos-core/skills/` | Where ARGOS' learned procedures live. Examples included; you bring your own for your stack |
| `docker/` | Dockerfile + Swarm stack file. Health checks tuned for production stability |

## Skills — the important part

ARGOS without skills is a chatbot with shell access. ARGOS *with* skills is what we're actually building.

A skill is a Markdown file with a fixed structure: when to trigger, how to diagnose, how to fix, how to verify. The agent reads them, picks one based on the situation, and executes the steps with verification at each stage.

The repo includes a small set of generic example skills (Git operations, Docker basics, common Linux ops). The author's personal homelab skills — the ones referencing specific IP ranges, hostnames, and infrastructure — are not in this repo. They're private. You build your own for your environment.

## What's NOT in this repo (intentionally)

- **Personal homelab skills** referencing specific hostnames, IP addresses, and credentials. Those live elsewhere.
- **Smart-home automations** (BLE beacons, Fibaro HC3, ESPHome configs) — separate domain, separate project.
- **KRONOS** — a retail POS reverse-engineering project that shares some ARGOS components but is its own thing.
- **Personal scripts and automations** that orchestrate the rest of my infrastructure on top of ARGOS.

If you're hoping to find a turnkey "control my whole house with Claude" solution, that's not this. ARGOS is the orchestration brain. Bring your own peripherals.

## Hardware where this has been tested

- **Beasty** — NixOS 25.11, RTX 3080, primary worker
- **Hermes** — Debian 13, permanent Swarm leader
- **Zeus** — Proxmox host running supporting LXCs (DB, Vikunja, n8n, LightRAG)

Reality check: this is one homelab. Your mileage will vary. The architecture is portable; the assumptions might not be.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Short version: open an issue first, talk before you code, write tests, no force-pushes to main, atomic commits, no bundled changes across scopes.

## License

[Apache 2.0](LICENSE). Use it, fork it, sell it. Don't sue people over patents you didn't disclose. The usual.

## Disclaimer

Read [DISCLAIMER.md](DISCLAIMER.md) before deploying this anywhere that matters. There are known things in the git history (a stale UniFi API key that returns 401, no longer functional) and architectural debt (`chat.py` needs decomposing, `*.bak` files until recently lived in the repo). We document this honestly because the alternative is pretending alpha software is something it isn't.

## Author

Built by **DarkAngel** — sysadmin, homelab operator, occasional reverse engineer.

ARGOS exists because LLMs got good enough to be operators, but the tooling to actually let them operate didn't. So I built it. The code is what it is; the goal is what it should become.

If this is useful to you, that's the point. If it isn't, fork it and make it useful.

---

_Public alpha. Things will change. The history is the truth._
