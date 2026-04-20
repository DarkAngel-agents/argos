# OpenClaw VM Setup — Debian 13 + Telegram + RAG Proxy + xAI Grok

## SCOP

This skill documents the complete setup of an OpenClaw gateway instance on a dedicated Debian 13 VM within the ARGOS homelab. It covers VM provisioning, OpenClaw installation and configuration, Telegram bot integration, ChromaDB-based RAG system, and a local RAG proxy that intercepts completions and injects relevant context before forwarding to xAI Grok. Use this skill to reproduce the environment from scratch or to diagnose issues with the running instance.

---

## PREREQUISITES

- **Hypervisor**: Proxmox VE on Zeus (11.11.11.11)
- **Network**: VLAN flat homelab subnet 11.11.11.0/24, DNS via AdGuard Home on Proxmox
- **Host-side**: No special Proxmox configuration required beyond standard VM creation
- **External**: xAI API key (console.x.ai), Telegram bot token (BotFather), phpBB forum API token

---

## VM CREATION

Created via Proxmox web UI:
- **Template**: Debian 13 Trixie netinstall ISO (downloaded directly)
- **CPU**: 2 vCPUs
- **RAM**: 4 GB
- **Disk**: 32 GB virtio, thin provisioned
- **Network**: virtio, bridge vmbr0 (homelab VLAN)
- **Boot order**: CD-ROM first for install, then disk

---

## OS INSTALLATION

- **OS**: Debian 13 Trixie (stable at time of install)
- **Hostname**: `claw`
- **IP**: `11.11.11.113` (static, set in `/etc/network/interfaces`)
- **User**: `darkangel` (sudo), root SSH disabled
- **Partition**: single ext4 root, no swap (VM has enough RAM)
- **SSH**: enabled, key-based auth for darkangel
- **Timezone**: Europe/Bucharest
- **Initial packages**:

```bash
apt update && apt upgrade -y
apt install -y curl wget git python3 python3-pip python3-venv nodejs npm sudo
```

Node.js version must be 22+. If apt gives an older version:

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt install -y nodejs
```

---

## OPENCLAW INSTALLATION

**Source**: npm global package (official OpenClaw distribution)

```bash
npm install -g openclaw
```

This installs the `openclaw` binary globally. Version installed: `2026.3.13 (61d171a)`.

**Initialize config**:

```bash
openclaw init
```

This creates `~/.openclaw/openclaw.json` and `~/.openclaw/workspace/`.

**Workspace structure created manually**:

```
~/.openclaw/workspace/
  SOUL.md                          # System prompt — keep under 20000 chars
  AGENTS.md                        # Agent behavior overrides
  skills/
    phpbb/
      SKILL.md                     # Forum tool instructions for the agent
      sync.py                      # Forum → forum_data.txt sync (legacy, replaced by sync_rag.py)
      forum_data.txt               # Legacy flat file (no longer primary data source)
  rag/
    rag.py                         # ChromaDB CRUD wrapper
    sync_rag.py                    # Incremental forum → RAG sync
    rag_proxy.py                   # RAG injection proxy (port 11435)
    forum_sync_state.json          # Sync state tracker
    db/                            # ChromaDB persistent storage
```

**systemd user service** (`~/.config/systemd/user/openclaw-gateway.service`):

```ini
[Unit]
Description=OpenClaw Gateway
After=network.target

[Service]
ExecStart=/usr/bin/openclaw start
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable openclaw-gateway
systemctl --user start openclaw-gateway
```

**Always restart via**:
```bash
systemctl --user restart openclaw-gateway
```
Never kill the process directly — OpenClaw manages session state.

---

## CONFIGURATION THAT WORKS

**`~/.openclaw/openclaw.json`** (relevant sections):

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "botToken": "<token in ~/.argos/argos-core/config/.env as OPENCLAW_TELEGRAM_TOKEN>",
      "dmPolicy": "allowlist",
      "allowFrom": ["8113171559"],
      "groupPolicy": "open",
      "streaming": "partial"
    }
  },
  "models": {
    "providers": {
      "xai": {
        "baseUrl": "http://127.0.0.1:11435/v1",
        "apiKey": "<key in ~/.argos/argos-core/config/.env as XAI_API_KEY>",
        "models": [{ "id": "grok-4-1-fast-non-reasoning" }]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "xai/grok-4-1-fast-non-reasoning"
      }
    }
  }
}
```

