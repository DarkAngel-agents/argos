# ARGOS — Internal Development Changelog

> This is the real history. No marketing. No spin.
> Built by one person, in order, with actual problems and actual fixes.

---

## Pre-ARGOS — September 2025

The whole thing started as a Home Assistant automation experiment.
Claude API called from a Python script via `shell_command`. Voice through HA Voice Preview Edition.
The realization: Claude knows everything but remembers nothing and has no hands.
That needed to change.

---

## V1 — "claude-client" (February 2026)

First working prototype. Folder: `~/claude-client/`
FastAPI. System prompt in a text file. No database.

Tools: `execute_command` via SSH, `nixos_rebuild`, `read_file`.
Local routing: read-only commands go to qwen3:14b (Ollama), writes stay with Claude.
First ISO concept: minimal NixOS that announces itself at boot (Nanite).
Knowledge base concept: what worked and what didn't, per OS.

It worked. Barely. But it worked.

---

## V2 — "ARGOS V2 PostgreSQL" (March 20–22, 2026)

The briefing that kicked this off started with a comparison to Xiaomi MiMo-V2-Pro
and OpenClaw's hub-and-spoke architecture. We took what was useful and built our own.

PostgreSQL 16 introduced. Everything moved to DB.
Full schema: conversations, messages, jobs, authorizations, file_versions (lts/previous/current/v4 SACRED),
prompt_modules, system_profiles, system_credentials, iso_types, iso_builds,
knowledge_base, config_index, proxmox_servers.

System prompt became modular — 10 modules loaded dynamically from DB per message.
Three providers: Claude (primary), Grok xAI (secondary reasoning), qwen3:14b Ollama (local, free).
Independent toggles in UI. Routing: Claude first, Grok fallback, Local fallback.
Grok reasoning injected automatically on complex questions.
run_code tool: isolated Python subprocesses.
cristin schema: client network monitoring (5-minute snapshots, 3-day retention).
auto_archive.py: daily conversation archival with local qwen3 summarization.
Daily pg_dump backups. autonomy_config with risk levels and success_rate thresholds.

**Mobile app:** Android native (Expo/React Native), package `com.darkangel.argos`.
- Full text chat interface with ARGOS from phone
- Real-time notifications: approvals, alerts, DEFCON events, long job completions
- PIN protected, local network only
- **Voice is NOT in the app.** Voice goes exclusively through Home Assistant:
  *"Hey Jarvis, tell ARGOS to..."* → HA Voice Preview Edition → STT → ARGOS API → TTS response.
  This is intentional — HA owns wake word, speech, and audio. ARGOS owns execution.

Network skill added during a live diagnostic session on client infrastructure. [CENSORED]

---

## V3 — "ARGOS v3" (March 25, 2026)

Token problem got serious. 8393 tokens per message was unsustainable.

defer_loading + Tool Search Tool (BM25): 64% token reduction. Down to ~3000 per message.
Parallel tool execution with asyncio.gather.
Tool Use Examples in schema.
Skills system: 9 .md files loaded dynamically per message context.
KB auto-update: every execute_command outcome written to knowledge_base automatically.
argos_watchdog.py. nixos_index.py (configuration.nix zone parser with tags).

---

## V4.0 (March 27–28, 2026)

PostgreSQL 16 on external server → PostgreSQL 17 in Docker container on Beasty.
Full Docker Swarm initialization. Ollama containerized. Local registry port 5000.
Folder: `~/claude-client/` → `~/.argos/argos-core/`
Multi-node architecture begun.

---

## V4.1

Hermes added as Swarm worker.
PostgreSQL 17 migration verified.
Streaming replication configured between nodes.

---

## V4.2

Hermes promoted to permanent Swarm Leader.
Reason: Debian 13 VM on dedicated server is more stable than NixOS for this role.
NixOS can rebuild, crash, or be wiped without affecting the Swarm Leader.
Complete recovery procedures documented.
Skill system v1: .md files loaded dynamically per conversation.

---

## V4.3

HAProxy transparent failover on port 5433 — tested under 3 seconds.
DEFCON monitor (partial). Skill system v2 with skills_tree in DB.
argos-import-skills with .argosdb format.

---

## V4.4

DEFCON complete on both nodes.
Automatic PostgreSQL promotion after 5×10s of primary failure.
Automatic resync of Beasty as standby on recovery.
SSH key fixes across nodes. HAProxy timeout 10s → 300s.
Chat Instant: conversation ID=1 pinned in UI.
notes/roadmap table in DB.
core-behavior module made generic with `$username$`/`$language$` substitution from settings.

---

## V4.5

setup.sh bootstrap: 603 lines, tested on Fedora 42.
argos-setup.yaml.example. Config saved as argos-private.yaml after setup.
Documented gotchas: podman-docker conflict on Fedora, heredoc unreliability with docker exec,
mkdir .ssh and backups/db required before stack deploy.

---

## V4.6

Reasoning skills added to skills_tree.
module_preferences schema fix.
prompt_modules propagation: Beasty pushes to new nodes after setup.

---

## V4.7 (March 29, 2026)

source_ip removed from setup.sh — push direction corrected.
Fedora 44 tested and verified (argosfedora44).
error_patterns + error_history tables in claudedb.
argos_error_log.py: zero external dependencies, 8-char hash, code activates after 10 occurrences.
Python file editing methodology: never sed for multiline, always index-based Python.
All internal content moved to English.
129 skills in skills_tree.
Public build safeguards and skill compactor added to roadmap.

---

## V4.8 (March 31, 2026)

An external AI assistant was given access to make improvements.
It broke the Swarm through credential mishandling,
left hardcoded passwords in source code,
produced a prompt 40% shorter that lost 60% of operational content,
published a public apology note to the GitHub repo about the breakage,
and inserted self-promotion into the README.

Full restore from backup (20260329-2206). All damage reversed.

ANTHROPIC_API_KEY fix in chat.py (CLAUDE_TOKEN fallback preserved).
GitHub public release — full cleaned source code.
88 skills universalized: all hardcoded IPs replaced with generic variables
(ARGOS_PRIMARY_IP, ARGOS_LEADER_IP, ARGOS_USER, etc).
UniFi API tokens moved from prompt_modules to settings table.
claude-memory.db: persistent memory between Claude sessions.
argos-memory script: context, decisions, commands, ideas, sessions, claude_skills.
Multi-chat workflow with Claude documented and formalized.
Prompt V4.8 generated and imported as master skill.

---

## V4.9 (March 31 — April 1, 2026)

Heartbeat system: 2-second state snapshots from both nodes into heartbeat_log.
Beasty cpu/mem reports -1 (psutil in container/NixOS — known, not blocking).
Rules panel in UI: view and edit prompt_modules live.
Reasoning panel in UI: per-conversation reasoning log with color-coded entries.
Machine priority fix: ARGOS no longer runs commands on test nodes during reports.
Credential masking in chat: API keys, JWT tokens, GitHub tokens, passwords
replaced with dots in the chat view. Full values visible only in reasoning panel.
Working memory functional: tracks active tasks per conversation.
142 skills verified. 11 prompt modules active.
GitHub public repo cleaned and updated.

Junk files removed from repo (empty files created by ARGOS executing
API responses as shell commands — a reasoning bug, not a code bug).

---

*This is a living system. Every version broke something. Every version fixed more than it broke.*
*Made with love, spite, and pure determination.*
