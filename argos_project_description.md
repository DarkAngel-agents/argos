# ARGOS — Project Overview

## The problem

Running a self-hosted infrastructure means spending time on the same class of problems repeatedly: configuration drift, failed rebuilds, forgotten command syntax for systems you touch once a month, hunting through logs after something breaks at 3am. AI assistants help, but they start from zero every session. They do not remember that this specific NixOS version has a kernel module conflict with that specific driver. You do.

Argos is built around the idea that an AI agent should accumulate operational knowledge the same way a sysadmin does — by doing things, seeing what breaks, and remembering.

---

## What Argos is

A self-hosted, persistent AI infrastructure agent. It runs on your hardware, connects to your systems, executes real operations, and builds a structured knowledge base from every action it takes.

It is not a wrapper around a chat API. It is an agent loop with tools, memory, and a progressive autonomy model that you control.

---

## Core capabilities

**Execution**
SSH command execution across all known hosts, with dynamic timeout handling based on operation type. Read-only commands are routed to a local model (free, no API cost). Write operations use the primary reasoning model.

**NixOS management**
Automatic backup before any configuration change. Zone-tagged configuration with markers that tell the agent what it can and cannot touch. Rebuild with automatic rollback on failure. Full config index updated after every rebuild.

**Learning**
Every executed command updates a knowledge base entry: what was run, on which OS version, what happened, and whether it should ever be tried again. The agent consults this before acting. A `skip=true` flag means it will never attempt that operation again on that system.

**Skill system**
When the agent encounters an unknown system, it researches it, structures the findings into a skill file (commands, gotchas, dangerous operations), and loads it automatically on future encounters. Skills are plain Markdown — readable, editable, version controlled.

**Multi-provider reasoning**
Complex questions trigger a secondary consultation with a web-search-capable model before the primary model responds. The external perspective is sanitized for prompt injection before use.

**Job system**
Destructive operations are not executed directly. They are queued as jobs with explicit approval gates. The agent will not delete a VM, format a disk, or modify a UniFi configuration without a job approval, regardless of what it is asked.

**Self-modification**
The agent can modify its own code through a controlled path (Claude Code with approval gates and automatic rollback if the service fails to restart). Configuration changes to Argos itself follow the same backup-modify-verify cycle as everything else.

---

## What is being released publicly

**NixOS Autonomous Management Module**

The component that handles:
- Configuration management with zone tagging (`@managed`, `@critical`, `@argos:do-not-touch`)
- Automated rebuild with backup and rollback
- Configuration indexing and change tracking
- Integration hooks for the broader Argos agent

This module can be used independently to add structured, auditable AI-assisted NixOS management to any setup.

**Argos Core** — the full agent including multi-provider routing, job system, mobile interface, skill generator, infrastructure-wide management, and Home Assistant integration — is in active development. It will be released when the autonomy model and packaging are stable.

---

## What it runs on

NixOS. The entire system is designed around NixOS's declarative model — immutable generations, rollback by design, reproducible builds. The agent's understanding of "safe" and "dangerous" is built around this model.

A flake-based installer is planned that will allow Argos to deploy itself, scan the local network, and begin building its knowledge base from first boot.

---

## Current state

| Component | Status |
|-----------|--------|
| NixOS module | Public, stable |
| Argos Core agent | In development |
| Knowledge base | Functional, growing |
| Skill system | 23 skills, auto-generation active |
| Mobile app (Android) | Functional on local network |
| flake.nix installer | Planned |
| External access | In progress |
| Autonomy level 1 | Active (service restarts without approval) |
| Autonomy level 2+ | Planned, manually unlocked |

*Follow this repository. The NixOS module drops in a few days.*


