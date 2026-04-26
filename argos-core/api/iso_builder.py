"""
ISO Builder - construieste, testeaza si gestioneaza ISO-uri NixOS
"""
import os
import json
import secrets
import asyncio
import asyncssh
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

router = APIRouter()

SSH_KEY     = os.path.expanduser("~/.ssh/id_ed25519")
ISO_DIR     = os.path.expanduser("~/ISO")
ARGOS_URL   = "http://11.11.11.111:666"
NIX_TEMPLATE_DIR = os.path.expanduser("~/argos-iso")

# ── Modele ────────────────────────────────────────────────────────────────────

class BuildISORequest(BaseModel):
    iso_type: str                          # argos-agent, nixos-server, etc
    params: dict = {}                      # parametri specifici build-ului
    proxmox_server: Optional[str] = "zeus"
    test_after_build: bool = True

class KBEntry(BaseModel):
    category: str
    iso_type: Optional[str] = None
    build_id: Optional[str] = None
    action: str
    context: dict = {}
    outcome: str                           # ok, failed, partial
    reason: Optional[str] = None
    skip: bool = False
    skip_reason: Optional[str] = None

# ── Helpers SSH ───────────────────────────────────────────────────────────────

async def _ssh(host: str, user: str, command: str, timeout: int = 30) -> dict:
    try:
        async with asyncssh.connect(
            host, username=user, client_keys=[SSH_KEY],
            known_hosts=None, connect_timeout=10
        ) as conn:
            r = await conn.run(command, timeout=timeout)
            return {
                "stdout": r.stdout.strip() if r.stdout else "",
                "stderr": r.stderr.strip() if r.stderr else "",
                "returncode": r.exit_status or 0
            }
    except Exception as e:
        from api.debug import argos_error as _ae; import asyncio as _aio
        try: _aio.get_event_loop().run_until_complete(_ae("iso_builder", "ERR001", str(e)[:200], exc=e))
        except: pass
        return {"stdout": "", "stderr": str(e), "returncode": 1}

async def _local(command: str, timeout: int = 600) -> dict:
    env = os.environ.copy()
    env["PATH"] = "/run/wrappers/bin:/run/current-system/sw/bin:" + env.get("PATH", "")
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "stdout": stdout.decode().strip(),
            "stderr": stderr.decode().strip(),
            "returncode": proc.returncode
        }
    except asyncio.TimeoutError:
        return {"stdout": "", "stderr": f"Timeout dupa {timeout}s", "returncode": 124}

# ── Knowledge Base ────────────────────────────────────────────────────────────

async def kb_check(pool, category: str, action: str, iso_type: str = None) -> Optional[dict]:
    """Verifica daca o actiune e bifata ca 'nu merge' in KB"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT * FROM knowledge_base
               WHERE category = $1 AND action ILIKE $2
               AND ($3::text IS NULL OR iso_type_id = (SELECT id FROM iso_types WHERE name = $3))
               AND skip = TRUE
               ORDER BY last_tried_at DESC LIMIT 1""",
            category, f"%{action[:50]}%", iso_type
        )
    return dict(row) if row else None