**Key config decisions**:
- `dmPolicy: allowlist` + `allowFrom: ["8113171559"]` — only Mihai's Telegram ID can DM the bot
- `groupPolicy: open` — all group members can interact
- `baseUrl` points to local RAG proxy on port 11435, NOT directly to xAI
- Model: `grok-4-1-fast-non-reasoning` — reasoning model adds unsolicited commentary; non-reasoning is more obedient

**`~/.openclaw/workspace/SOUL.md`** — must stay under 20000 chars or OpenClaw truncates it silently:

```
Esti asistentul clubului Outlaws MC Romania.
```

That's it. All behavioral rules go in the RAG proxy's SYSTEM_PROMPT, not here. Do NOT inject forum data into SOUL.md — it bloats the file over the limit.

---

## RAG SYSTEM

**Dependencies**:

```bash
pip3 install chromadb sentence-transformers requests --break-system-packages
```

**RAG proxy systemd service** (`~/.config/systemd/user/rag-proxy.service`):

```ini
[Unit]
Description=RAG Proxy for OpenClaw
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/darkangel/.openclaw/workspace/rag/rag_proxy.py
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
```

**RAG proxy** listens on `127.0.0.1:11435`, emulates OpenAI-compatible API. On each request it:
1. Extracts user message from the content array (OpenClaw sends messages as `[{type: text, text: ...}]` with metadata prefix — the proxy strips metadata and extracts the last plain text line)
2. Calls `rag.py search <query>` via subprocess (timeout: 60s — sentence-transformers takes ~30s on first call)
3. Injects RAG results into system prompt alongside SYSTEM_PROMPT
4. Forwards to xAI Grok and streams response back

**SYSTEM_PROMPT in proxy** (hardcoded, not in SOUL.md):

```python
SYSTEM_PROMPT = """Esti asistentul clubului Outlaws MC Romania.

REGULI ABSOLUTE - RESPECTA-LE FARA EXCEPTIE:
- Raspunzi EXACT la ce esti intrebat. NIMIC in plus.
- NICIODATA nu mentiona: vesta, echipament, trusa, reguli, obligatii nesolicitate
- NICIODATA nu mentiona sursa datelor
- NICIODATA nu adauga comentarii, observatii sau sfaturi la final
- NICIODATA nu folosi numele utilizatorului
- NICIODATA nu folosi tabele markdown cu |
- Ton neutru si scurt
- Raspunzi in limba in care esti intrebat"""
```

**Forum sync cron** (runs every 5 min):

```
*/5 * * * * python3 /home/darkangel/.openclaw/workspace/rag/sync_rag.py
*/5 * * * * python3 /home/darkangel/.openclaw/workspace/rag/email_monitor.py >> /tmp/email_monitor.log 2>&1
*/5 * * * * python3 /home/darkangel/.openclaw/workspace/rag/confirm_bot.py >> /tmp/confirm_bot.log 2>&1
```

**Forum IDs** (current as of March 2026):

| forum_id | name | access |
|----------|------|--------|
| 3 | Regulament/Rules | read |
| 4 | Membri/Members | read |
| 5 | Probati/Promates | read+write |
| 8 | Members list and personal data | read |
| 10 | Promotional materials | read |
| 11 | Contacts, maps | read |
| 12 | EVENTS | read+write (reminders) |
| 13 | Accounting | read |
| 15 | EVENTS Probati | read+write |
| 7, 9, 14 | Discutii generale / Different discussions / Vault | excluded |

**RAG collections**: `regulament`, `membri`, `probati`, `promotional`, `contacte`, `evenimente`, `contabilitate`

---

## VERIFICATION

```bash
# OpenClaw running
systemctl --user status openclaw-gateway

# RAG proxy running
systemctl --user status rag-proxy

# Proxy responds
curl http://127.0.0.1:11435/v1/models

# RAG search works
python3 ~/.openclaw/workspace/rag/rag.py search "eveniment" 2>/dev/null | grep -v "Warning\|Loading\|BertModel\|UNEXPECTED\|Notes"

# Forum sync works
python3 ~/.openclaw/workspace/rag/sync_rag.py

# Logs
journalctl --user -u openclaw-gateway -n 30 --no-pager
```

Functional test: send a message to the Telegram bot from Mihai's account (ID 8113171559) and verify a response comes back.

---

## GOTCHAS ENCOUNTERED

- **SOUL.md 20000 char limit**: OpenClaw silently truncates SOUL.md above 20000 chars. `update_soul.sh` was injecting forum data into it, bloating it to 21k+. Fix: remove `update_soul.sh` from cron, keep SOUL.md minimal, put all data in RAG.

