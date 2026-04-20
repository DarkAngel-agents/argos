# argos-error-log
version: 1.0
os: any
loaded_when: any error occurs, debugging, pattern analysis, error code lookup

## Purpose
Log, normalize and track errors across all ARGOS nodes.
Generates short hash codes (8 char) per error type.
Code becomes active (usable in scripts) after 10 occurrences.
Zero external dependencies — uses docker exec psql internally.

## Script Location
```
~/.argos/argos-core/argos_error_log.py
```

## Database Tables
- `error_patterns` — active errors being tracked
- `error_history` — tombstones of resolved errors (generic summary only)

## Commands

### Log an error
```bash
python3 ~/.argos/argos-core/argos_error_log.py log \
  '<error message>' \
  '<category>' \
  '<node_hostname>' \
  '<node_os>' \
  '<script_name>' \
  '<command_that_failed>'
```

### Lookup error by hash
```bash
python3 ~/.argos/argos-core/argos_error_log.py get <hash>
```

### Mark error as resolved
```bash
python3 ~/.argos/argos-core/argos_error_log.py resolve \
  <hash> \
  '<short generic summary>' \
  '<node_hostname>'
```

## Category Format
First word must be one of: docker, db, ssh, nixos, swarm, python, bash, generic
Examples: db-connectivity, docker-network, ssh-timeout, nixos-rebuild, swarm-rejected

## Normalization Rules
Automatically strips from message before hashing:
- IP addresses → <IP>
- Ports → <PORT>
- Timestamps → <TS>
- Hex strings >6 chars → <HEX>
- /tmp/... paths → /tmp/<FILE>
- /home/user/... → /home/<USER>
- Standalone numbers → <N>

## Code Active Logic
- count < 10: error tracked silently, no code emitted
- count >= 10: code_active=true, use [ERR:hash] in scripts and logs

## Retention Rules
- ARGOS proposes deletion after 6 months if not client_owned and not seen again
- resolved=true errors moved to error_history as generic tombstone
- ARGOS decides resolution — not automatic cron

## Example
```bash
python3 ~/.argos/argos-core/argos_error_log.py log \
  "Could not connect to 11.11.11.111:5432 — Connection refused" \
  "db-connectivity" "Beasty" "NixOS 25.11" "setup.sh" "psql -U claude"

# Returns:
# { "hash": "fadba05b", "count": 1, "code_active": false, ... }
# After 10 occurrences: [ERR:fadba05b] — cod activ
```

## DB Query — View Active Errors
```bash
docker exec argos-db psql -U claude -d claudedb -c \
  "SELECT hash, category, count, last_seen FROM error_patterns WHERE resolved=FALSE ORDER BY count DESC;"
```