async def kb_log(pool, entry: KBEntry):
    """Salveza o intrare in KB"""
    async with pool.acquire() as conn:
        iso_type_id = None
        if entry.iso_type:
            iso_type_id = await conn.fetchval(
                "SELECT id FROM iso_types WHERE name = $1", entry.iso_type
            )
        # Verifica daca exista deja o intrare similara
        existing = await conn.fetchrow(
            "SELECT id, times_tried FROM knowledge_base WHERE category = $1 AND action = $2 LIMIT 1",
            entry.category, entry.action
        )
        if existing:
            await conn.execute(
                """UPDATE knowledge_base SET times_tried = times_tried + 1,
                   last_tried_at = NOW(), outcome = $1, reason = $2,
                   skip = $3, skip_reason = $4
                   WHERE id = $5""",
                entry.outcome, entry.reason, entry.skip, entry.skip_reason, existing["id"]
            )
        else:
            await conn.execute(
                """INSERT INTO knowledge_base
                   (category, iso_type_id, build_id, action, context, outcome, reason, skip, skip_reason)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                entry.category, iso_type_id, entry.build_id,
                entry.action, json.dumps(entry.context),
                entry.outcome, entry.reason, entry.skip, entry.skip_reason
            )

# ── Build ISO ─────────────────────────────────────────────────────────────────

async def _generate_nix_config(iso_type_row: dict, params: dict, build_id: str, version: int) -> str:
    """Genereaza configuration.nix pentru ISO"""
    iso_name    = iso_type_row["name"]
    display_ver = f"{version:04d}_{iso_name}"
    user        = params.get("user", "argos")
    password    = params.get("password", "argos")
    hostname    = params.get("hostname", iso_name)
    extra_pkgs  = params.get("extra_packages", [])
    default_pkgs = iso_type_row.get("default_packages") or []
    all_pkgs    = list(set(default_pkgs + extra_pkgs))
    pkgs_str    = " ".join(all_pkgs) if all_pkgs else "curl git vim"

    authorized_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBL3NI1LjCZtHYTq8g5ng2fNyggaOBTJe0TGlM/uORgg argos@beasty"

    return f"""# @host:{hostname} @iso-type:{iso_name} @build-id:{build_id} @build-version:{version:04d}
# @argos:iso-managed @display-version:{display_ver}
# @managed:argos @category:{iso_type_row['category']} @purpose:{iso_type_row['purpose']}
{{ config, pkgs, lib, ... }}:
let
  authorizedKey = "{authorized_key}";
in
{{
  imports = [ <nixpkgs/nixos/modules/installer/cd-dvd/iso-image.nix> ];

  isoImage.makeEfiBootable = true;
  isoImage.makeUsbBootable = true;
  isoImage.isoName = "{display_ver}.iso";

  boot.kernelPackages = pkgs.linuxPackages_6_12;
  boot.kernelParams = [ "console=tty1" ];
  boot.loader.grub.enable = false;
  boot.initrd.availableKernelModules = [
    "ahci" "xhci_pci" "virtio_pci" "virtio_net" "vmxnet3"
    "e1000" "e1000e" "igb" "r8169" "nvme" "usb_storage" "sd_mod"
  ];
  boot.kernelModules = [ "kvm-intel" "kvm-amd" "virtio_balloon" "virtio_scsi" ];
  boot.supportedFilesystems = [ "zfs" "ext4" "vfat" ];
  boot.zfs.forceImportRoot = false;

  networking.hostName = "{hostname}";
  networking.hostId = "a1b2c3d4";
  networking.useDHCP = true;
  networking.firewall.enable = false;
  time.timeZone = "Europe/Paris";

  users.users.{user} = {{
    isNormalUser = true;
    extraGroups = [ "wheel" ];
    password = "{password}";
  }};

  security.sudo.extraRules = [
    {{ users = [ "{user}" ]; commands = [ {{ command = "ALL"; options = [ "NOPASSWD" ]; }} ]; }}
  ];

  services.openssh = {{
    enable = true;
    settings = {{
      PermitRootLogin = "no";
      PasswordAuthentication = true;
      PubkeyAuthentication = true;
      AuthorizedKeysFile = "/run/argos_keys/%u .ssh/authorized_keys";
    }};
  }};

  services.getty.autologinUser = "{user}";

  systemd.services.setup-ssh-keys = {{
    description = "Setup SSH authorized keys";
    before = [ "sshd.service" ];
    requiredBy = [ "sshd.service" ];
    wantedBy = [ "multi-user.target" ];
    serviceConfig = {{ Type = "oneshot"; RemainAfterExit = true; }};
    script = ''
      mkdir -p /run/argos_keys
      echo "${{authorizedKey}}" > /run/argos_keys/{user}
      chmod 755 /run/argos_keys
      chmod 644 /run/argos_keys/{user}
    '';
  }};

  systemd.services.argos-announce = {{
    description = "Argos Agent Announce";
    after = [ "network-online.target" "sshd.service" "setup-ssh-keys.service" ];
    wants = [ "network-online.target" ];
    wantedBy = [ "multi-user.target" ];
    serviceConfig = {{ Type = "oneshot"; RemainAfterExit = true; User = "{user}"; StandardOutput = "journal+console"; }};
    script = ''
      ARGOS_URL="{ARGOS_URL}"
      MAX_WAIT=60; WAITED=0
      echo "=== ARGOS ISO {display_ver} BUILD:{build_id} ==="
      echo -n "Waiting for network"
      while true; do
        IP=$(${{pkgs.iproute2}}/bin/ip -4 addr show scope global | ${{pkgs.gnugrep}}/bin/grep -oP '(?<=inet\\s)\\d+(\\.(\\d+)){{3}}' | head -1)
        if [ -n "$IP" ]; then break; fi
        echo -n "."; sleep 2; WAITED=$((WAITED + 2))
        if [ $WAITED -ge $MAX_WAIT ]; then echo ""; echo "ERROR: No network"; exit 1; fi
      done
      echo ""; echo "IP: $IP"
      for i in 1 2 3 4 5; do
        if ${{pkgs.curl}}/bin/curl -sf -X POST "$ARGOS_URL/api/vm-announce" \\
          -H "Content-Type: application/json" \\
          -d "{{\"ip\":\"$IP\",\"hostname\":\"{hostname}\",\"status\":\"ready\",\"build_id\":\"{build_id}\",\"iso_type\":\"{iso_name}\"}}" \\
          --connect-timeout 5; then
          echo "Announced OK"; break
        fi
        sleep 3
      done
      echo "=== Ready: ssh {user}@$IP ==="
    '';
  }};

  environment.systemPackages = with pkgs; [
    {pkgs_str}
    (pkgs.writeScriptBin "argos-report" ''
      #!${{pkgs.bash}}/bin/bash
      IP="$1"; STATUS="$2"; MSG="$3"
      ${{pkgs.curl}}/bin/curl -sf -X POST "{ARGOS_URL}/api/vm-progress" \\
        -H "Content-Type: application/json" \\
        -d "{{\"ip\":\"$IP\",\"status\":\"$STATUS\",\"message\":\"$MSG\",\"build_id\":\"{build_id}\"}}" \\
        --connect-timeout 3 || true
      echo "[$STATUS] $MSG"
    '')
  ];

  nix.settings.experimental-features = [ "nix-command" "flakes" ];
  nixpkgs.config.allowUnfree = true;
  system.stateVersion = "25.11";
}}
"""


async def build_iso(pool, req: BuildISORequest) -> dict:
    """Construieste un ISO NixOS"""
    # Ia datele tipului ISO
    async with pool.acquire() as conn:
        iso_type = await conn.fetchrow(
            "SELECT * FROM iso_types WHERE name = $1 AND active = TRUE", req.iso_type
        )
        if not iso_type:
            return {"status": "failed", "error": f"Tip ISO necunoscut: {req.iso_type}"}

        proxmox = await conn.fetchrow(
            "SELECT * FROM proxmox_servers WHERE name = $1", req.proxmox_server
        )
        if not proxmox:
            return {"status": "failed", "error": f"Server Proxmox necunoscut: {req.proxmox_server}"}

        # Incrementeaza counter si genereaza IDs
        version = iso_type["version_counter"] + 1
        await conn.execute(
            "UPDATE iso_types SET version_counter = $1, updated_at = NOW() WHERE id = $2",
            version, iso_type["id"]
        )

    build_id = secrets.token_hex(8)  # 16 chars hex
    display_version = f"{version:04d}_{req.iso_type}"
    iso_filename = f"{display_version}.iso"

    # Merge params cu default
    default_params = iso_type["default_params"] or {}
    params = {**default_params, **req.params}

    # Creeaza inregistrarea in DB
    async with pool.acquire() as conn:
        build_db_id = await conn.fetchval(
            """INSERT INTO iso_builds
               (iso_type_id, version, build_id, display_version, params,
                path_beasty, proxmox_server_id, status, created_at, updated_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, 'building', NOW(), NOW())
               RETURNING id""",
            iso_type["id"], version, build_id, display_version,
            json.dumps(params),
            f"{ISO_DIR}/{iso_filename}",
            proxmox["id"]
        )

    print(f"[ISO] Build {display_version} ({build_id}) pornit")

    # Genereaza configuration.nix
    nix_config = await _generate_nix_config(dict(iso_type), params, build_id, version)

    # Scrie configuration.nix in dir temporar
    build_dir = f"/tmp/iso-build-{build_id}"
    os.makedirs(build_dir, exist_ok=True)
    nix_path = f"{build_dir}/configuration.nix"
    with open(nix_path, "w") as f:
        f.write(nix_config)

    # Copiaza hardware-configuration daca exista
    hw_src = f"{NIX_TEMPLATE_DIR}/hardware-configuration.nix"
    if os.path.exists(hw_src):
        import shutil
        shutil.copy(hw_src, f"{build_dir}/hardware-configuration.nix")

    start_time = datetime.now()

    # Build ISO
    print(f"[ISO] Compilez {display_version}...")
    build_result = await _local(
        f"cd {build_dir} && nix-build '<nixpkgs/nixos>' -A config.system.build.isoImage "
        f"-I nixos-config={nix_path} 2>&1",
        timeout=1800  # 30 minute max
    )

    duration = int((datetime.now() - start_time).total_seconds())

    if build_result["returncode"] != 0:
        error = build_result["stdout"][-500:] + build_result["stderr"][-200:]
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE iso_builds SET status = 'failed', error = $1, build_log = $2, build_duration_seconds = $3, updated_at = NOW() WHERE id = $4",
                error[:500], build_result["stdout"][-2000:], duration, build_db_id
            )
        await kb_log(pool, KBEntry(
            category="iso_build", iso_type=req.iso_type, build_id=build_id,
            action=f"nix-build {req.iso_type} v{version}",
            outcome="failed", reason=error[:300]
        ))
        return {"status": "failed", "build_id": build_id, "error": error[:300], "duration_s": duration}

    # Gaseste ISO-ul generat
    find_result = await _local(
        f"find {build_dir}/result -name '*.iso' 2>/dev/null | head -1"
    )
    iso_src = find_result["stdout"].strip()
    if not iso_src:
        return {"status": "failed", "build_id": build_id, "error": "ISO negasit dupa build"}

    # Copiaza in ~/ISO/
    os.makedirs(ISO_DIR, exist_ok=True)
    iso_dest = f"{ISO_DIR}/{iso_filename}"
    copy_result = await _local(f"cp {iso_src} {iso_dest}")

    # Copiaza pe Proxmox
    proxmox_iso_path = f"{proxmox['iso_path']}/{iso_filename}"
    copy_proxmox = await _ssh(
        proxmox["ip"], proxmox["ssh_user"],
        f"true"  # verificare conexiune
    )

    if copy_proxmox["returncode"] == 0:
        # accept-new = TOFU: write to known_hosts on first contact, then refuse
        # if the key changes. Audit H5 (was StrictHostKeyChecking=no).
        scp_result = await _local(
            f"scp -o StrictHostKeyChecking=accept-new -i {SSH_KEY} {iso_dest} "
            f"{proxmox['ssh_user']}@{proxmox['ip']}:{proxmox_iso_path}"
        )
        if scp_result["returncode"] != 0:
            print(f"[ISO] Warning: nu am putut copia pe {proxmox['name']}: {scp_result['stderr']}")
            proxmox_iso_path = None
    else:
        proxmox_iso_path = None

    # Salveaza nix_config si actualizeaza status
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE iso_builds SET status = 'built', path_beasty = $1, path_proxmox = $2,
               nix_config = $3, build_log = $4, build_duration_seconds = $5, updated_at = NOW()
               WHERE id = $6""",
            iso_dest, proxmox_iso_path, nix_config,
            build_result["stdout"][-2000:], duration, build_db_id
        )

    await kb_log(pool, KBEntry(
        category="iso_build", iso_type=req.iso_type, build_id=build_id,
        action=f"nix-build {req.iso_type} v{version}",
        outcome="ok", reason=f"Build reusit in {duration}s"
    ))

    print(f"[ISO] Build {display_version} gata in {duration}s -> {iso_dest}")

    result = {
        "status": "built",
        "build_id": build_id,
        "display_version": display_version,
        "path_beasty": iso_dest,
        "path_proxmox": proxmox_iso_path,
        "duration_s": duration
    }

    # Test automat daca e cerut
    if req.test_after_build and proxmox_iso_path:
        print(f"[ISO] Pornesc test automat pentru {display_version}")
        test_result = await test_iso(pool, build_id, proxmox["id"], proxmox)
        result["test"] = test_result

    return result


