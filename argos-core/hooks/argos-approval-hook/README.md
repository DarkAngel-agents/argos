# argos-approval-hook

Rust PreToolUse hook for Claude Code (2.1.25+). Part of **ARGOS Faza B Pas 2** (Vikunja #152).

Reads Claude Code hook JSON from stdin, maps the tool invocation to an ARGOS
`cc_*` `kind`, POSTs an approval request to the ARGOS API, polls until decision,
exits `0` (allow) or `2` (deny).

## Build (on Beasty, NixOS)

Requires Rust 1.75+ (apt Ubuntu 24.04) or newer. On NixOS:

```bash
nix-shell -p rustc cargo --run 'cd ~/.argos/argos-core/hooks/argos-approval-hook && cargo build --release'
```

or if `rustc`+`cargo` are already in system packages:

```bash
cd ~/.argos/argos-core/hooks/argos-approval-hook
cargo build --release
```

Binary output: `target/release/argos-approval-hook` (~1-2 MB stripped).

## Install

```bash
mkdir -p ~/bin
cp target/release/argos-approval-hook ~/bin/argos-approval-hook
chmod +x ~/bin/argos-approval-hook
```

## Configure in ~/.claude/settings.json

```json
{
  "mcpServers": { ... existing ... },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [
          { "type": "command", "command": "/home/darkangel/bin/argos-approval-hook" }
        ]
      }
    ]
  }
}
```

## Environment variables (optional)

| Var | Default | Purpose |
|---|---|---|
| `ARGOS_HOOK_URL` | `http://127.0.0.1:666` | ARGOS API base URL |
| `ARGOS_HOOK_DEBUG` | unset | Set to `1` to enable debug log |
| `ARGOS_HOOK_LOG` | `/tmp/argos_hook.log` | Debug log file path |
| `ARGOS_HOOK_TIMEOUT` | `1800` | Approval timeout in seconds |

## Tool mapping

| Claude Code tool | ARGOS kind | Notes |
|---|---|---|
| `Bash` | `cc_bash` | command + description |
| `Write`, `Edit`, `MultiEdit`, `NotebookEdit` | `cc_file` | path + operation |
| `Read`, `Grep`, `Glob`, `LS`, `WebFetch`, `WebSearch`, `TodoWrite`, `TodoRead`, `Task`, `NotebookRead`, `BashOutput`, `KillShell`, `ExitPlanMode` | (skip, exit 0) | Read-only / agent-internal |
| `<anything else>` | `cc_tool` | Generic fallback (MCP tools land here) |

## Exit codes

- `0` — allow tool to run
- `2` — deny; stderr message shown to Claude

## Fail-safe behavior

- ARGOS unreachable → deny (exit 2)
- Invalid stdin JSON → deny
- Consecutive poll errors ≥30 (= ~60s downtime) → deny

Never fails "open" — if in doubt, block.

## Test

```bash
cargo test
```

Unit tests include deserialization of real JSON captured live from Claude Code 2.1.25.
