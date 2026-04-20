# argos-heartbeat
version: 2.0
os: any
loaded_when: heartbeat, health, fleet online, system offline, node status, ping fleet

## Architecture
heartbeat.py runs on each node as host process (NOT in container).
Reports CPU, memory, DB latency, container count every 2 seconds.
Updates system_profiles.online for fleet status.

## Locations
- Beasty: ~/.argos/argos-core/heartbeat.py (host process, nix-store Python)
- Hermes: /opt/argos/heartbeat.py (COPY via scp, not NFS symlink)
- DB_PASSWORD must be set as env var (not in .env file)

## Key Functions
- _bin(name): finds binary - NixOS /run/current-system/sw/bin/ first, then shutil.which, then name
- get_cpu(): reads /proc/stat, computes delta between readings
- get_mem(): reads /proc/meminfo with free -m fallback
- get_containers(): docker ps count (skip on hermes - NODE != 'hermes')
- ping_fleet(): runs on beasty only, every 30s, pings all system_profiles IPs
- write_to_db(): INSERT heartbeat_log + UPDATE system_profiles.online

## Start Commands
```bash
# Beasty (NixOS - needs nix-store Python with asyncpg)
DB_PASSWORD='...' nohup /nix/store/yf4nfs51z4ibzbv3pi20dz5spmdjdqcw-python3-3.13.12-env/bin/python3 ~/.argos/argos-core/heartbeat.py > /tmp/heartbeat_beasty.log 2>&1 &

# Hermes (Debian - system Python)
ssh root@11.11.11.98 "kill $(pgrep -f 'python3.*heartbeat.py') 2>/dev/null; DB_PASSWORD='...' nohup /usr/bin/python3 /opt/argos/heartbeat.py > /tmp/heartbeat.log 2>&1 &"
```

## After Code Change
1. Update file on disk (Beasty: direct edit, Hermes: scp)
2. Kill old process: kill $(pgrep -f 'python3.*heartbeat.py')
3. Start new process with DB_PASSWORD env var
4. Python does NOT hot-reload - must kill+restart

## Update Hermes Copy
```bash
scp ~/.argos/argos-core/heartbeat.py root@11.11.11.98:/opt/argos/heartbeat.py
```

## DB Tables
- heartbeat_log: raw readings (node, cpu_pct, mem_pct, db_latency_ms, containers_up)
- system_profiles: fleet status (online, last_seen) - updated by heartbeat
- heartbeat_checks: check definitions (used by health UI summary)

## Gotchas
- Hermes NFS share may have stale heartbeat.py - ALWAYS scp to /opt/argos/
- DB_PASSWORD not inherited from container env - must set explicitly
- Process survives SSH disconnect (nohup) but NOT host reboot (no systemd yet)
- ping_fleet uses _bin('ping') for NixOS PATH compatibility
- Container heartbeat (inside argos-swarm) is SEPARATE from host heartbeat