async def test_iso(pool, build_id: str, proxmox_server_id: int, proxmox: dict) -> dict:
    """Testeaza ISO pe un VM temporar"""
    # Gaseste VMID liber
    vm_list = await _ssh(proxmox["ip"], proxmox["ssh_user"],
        "qm list | awk 'NR>1{print $1}' | sort -n | tail -1"
    )
    last_vmid = int(vm_list["stdout"].strip() or "100")
    test_vmid = last_vmid + 1

    # Gaseste ISO-ul pe Proxmox
    async with pool.acquire() as conn:
        build = await conn.fetchrow("SELECT * FROM iso_builds WHERE build_id = $1", build_id)

    iso_filename = os.path.basename(build["path_proxmox"] or "")
    if not iso_filename:
        return {"status": "failed", "error": "ISO nu e pe Proxmox"}

    # Creeaza VM test
    create_result = await _ssh(
        proxmox["ip"], proxmox["ssh_user"],
        f"qm create {test_vmid} --name test-iso-{build_id[:8]} --cores 1 --memory 1024 "
        f"--net0 virtio,bridge=vmbr0 --scsi0 local-zfs:4 "
        f"--ide2 local:iso/{iso_filename},media=cdrom "
        f"--boot order=ide2;scsi0 --ostype l26 --machine q35 --vga virtio "
        f"--scsihw virtio-scsi-pci && qm start {test_vmid}"
    )

    if create_result["returncode"] != 0:
        return {"status": "failed", "error": f"Nu am putut crea VM test: {create_result['stderr'][:200]}"}

    # Salvam test in DB
    async with pool.acquire() as conn:
        test_id = await conn.fetchval(
            """INSERT INTO iso_test_results (build_id, proxmox_server_id, test_vm_id, tested_at)
               VALUES ($1, $2, $3, NOW()) RETURNING id""",
            build_id, proxmox_server_id, test_vmid
        )

    # Asteapta announce (max 5 minute)
    print(f"[ISO] VM test {test_vmid} pornit, astept announce...")
    announced_ip = None
    for i in range(30):  # 30 x 10s = 5 minute
        await asyncio.sleep(10)
        async with pool.acquire() as conn:
            # Cauta in memories VM-ul anuntat cu build_id-ul nostru
            row = await conn.fetchrow(
                "SELECT value FROM memories WHERE key LIKE 'vm_%' AND value LIKE $1 ORDER BY updated_at DESC LIMIT 1",
                f"%{build_id}%"
            )
            if row:
                # Extrage IP din value
                import re
                ip_match = re.search(r'ip=(\d+\.\d+\.\d+\.\d+)', row["value"])
                if ip_match:
                    announced_ip = ip_match.group(1)
                    break

    if announced_ip:
        # Test SSH
        ssh_test = await _ssh(announced_ip, "argos", "hostname && echo OK")
        ssh_ok = ssh_test["returncode"] == 0

        async with pool.acquire() as conn:
            await conn.execute(
                """UPDATE iso_test_results SET announced = TRUE, test_vm_ip = $1,
                   announce_time_seconds = $2, ssh_success = $3,
                   boot_success = TRUE, tested_at = NOW()
                   WHERE id = $4""",
                announced_ip, (i + 1) * 10, ssh_ok, test_id
            )
            await conn.execute(
                "UPDATE iso_builds SET status = 'ok', updated_at = NOW() WHERE build_id = $1",
                build_id
            )

        # Sterge VM test
        await _ssh(proxmox["ip"], proxmox["ssh_user"],
            f"qm stop {test_vmid} 2>/dev/null; qm destroy {test_vmid} --destroy-unreferenced-disks 1 --purge 1"
        )

        print(f"[ISO] Test OK - VM anuntat la {announced_ip}")
        return {"status": "ok", "ip": announced_ip, "ssh": ssh_ok, "announce_time_s": (i + 1) * 10}
    else:
        # Nu s-a anuntat - retry o data
        print(f"[ISO] VM nu s-a anuntat, retry...")
        await _ssh(proxmox["ip"], proxmox["ssh_user"], f"qm reboot {test_vmid}")
        await asyncio.sleep(60)

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT value FROM memories WHERE key LIKE 'vm_%' AND value LIKE $1 ORDER BY updated_at DESC LIMIT 1",
                f"%{build_id}%"
            )

        if row:
            return {"status": "ok", "note": "anuntat dupa retry"}

        # Esec total - curata si rollback
        error_log = await _ssh(
            proxmox["ip"], proxmox["ssh_user"],
            f"qm showcmd {test_vmid} 2>/dev/null | head -5"
        )
        await _ssh(proxmox["ip"], proxmox["ssh_user"],
            f"qm stop {test_vmid} 2>/dev/null; qm destroy {test_vmid} --destroy-unreferenced-disks 1 --purge 1"
        )
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE iso_test_results SET error = $1, tested_at = NOW() WHERE id = $2",
                "VM nu s-a anuntat dupa 10 minute + retry", test_id
            )
            await conn.execute(
                "UPDATE iso_builds SET status = 'failed', error = 'Test esuat: VM nu s-a anuntat', updated_at = NOW() WHERE build_id = $1",
                build_id
            )

        await kb_log(pool, KBEntry(
            category="iso_build", build_id=build_id,
            action=f"test_vm_announce {build_id[:8]}",
            outcome="failed", reason="VM nu s-a anuntat dupa 10 minute + retry"
        ))

        print(f"[ISO] Test ESUAT pentru {build_id}")
        return {"status": "failed", "error": "VM nu s-a anuntat", "vm_cleaned": True}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/iso/build")
