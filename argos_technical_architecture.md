# ARGOS — How It Actually Works
## A self-hosted AI infrastructure agent on NixOS

This document describes the architecture and operational logic of a working system.
No marketing. No demos. Production infrastructure, running continuously.

---

## The core loop

```
User message
    │
    ▼
Argos API (FastAPI)
    │
    ├── Load relevant prompt modules from DB (based on message keywords)
    ├── Load skill files (nixos-25.11 always, others on keyword match)
    ├── Check if Grok reasoning needed (complex question detection)
    │       └── If yes: query Grok web search → sanitize → inject as context
    ├── Check tool scores (which tools have best success rate for this type)
    │
    ▼
Claude API (primary reasoning model)
    │
    ├── Tool use loop (parallel execution via asyncio.gather):
    │       execute_command → SSH to target host
    │       read_file       → remote file read
    │       nixos_rebuild   → backup + write + rebuild + index
    │       create_job      → approval queue for destructive ops
    │       code_edit       → self-modification via Claude Code
    │       build_iso       → NixOS ISO generation + VM test
    │
    ├── After each execute_command:
    │       → Update knowledge_base (action, outcome, success_rate)
    │       → Update tool_scores
    │       → Log to debug_logs with standardized error code
    │       → Check for unknown system → trigger skill generation
    │
    ▼
Response saved to DB → UI polls → displayed to user
```

---

## Knowledge base

Every executed command produces a structured record:

```sql
knowledge_base:
  os_type        -- linux / nixos / proxmox / unifi / idrac / etc
  os_version     -- 25.11 / 8.x / 4.x / etc
  command_type   -- shell / api / rebuild / etc
  action         -- the actual command (truncated to 200 chars)
  outcome        -- ok / fail
  success_rate   -- float, updated after each execution
  skip           -- boolean: never attempt this again
  reason         -- stderr output on failure
```

Before any action, the agent queries this table. If `skip=true` for that command on that OS version, it refuses to execute and explains why. If `success_rate < 0.3`, it warns before proceeding.

This is not a static knowledge base. It grows with every operation on every host.

---

## Skill system

Skills are Markdown files, loaded into the system prompt on demand.

```
skills/
├── nixos-25.11.md      -- always loaded
├── proxmox-8.md        -- loaded when proxmox/qm/vm detected in message
├── unifi-os-4.md       -- loaded when unifi/udm/switch detected
├── idrac-9.md          -- loaded when idrac/redfish detected
├── esphome-2024.md     -- loaded when esp32/esphome detected
├── pentest-generic.md  -- loaded when audit/scan/nmap detected
└── [21 more...]
```

**Auto-generation flow** (for unknown systems):

```
Unknown system detected in SSH output
    │
    ▼
Claude composes 4-5 specific search queries
    │
    ▼
Grok searches web (POST /v1/responses with web_search tool)
    │
    ▼
Results sanitized for prompt injection
(strips: "ignore previous", "you are now", "new instructions", etc)
    │
    ▼
Claude structures findings into skill file:
- Detection commands
- Core commands
- Important file paths
- Dangerous / irreversible operations
- Known gotchas and bugs
    │
    ▼
Skill saved to disk + registered in DB
Max 5 auto-generated skills per day (bypassed for explicit user tasks)
    │
    ▼
Morning report on first conversation of the day:
"Learned 3 new skills overnight: cisco-ios, synology-dsm7, vmware-esxi-8"
```

---

## NixOS configuration management

This is the most critical part — the agent manages its own host system.

**Zone tagging system:**
```nix
# @zone:network-config @managed:argos @restart:networking
networking.hostName = "hostname";

# @zone:gpu-drivers @managed:human @critical
hardware.graphics.enable = true;

# @argos:do-not-touch
boot.kernelPackages = pkgs.linuxPackages_6_12;
```

The agent reads these tags before any modification:
- `@managed:argos` → can modify freely
- `@managed:human` → will not touch, ever
- `@critical` → requires explicit confirmation
- `@argos:do-not-touch` → hard block, no exceptions

**Rebuild flow (strict, no exceptions):**
```bash
# Step 1: work in /tmp, never directly in /etc/nixos/
cp /etc/nixos/configuration.nix /tmp/configuration.nix.test
# ... make changes to /tmp/configuration.nix.test ...

# Step 2: syntax validation
nix-instantiate --eval /tmp/configuration.nix.test

# Step 3: full dry build (no system changes)
nixos-rebuild dry-build -I nixos-config=/tmp/configuration.nix.test

# Step 4: only if both pass
cp /tmp/configuration.nix.test /etc/nixos/configuration.nix
nixos-rebuild switch --show-trace

# Step 5: post-rebuild
nixos_index.py  # update config zone index in DB
```

**Retry logic:** max 3 attempts. Each failure triggers error analysis, correction in /tmp, revalidation. After 3 failures: full report + asks user whether to continue.

**Watchdog:** Before switch, saves `rebuild_started_at` to DB settings. If `rebuild_finished_at` not set within 5 minutes, forces system reboot and logs NIXOS001 to debug_logs.

**Rollback:** Switch failure → immediate `nixos-rebuild switch --rollback` without asking. Rollback failure → CRITICAL report, full stop.

---

## Autonomy model

The system operates at configurable autonomy levels, controlled exclusively by the user:

```
Level 0: Read-only. Everything requires approval.

Level 1 (current):
  Allowed without approval:
    systemctl restart/reload/start <service>
    journalctl, systemctl status
  
  Always blocked:
    rm -rf
    dd if=
  
  Requires create_job (approval queue):
    nixos-rebuild switch
    qm destroy / qm create (Proxmox VM ops)
    mkfs, parted (disk operations)
    Any UniFi configuration change

Level 2 (planned): Low-impact changes (temporary firewall rules)
Level 3 (planned): Permanent changes after success_rate > threshold
Level 4 (future):  Fully autonomous with post-facto notification
```

Levels are unlocked manually. The system cannot promote its own autonomy level.

---

## Multi-provider routing

```
All providers controlled by independent toggles stored in DB:

CLAUDE  (primary)   -- claude-sonnet-4-6, full tool use
GROK    (secondary) -- grok-4.20, web search, reasoning
LOCAL   (tertiary)  -- qwen3:14b via Ollama, free, no API cost

Routing logic:
  Read-only SSH commands     → auto-routed to LOCAL (free)
  Simple questions           → CLAUDE direct
  Complex questions          → CLAUDE + GROK reasoning injected
  (how/why/recommend/compare/error/not working triggers Grok)
  
  If CLAUDE off + GROK on    → GROK direct
  If both off                → LOCAL
```

**Grok reasoning injection:**
```python
# Simplified logic
if _should_consult_grok(user_message):
    grok_perspective = await _grok_reasoning(user_message)
    if grok_perspective:
        system_prompt += f"\n\n[EXTERNAL PERSPECTIVE - evaluate and decide]\n{grok_perspective}"
```

The injected perspective is clearly labeled. Claude decides whether to use it.

---

## Job system (approval queue)

Destructive operations are never executed directly:

```
User: "delete VM 115"
    │
    ▼
Argos detects: qm destroy = destructive
    │
    ▼
create_job called:
  title: "Delete VM 115"
  steps: ["qm stop 115", "qm destroy 115"]
  target: "proxmox-host"
  risk_level: "high"
    │
    ▼
Job saved to DB with status: pending_approval
UI shows approval button
    │
    ▼
User approves
    │
    ▼
Steps executed sequentially
Each step logged to debug_logs
```

---

## Debug system

All errors produce structured log entries:

```
debug_logs:
  ts        -- timestamp
  level     -- DEBUG / INFO / WARN / ERROR / CRITICAL
  module    -- chat / executor / kb / skill / api
  code      -- standardized error code
  message   -- human readable
  context   -- JSONB with relevant data

Error codes:
  KB001/002   -- knowledge base insert/query fail
  SSH001      -- SSH connection fail / permission denied
  SSH002      -- SSH timeout
  SSH003      -- command returned non-zero
  API001      -- Anthropic API error
  API002      -- Grok API error
  API003      -- Ollama error
  SKILL001    -- skill load fail
  SKILL002    -- skill not found
  DB001/002   -- pool/query fail
  NIXOS001    -- rebuild watchdog triggered reboot
  REASON001   -- Grok reasoning consulted
  ERR001      -- generic exception
```

Endpoint: `GET /api/debug/logs?limit=50&code=SSH001&level=ERROR`

---

## Self-modification

The agent can modify its own code. This sounds dangerous. The controls:

1. `code_edit` tool always requires explicit user request
2. Before modification: backup current file to DB (versioned: current/previous/lts/v4)
3. `v4` version is marked SACRA — never overwritten automatically
4. After modification: argos service restarted automatically
5. Watchdog checks health within 10 seconds
6. If health check fails: automatic rollback to lts version

The agent has modified its own code hundreds of times during development. The rollback has triggered multiple times. Both work correctly.

---

## What this is not

- Not a demo. Runs on production infrastructure managing real VMs, real switches, real home automation.
- Not a prompt wrapper. The tool use loop, knowledge base, and skill system are custom code running as a systemd service.
- Not stateless. Every conversation, every command, every outcome is stored. The system's operational knowledge compounds over time.
- Not complete. Autonomy level 1 is active. Levels 2-4 are planned and will be unlocked manually as the system demonstrates reliability.

---

## Current skill coverage

Systems the agent has documented skills for:

| System | Source |
|--------|--------|
| NixOS 25.11 | Manual |
| Proxmox VE 8.x | Manual |
| UniFi OS 4.x | Manual |
| Debian 12 | Manual |
| Home Assistant OS | Manual |
| ESPHome 2024 | Manual |
| Arduino (bare metal) | Manual |
| Linux generic | Manual |
| Windows generic | Manual |
| Pentest generic | Manual |
| Claude API | Manual |
| Grok API | Manual |
| Ollama local | Manual |
| Argos Mobile | Manual |
| iDRAC 9 (Dell) | Auto-generated |
| MikroTik RouterOS | Auto-generated |
| Cisco IOS | Auto-generated |
| Synology DSM 7 | Auto-generated |
| TrueNAS Scale | Auto-generated |
| VMware ESXi 8 | Auto-generated |
| VMware ESXi (generic) | Auto-generated |
| TrueNAS (generic) | Auto-generated |
| iDRAC Dell (generic) | Auto-generated |

Auto-generated skills are researched via Grok web search and structured by Claude. They are marked as unvalidated until used successfully in production.
