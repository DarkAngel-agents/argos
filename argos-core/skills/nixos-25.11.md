# nixos-25.11
version: 25.11
os: nixos
loaded_when: NixOS machine detected

## Detection
```bash
nixos-version
nix --version
cat /etc/nixos/configuration.nix | head -20
```

## Rebuild - MANDATORY FLOW
```bash
# 1. Test in /tmp first
cp /etc/nixos/configuration.nix /tmp/configuration.nix.test
# edit /tmp/configuration.nix.test
nix-instantiate --eval /tmp/configuration.nix.test
nixos-rebuild dry-build -I nixos-config=/tmp/configuration.nix.test
# 2. Validate paths
grep -E "ExecStart|WorkingDirectory" /tmp/configuration.nix.test | grep -v "pkgs\." | grep -oP '"\K[^"]+' | while read p; do
  [ ! -e "$p" ] && echo "MISSING PATH: $p"
done
# 3. If both OK: apply
sudo cp /tmp/configuration.nix.test /etc/nixos/configuration.nix
sudo nixos-rebuild switch --show-trace 2>&1 | tail -20
# 4. Update index
python3.13 ~/.argos/argos-core/nixos_index.py
```

## Generations
```bash
sudo nix-env --list-generations --profile /nix/var/nix/profiles/system
sudo nixos-rebuild switch --rollback
sudo nix-collect-garbage -d
```

## Packages
```bash
nix-env -qaP <package>        # search
nix-shell -p <package>        # temporary shell
nix-env -iA nixpkgs.<package> # permanent user install
```

## Services
```bash
systemctl status <service>
sudo systemctl restart <service>
journalctl -u <service> -n 50 --no-pager
```

## Store
```bash
du -sh /nix/store
nix store gc
nix-store --verify --check-contents
```

## Firewall (configuration.nix)
```nix
networking.firewall = {
  enable = true;
  allowedTCPPorts = [ 22 80 443 666 2049 2377 7946 8000 ];
  allowedUDPPorts = [ 4789 7946 ];
};
```

## Docker in NixOS (configuration.nix)
```nix
virtualisation.docker = {
  enable = true;
  enableOnBoot = true;
  autoPrune = { enable = true; dates = "weekly"; };
  daemon.settings = {
    dns = [ "8.8.8.8" "1.1.1.1" ];
    insecure-registries = [ "11.11.11.111:5000" ];
  };
  enableNvidia = true;
};
hardware.nvidia-container-toolkit.enable = true;
```

## Systemd service in NixOS (configuration.nix)
```nix
systemd.services.<name> = {
  description = "Service description";
  after = [ "network-online.target" ];
  wants = [ "network-online.target" ];
  wantedBy = [ "multi-user.target" ];
  serviceConfig = {
    ExecStart = "/run/current-system/sw/bin/<binary> <args>";
    User = "darkangel";
    Restart = "always";
    RestartSec = 10;
  };
};
```

## Systemd timer in NixOS (configuration.nix)
```nix
systemd.services.<name> = {
  description = "One-shot task";
  serviceConfig = {
    ExecStart = "/run/current-system/sw/bin/<binary> <args>";
    User = "darkangel";
    Type = "oneshot";
  };
};
systemd.timers.<name> = {
  description = "<name> timer";
  wantedBy = [ "timers.target" ];
  timerConfig = {
    OnBootSec = "2min";
    OnUnitActiveSec = "5min";
    Unit = "<name>.service";
  };
};
```

## NFS server in NixOS (configuration.nix)
```nix
services.nfs.server = {
  enable = true;
  exports = "/path/to/export <client-IP>(ro,sync,no_subtree_check)";
};
# Port 2049 must be open in firewall
```

## Known gotchas NixOS 25.11
- NEVER use apt/yum/dnf — they do not exist
- Binaries in /run/current-system/sw/bin not /usr/bin
- ssh binary: /run/current-system/sw/bin/ssh — use full path in systemd ExecStart
- Python/Node must be in nix-shell or configuration.nix
- sudo path: /run/wrappers/bin/sudo
- hardware.opengl.* -> hardware.graphics.*
- kate -> kdePackages.kate
- hardware.pulseaudio -> services.pulseaudio
- PATH in systemd -> lib.mkForce
- After rebuild always run: python3.13 ~/.argos/argos-core/nixos_index.py
- kernel modules: boot.kernelModules in configuration.nix
- NEVER write directly to /etc/nixos/ without dry-build first
- Max 3 rebuild retries, then report + ask
- Rollback automatic on switch fail

## ARGOS on Beasty (11.11.11.111)
- argos systemd service: DISABLED (replaced by Docker Swarm)
- argos-watchdog: still active as systemd service
- argos-rsync timer: syncs argos-core to Hermes every 5 minutes via rsync+ssh
- WorkingDirectory: /home/darkangel/.argos/argos-core
- Watchdog: /home/darkangel/.argos/argos-core/argos_watchdog.py