async def api_build_iso(req: BuildISORequest):
    from api.main import pool
    return await build_iso(pool, req)


@router.get("/iso/types")
async def api_iso_types():
    from api.main import pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, display_name, category, purpose, version_counter, active FROM iso_types ORDER BY category, name"
        )
    return {"types": [dict(r) for r in rows]}


@router.get("/iso/builds")
async def api_iso_builds(iso_type: str = None, status: str = None, limit: int = 20):
    from api.main import pool
    async with pool.acquire() as conn:
        query = """SELECT b.*, t.name as type_name, p.name as server_name
                   FROM iso_builds b
                   JOIN iso_types t ON b.iso_type_id = t.id
                   JOIN proxmox_servers p ON b.proxmox_server_id = p.id
                   WHERE 1=1"""
        args = []
        if iso_type:
            args.append(iso_type)
            query += f" AND t.name = ${len(args)}"
        if status:
            args.append(status)
            query += f" AND b.status = ${len(args)}"
        query += f" ORDER BY b.created_at DESC LIMIT {limit}"
        rows = await conn.fetch(query, *args)
    return {"builds": [dict(r) for r in rows]}


@router.get("/iso/builds/{build_id}")
async def api_iso_build_detail(build_id: str):
    from api.main import pool
    async with pool.acquire() as conn:
        build = await conn.fetchrow("SELECT * FROM iso_builds WHERE build_id = $1", build_id)
        if not build:
            raise HTTPException(status_code=404, detail="Build negasit")
        tests = await conn.fetch("SELECT * FROM iso_test_results WHERE build_id = $1", build_id)
    return {"build": dict(build), "tests": [dict(t) for t in tests]}