- **dmPolicy ordering bug**: Running `openclaw config set channels.telegram.dmPolicy allowlist` before setting `allowFrom` causes a validation error because OpenClaw validates immediately. Fix: edit `~/.openclaw/openclaw.json` directly with Python and restart.

- **User message format**: OpenClaw sends messages to the API as `content: [{type: "text", text: "...metadata...\n\nactual message"}]` — not a plain string. The RAG proxy must extract the text field from the array and strip the metadata prefix to get the actual query for RAG search.

- **RAG subprocess timeout**: `sentence-transformers` loads the embedding model on first call (~30s). Default 15s timeout in subprocess causes RAG search to fail silently on first request after proxy restart. Fix: set timeout to 60s.

- **HTML entities in phpBB**: Forum posts contain `&#128197;` etc. Fix: `import html; text = html.unescape(text)` in sync_rag.py before storing.

- **BBCode in posts**: `[hr]`, `[b]`, `[/b]` etc. present in post text. Fix: replace in `clean_text()` before storing in RAG.

- **Grok reasoning model adds unsolicited comments**: `grok-4-1-fast-reasoning` adds safety notes, equipment reminders, source citations regardless of system prompt. Fix: use `grok-4-1-fast-non-reasoning`.

- **Session memory persists**: Bot remembers previous conversations including test data. Fix: `rm -f ~/.openclaw/agents/main/sessions/*.json` then restart gateway.

---

## INTEGRATION POINTS FOR ARGOS

- **VM IP**: `11.11.11.113` (static)
- **Hostname**: `claw`
- **Depends on**: xAI API (external), phpBB forum at `aoa.aoaromania.ro`, AdGuard DNS
- **Credentials location**: xAI API key and Telegram token should be moved to `~/.argos/argos-core/config/.env` — currently hardcoded in `rag_proxy.py` (technical debt)
- **Forum API token**: hardcoded in `sync_rag.py` and `rag_proxy.py` — move to .env
- **Nothing in ARGOS core currently depends on this VM** — it is a standalone service
- **Ports used**: 11435 (RAG proxy, localhost only), Telegram polling (outbound only)

---

## TODO

- [ ] Move all credentials (xAI key, Telegram token, forum API token) out of scripts and into `~/.argos/argos-core/config/.env`
- [ ] Fix RAG proxy: preload sentence-transformers embedder at proxy startup instead of per-request subprocess (eliminates 30s cold start)
- [ ] Implement second personal bot (`@hauncarojarvis_bot`, token in memory) with separate RAG collections and Ollama routing for sensitive data
- [ ] Implement WhatsApp notification monitoring via HA Companion App → webhook → PostgreSQL
- [ ] PostgreSQL migration: move ChromaDB + all persistent state to PostgreSQL on ARGOS primary node
- [ ] Add HA PostgreSQL history backend for energy/automation event logging
- [ ] Implement sensitive data routing: Grok for general queries, Ollama local for CNP/passport/banking data
- [ ] Auto-restart HA Companion App if `sensor.s24ultra_last_notification` not updated in 12h
- [ ] Credential rotation after project completion (xAI key, forum API token, Telegram tokens)

---

## ROLLBACK / DESTROY

```bash
# Stop services
systemctl --user stop openclaw-gateway rag-proxy
systemctl --user disable openclaw-gateway rag-proxy

# Remove data
rm -rf ~/.openclaw
rm -f ~/.config/systemd/user/openclaw-gateway.service
rm -f ~/.config/systemd/user/rag-proxy.service
systemctl --user daemon-reload

# Remove npm package
npm uninstall -g openclaw

# Remove Python deps (optional)
pip3 uninstall chromadb sentence-transformers --break-system-packages

# Remove cron jobs
crontab -l | grep -v "sync_rag\|email_monitor\|confirm_bot" | crontab -
```

To destroy the VM entirely: delete from Proxmox UI. No host-side traces beyond the VM disk.

---

## VEZI SI

- `argos-deploy/proxmox-vm-base` — base VM creation procedure on Zeus
- `argos-integrations/phpbb-api` — forum API wrapper and token management
- `argos-integrations/chromadb-rag` — RAG CRUD operations and collection management
- `argos-integrations/ha-companion-notifications` — HA Android sensor setup for notification monitoring
- OpenClaw docs: check `openclaw --help` and `openclaw config --help` for current CLI reference
- xAI models: `https://console.x.ai` — model names change; verify current non-reasoning model name before deploy
