# @host:nanite @iso-type:argos-nanite @build-version:0002
# @managed:argos @category:client @purpose:nanite-live
# Argos Nanite - ISO live minimal, anunt hardware la boot
{ config, pkgs, lib, ... }:
let
  argosUrl = "http://11.11.11.111:666";
  naniteVersion = "1.0";
  authorizedKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBL3NI1LjCZtHYTq8g5ng2fNyggaOBTJe0TGlM/uORgg argos@beasty";

  # Script de detectie hardware + anunt
  naniteAnnounce = pkgs.writeScriptBin "nanite-announce" ''
    #!/run/current-system/sw/bin/bash
    set -e

    ARGOS_URL="${argosUrl}"
    LOG_TAG="[NANITE]"

    echo "$LOG_TAG Boot Argos Nanite v${naniteVersion}"

    # Asteapta retea
    MAX_WAIT=60
    WAITED=0
    echo -n "$LOG_TAG Waiting for network"
    while true; do
      IP=$(${pkgs.iproute2}/bin/ip -4 addr show scope global \
        | ${pkgs.gnugrep}/bin/grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)
      [ -n "$IP" ] && break
      echo -n "."
      sleep 2
      WAITED=$((WAITED + 2))
      [ $WAITED -ge $MAX_WAIT ] && { echo ""; echo "$LOG_TAG ERROR: No network"; exit 1; }
    done
    echo ""
    echo "$LOG_TAG IP: $IP"

    # Genereaza node_id
    NODE_ID="nanite-$(cat /proc/sys/kernel/random/uuid | tr -d '-' | head -c 8)"
    echo "$LOG_TAG Node ID: $NODE_ID"

    # Detectie CPU
    CPU_MODEL=$(${pkgs.util-linux}/bin/lscpu | ${pkgs.gnugrep}/bin/grep "^Model name" \
      | ${pkgs.gnused}/bin/sed 's/Model name:[ \t]*//' | ${pkgs.coreutils}/bin/tr -d '\n')
    CPU_CORES=$(${pkgs.util-linux}/bin/lscpu | ${pkgs.gnugrep}/bin/grep "^Core(s) per socket" \
      | ${pkgs.gawk}/bin/awk '{print $NF}')
    CPU_THREADS=$(${pkgs.util-linux}/bin/lscpu | ${pkgs.gnugrep}/bin/grep "^CPU(s):" \
      | ${pkgs.gawk}/bin/awk '{print $NF}')
    ARCH=$(uname -m)

    # RAM
    RAM_KB=$(${pkgs.gnugrep}/bin/grep MemTotal /proc/meminfo | ${pkgs.gawk}/bin/awk '{print $2}')
    RAM_MB=$((RAM_KB / 1024))

    # UEFI
    UEFI="false"
    [ -d /sys/firmware/efi ] && UEFI="true"

    # GPU
    GPU=$(${pkgs.pciutils}/bin/lspci 2>/dev/null \
      | ${pkgs.gnugrep}/bin/grep -i "vga\|3d\|display" \
      | ${pkgs.gnused}/bin/sed 's/.*: //' | head -1 || echo "")

    # Discuri
    DISKS_JSON="["
    FIRST=1
    for DISK in $(ls /sys/block/ | ${pkgs.gnugrep}/bin/grep -v "loop\|sr\|fd"); do
      SIZE_BYTES=$(cat /sys/block/$DISK/size 2>/dev/null || echo 0)
      SIZE_GB=$(echo "scale=1; $SIZE_BYTES * 512 / 1073741824" | ${pkgs.bc}/bin/bc 2>/dev/null || echo 0)
      ROTATIONAL=$(cat /sys/block/$DISK/queue/rotational 2>/dev/null || echo 0)
      TYPE="hdd"
      [ "$ROTATIONAL" = "0" ] && TYPE="ssd"
      echo "$DISK" | ${pkgs.gnugrep}/bin/grep -q "nvme" && TYPE="nvme"
      MODEL=$(cat /sys/block/$DISK/device/model 2>/dev/null | ${pkgs.coreutils}/bin/tr -d '\n' || echo "")
      [ $FIRST -eq 0 ] && DISKS_JSON="$DISKS_JSON,"
      DISKS_JSON="$DISKS_JSON{\"name\":\"$DISK\",\"size_gb\":$SIZE_GB,\"type\":\"$TYPE\",\"model\":\"$MODEL\"}"
      FIRST=0
    done
    DISKS_JSON="$DISKS_JSON]"

    # Interfete retea
    NICS_JSON="["
    FIRST=1
    for NIC in $(ls /sys/class/net/ | ${pkgs.gnugrep}/bin/grep -v "lo"); do
      MAC=$(cat /sys/class/net/$NIC/address 2>/dev/null || echo "")
      SPEED=$(cat /sys/class/net/$NIC/speed 2>/dev/null || echo "0")
      [ $FIRST -eq 0 ] && NICS_JSON="$NICS_JSON,"
      NICS_JSON="$NICS_JSON{\"name\":\"$NIC\",\"mac\":\"$MAC\",\"speed\":\"''${SPEED}Mbps\"}"
      FIRST=0
    done
    NICS_JSON="$NICS_JSON]"

    # PCI devices scurt
    PCI_JSON=$(${pkgs.pciutils}/bin/lspci 2>/dev/null \
      | ${pkgs.gawk}/bin/awk '{id=$1; $1=""; desc=substr($0,2); printf "{\"id\":\"%s\",\"desc\":\"%s\"}\n", id, desc}' \
      | head -20 \
      | ${pkgs.jq}/bin/jq -s '.' 2>/dev/null || echo "[]")

    # Trimite announce
    echo "$LOG_TAG Announcing to Argos..."
    CPU_CORES_INT=''${CPU_CORES:-0}
    CPU_THREADS_INT=''${CPU_THREADS:-0}
    RAM_MB_INT=''${RAM_MB:-0}
    PAYLOAD=$(${pkgs.jq}/bin/jq -n \
      --arg node_id    "$NODE_ID" \
      --arg ip         "$IP" \
      --arg hostname   "$(cat /proc/sys/kernel/hostname)" \
      --arg arch       "$ARCH" \
      --arg cpu_model  "$CPU_MODEL" \
      --argjson cpu_cores    "$CPU_CORES_INT" \
      --argjson cpu_threads  "$CPU_THREADS_INT" \
      --argjson ram_mb       "$RAM_MB_INT" \
      --argjson disks        "$DISKS_JSON" \
      --arg gpu        "$GPU" \
      --argjson network_interfaces  "$NICS_JSON" \
      --argjson pci_devices         "$PCI_JSON" \
      --arg nanite_version   "${naniteVersion}" \
      --argjson uefi   "$UEFI" \
      '{node_id:$node_id, ip:$ip, hostname:$hostname, arch:$arch, uefi:$uefi,
        cpu_model:$cpu_model, cpu_cores:$cpu_cores, cpu_threads:$cpu_threads,
        ram_mb:$ram_mb, disks:$disks, gpu:$gpu,
        network_interfaces:$network_interfaces, pci_devices:$pci_devices,
        nanite_version:$nanite_version}')

    for i in 1 2 3 4 5; do
      RESP=$(${pkgs.curl}/bin/curl -sf -X POST "$ARGOS_URL/api/nanite/announce" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" --connect-timeout 5 2>/dev/null)
      if [ $? -eq 0 ]; then
        echo "$LOG_TAG Announced OK: $RESP"
        break
      fi
      echo "$LOG_TAG Retry $i..."
      sleep 3
    done

    # Afiseaza info pe consola
    echo ""
    echo "╔══════════════════════════════════════╗"
    echo "║         ARGOS NANITE v${naniteVersion}            ║"
    echo "╠══════════════════════════════════════╣"
    echo "║  Node:  $NODE_ID"
    echo "║  IP:    $IP"
    echo "║  CPU:   $CPU_MODEL"
    echo "║  RAM:   ''${RAM_MB}MB"
    echo "║  Arch:  $ARCH  UEFI: $UEFI"
    echo "╠══════════════════════════════════════╣"
    echo "║  SSH:   ssh argos@$IP"
    echo "║  Argos: $ARGOS_URL"
    echo "╚══════════════════════════════════════╝"
    echo ""
  '';

in
{
  imports = [ <nixpkgs/nixos/modules/installer/cd-dvd/iso-image.nix> ];

  isoImage.makeEfiBootable = true;
  isoImage.makeUsbBootable = true;
  image.baseName = lib.mkForce "argos-nanite-v${naniteVersion}";
  isoImage.isoBaseName = "argos-nanite";
  isoImage.squashfsCompression = "zstd -Xcompression-level 6";

  # Kernel minimal
  boot.kernelPackages = pkgs.linuxPackages_6_12;
  boot.kernelParams = [ "console=tty1" "quiet" ];
  boot.loader.grub.enable = false;
  boot.initrd.availableKernelModules = [
    "ahci" "xhci_pci" "virtio_pci" "virtio_net" "vmxnet3"
    "e1000" "e1000e" "igb" "r8169" "nvme" "usb_storage" "sd_mod"
    "uas" "usbhid" "hid_generic"
  ];
  boot.kernelModules = [ "kvm-intel" "kvm-amd" ];
  boot.supportedFilesystems = [ "ext4" "vfat" "zfs" ];
  boot.zfs.forceImportRoot = false;

  networking.hostName = "nanite";
  networking.hostId = "b1c2d3e4";
  networking.useDHCP = true;
  networking.firewall.enable = false;

  time.timeZone = "Europe/Paris";

  # User argos
  users.users.argos = {
    isNormalUser = true;
    extraGroups = [ "wheel" "networkmanager" ];
    password = "argos";
  };

  security.sudo.extraRules = [{
    users = [ "argos" ];
    commands = [{ command = "ALL"; options = [ "NOPASSWD" ]; }];
  }];

  # SSH cu cheie Beasty
  services.openssh = {
    enable = true;
    settings = {
      PermitRootLogin = "no";
      PasswordAuthentication = true;
      PubkeyAuthentication = true;
      AuthorizedKeysFile = "/run/argos_keys/%u .ssh/authorized_keys";
    };
  };

  services.getty.autologinUser = "argos";

  # Servicii la boot
  systemd.services.setup-ssh-keys = {
    description = "Setup SSH keys";
    before = [ "sshd.service" ];
    requiredBy = [ "sshd.service" ];
    wantedBy = [ "multi-user.target" ];
    serviceConfig = { Type = "oneshot"; RemainAfterExit = true; };
    script = ''
      mkdir -p /run/argos_keys
      echo "${authorizedKey}" > /run/argos_keys/argos
      chmod 755 /run/argos_keys
      chmod 644 /run/argos_keys/argos
    '';
  };

  systemd.services.nanite-announce = {
    description = "Argos Nanite Announce";
    after = [ "network-online.target" "sshd.service" "setup-ssh-keys.service" ];
    wants = [ "network-online.target" ];
    wantedBy = [ "multi-user.target" ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      User = "argos";
      StandardOutput = "journal+console";
    };
    script = "${pkgs.bash}/bin/bash ${naniteAnnounce}/bin/nanite-announce";
  };

  # Pachete
  environment.systemPackages = with pkgs; [
    # Argos tools
    naniteAnnounce
    curl wget

    # Hardware detection
    pciutils usbutils lshw inxi smartmontools
    util-linux bc

    # Network tools
    nmap tcpdump wireshark-cli iftop nethogs mtr
    iproute2 iputils

    # Storage
    parted gptfdisk e2fsprogs dosfstools
    hdparm

    # System
    vim htop mc git rsync
    python3 jq
    file lsof strace

    # Extra networking
    ethtool arp-scan
  ];

  nix.settings = {
    experimental-features = [ "nix-command" "flakes" ];
    substituters = [ "https://cache.nixos.org/" ];
    trusted-public-keys = [ "cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY=" ];
  };
  nixpkgs.config.allowUnfree = true;
  system.stateVersion = "25.11";
}