@router.get("/iso/proxmox-servers")
async def api_proxmox_servers():
    from api.main import pool
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, name, display_name, ip, iso_path, is_default FROM proxmox_servers ORDER BY is_default DESC")
    return {"servers": [dict(r) for r in rows]}


@router.post("/iso/kb")
async def api_kb_log(entry: KBEntry):
    from api.main import pool
    await kb_log(pool, entry)
    return {"status": "ok"}


@router.get("/iso/kb")
async def api_kb_list(category: str = None, skip_only: bool = False, limit: int = 50):
    from api.main import pool
    async with pool.acquire() as conn:
        query = "SELECT * FROM knowledge_base WHERE 1=1"
        args = []
        if category:
            args.append(category)
            query += f" AND category = ${len(args)}"
        if skip_only:
            query += " AND skip = TRUE"
        query += f" ORDER BY last_tried_at DESC LIMIT {limit}"
        rows = await conn.fetch(query, *args)
    return {"entries": [dict(r) for r in rows]}


@router.put("/iso/types/{type_name}/rename")
async def api_rename_iso_type(type_name: str, display_name: str):
    from api.main import pool
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE iso_types SET display_name = $1, updated_at = NOW() WHERE name = $2",
            display_name, type_name
        )
    return {"status": "ok", "name": type_name, "display_name": display_name}
