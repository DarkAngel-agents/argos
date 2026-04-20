# ARGOS Networking Reasoning
# Domain: network protocols, UniFi, HAProxy, DNS
# NEVER auto-modified. Edit manually only.

## BEFORE ANY CHANGE
- Never approximate IPs - always verify with ip a or ifconfig
- Check connectivity before diagnosing: ping, curl, nc -zv
- UniFi topology: UDM Pro home (11.11.11.1) + 4 remote sites via Site Magic

## IP MAP (static, never approximate)
- Beasty: 11.11.11.111 (NixOS, Docker Swarm worker)
- Hermes: 11.11.11.98 (Debian 13, Swarm Leader)
- Zeus: 11.11.11.53 (Vikunja), 11.11.11.95 (n8n), 11.11.11.74 (LightRAG)
- HAProxy: port 5433 -> routes to PostgreSQL primary

## HAPROXY
- Config: /etc/haproxy/haproxy.cfg on Hermes
- Beasty FIRST in server list (primary), Hermes second (standby)
- Failover < 3s, verify with: psql -h 11.11.11.98 -p 5433 -U claude -d claudedb

## UNIFI
- API token: stored in ARGOS env, never hardcode
- Site Magic = mesh across 5 sites, do not break WAN links
- Changes via UniFi controller, not direct device SSH unless emergency

## DNS
- AdGuard on LXC, upstream 8.8.8.8 (not Quad9 DoH - causes PTR spam)
- PTR query storm = upstream DoH issue, switch to plain UDP

## ERROR PATTERN
STATUS: FAIL
CAUSE: port X unreachable on host Y
ACTION: check firewall (ufw/nftables), check service binding (ss -tlnp), check routing
