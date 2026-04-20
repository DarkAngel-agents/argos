# ARGOS Linux Admin Reasoning
# Domain: linux system administration
# NEVER auto-modified. Edit manually only.

## BEFORE ANY CHANGE
- Check current state: systemctl status, journalctl -u, df -h, free -m
- Identify which machine: Beasty (11.11.11.111 NixOS) or Hermes (11.11.11.98 Debian)
- NixOS changes go in configuration.nix, never direct package install

## COMMAND SCORING (inherits base.md tool_scores)
- systemctl restart <service>: allowed, low risk
- nixos-rebuild switch: ask_first, high impact
- rm -rf: never_alone, always confirm
- apt install / nix-env: ask_first

## NIXOS SPECIFIC
- Edit /etc/nixos/configuration.nix, then nixos-rebuild switch
- Never pip install without --break-system-packages or venv
- conda requires conda-shell wrapper, not direct conda
- Python multiline file edits only, never sed

## DEBIAN SPECIFIC  
- Hermes = Debian 13, Docker Swarm worker/leader
- apt update before install
- systemd services, not init.d

## ERROR PATTERN
STATUS: FAIL
CAUSE: service X not responding on port Y
ACTION: check journalctl -u X --tail 50, then docker logs X if containerized
