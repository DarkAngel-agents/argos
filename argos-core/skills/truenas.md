```markdown
# truenas
version: "25.04.2.6 (Mission Critical) / 25.10.1 (General)"
os: "TrueNAS SCALE (Linux/Debian-based)"
loaded_when: "sistemul detectat este TrueNAS SCALE"

## Detectie

```bash
# Detectare versiune si tip
cat /etc/version
# sau
cli -c "system info" | grep -E "version|hostname"
# sau prin middleware
midclt call system.info | jq '{version: .version, hostname: .hostname}'

# Confirmare SCALE vs CORE
uname -a          # Linux = SCALE, FreeBSD = CORE
cat /etc/os-release | grep -E "NAME|VERSION"
```

## Comenzi de baza

```bash
# ── Informații sistem ────────────────────────────────────────
midclt call system.info
midclt call system.version

# ── ZFS Pool management ──────────────────────────────────────
zpool list                          # Lista pool-uri
zpool status                        # Status detaliat pool-uri
zpool status -v <pool>              # Status pool specific cu erori
zfs list                            # Lista toate dataset-urile
zfs list -t snapshot                # Lista snapshot-uri
zfs list | grep .system             # Dataset-uri sistem

# ── Snapshot-uri ─────────────────────────────────────────────
zfs snapshot <pool>/<dataset>@<nume>            # Creare snapshot
zfs rollback <pool>/<dataset>@<snapshot>        # Rollback la snapshot
zfs clone <pool>/<dataset>@<snap> <pool>/clone  # Clonare snapshot

# ── Servicii ─────────────────────────────────────────────────
midclt call service.query                       # Lista servicii
midclt call service.start '{"service": "ssh"}'  # Pornire serviciu
midclt call service.stop  '{"service": "ssh"}'  # Oprire serviciu
midclt call service.restart '{"service": "smb"}'

# ── Rețea ────────────────────────────────────────────────────
midclt call interface.query | jq '.[].name'
ip addr show
ip route show

# ── Aplicații (Apps/Docker) ───────────────────────────────────
midclt call app.query | jq '.[].name'
midclt call app.query | jq '.[] | {name, state}'
docker ps -a                        # Containere rulând
docker logs <container_id>          # Loguri container (workaround TTY bug)

# ── Configuratie backup/restore (CLI) ────────────────────────
midclt call systemdataset.config | jq '.path'
midclt call config.save '{"secretseed": true}'   # Export cu seed

# ── Loguri sistem ────────────────────────────────────────────
journalctl -u middlewared -f        # Log middleware live
journalctl -p err -b                # Erori din boot-ul curent
tail -f /var/log/syslog

# ── Utilizatori / permisiuni ─────────────────────────────────
midclt call user.query | jq '.[] | {id, username}'
midclt call group.query | jq '.[] | {id, group}'

# ── SMART / Disk health ──────────────────────────────────────
midclt call disk.query | jq '.[] | {name, serial, size}'
smartctl -a /dev/sd<X>

# ── Update ───────────────────────────────────────────────────
midclt call update.check_available
midclt call update.get_trains
```

## Fisiere importante

```
# ── TrueNAS SCALE ─────────────────────────────────────────────
/data/freenas-v1.db              # Baza de date SQLite principala (configuratie completa)
/etc/version                     # Versiune sistem

# Aplicatii
/mnt/.ix-apps/                   # Configuratii aplicatii
/mnt/.ix-apps/metadata.yaml      # Metadate aplicatii
/mnt/.ix-apps/app_configs/<app>/ # Config per-aplicatie
/mnt/.ix-apps/user_config.yaml   # Config utilizator aplicatii
/mnt/<pool>/ix-applications/releases/<app>/  # Volume aplicatii Kubernetes legacy

# SSH
/usr/local/etc/ssh/              # SSH host keys (ssh_host_* files)
/root/.ssh/authorized_keys       # Chei SSH root
/home/<user>/.ssh/authorized_keys

# Retea / Servicii (GENERATE LA BOOT - nu edita direct!)
/etc/                            # Fisiere runtime regenerate din DB la fiecare boot
/etc/hosts
/etc/resolv.conf
/etc/network/interfaces

# Loguri
/var/log/syslog
/var/log/middlewared.log

# Sistem dataset (montat dinamic)
<pool>/.system/configs-<hostid>/  # Backup-uri versionate ale configuratiei
/var/db/system/configs-<hostid>/  # Mountpoint runtime pentru configs

# ── TrueNAS CORE (FreeBSD - referinta) ────────────────────────
/data/freenas-v1.db              # Acelasi nume, SQLite
/conf/base/etc/                  # Template-uri baza pentru generare /etc/
/var/db/system/configs-<hostid>/ # Backup-uri versionate
```

> ⚠️ **IMPORTANT**: Fisierele din `/etc/` sunt **regenerate la fiecare boot** din baza de date.
> Orice modificare directa in `/etc/` este **pierduta la restart**. Foloseste UI sau `midclt` pentru modificari persistente.

> ⚠️ **SSH host keys si cheile root NU sunt incluse** in backup-ul de configuratie. Salveaza-le separat!

## Periculos / Ireversibil

> 🔴 **TOATE comenzile de mai jos necesita confirmare explicita din partea lui Mihai inainte de executie.**

```bash
# ── STERGERE POOL - IREVERSIBIL ──────────────────────────────
# ❌ DISTRUGE TOATE DATELE din pool
# CONFIRMARE EXPLICITA MIHAI OBLIGATORIE
zpool destroy <pool>

# ── STERGERE DATASET / SNAPSHOT ──────────────────────────────
# ❌ Date irecuperabile dupa executie
# CONFIRMARE EXPLICITA MIHAI OBLIGATORIE
zfs destroy <pool>/<dataset>
zfs destroy <pool>/<dataset>@<snapshot>
zfs destroy -r <pool>/<dataset>      # Recursiv - sterge tot sub dataset

# ── ROLLBACK SNAPSHOT ────────────────────────────────────────
# ❌ Suprascrie starea curenta a dataset-ului; datele post-snapshot se pierd
# CONFIRMARE EXPLICITA MIHAI OBLIGATORIE
zfs rollback -r <pool>/<dataset>@<snapshot>

# ── RESET CONFIGURATIE LA DEFAULT ────────────────────────────
# ❌ Sterge toata configuratia (useri, shares, servicii, etc.)
# CONFIRMARE EXPLICITA MIHAI OBLIGATORIE
# (Doar prin UI: System Settings > General > Manage Configuration > Reset to Defaults)
midclt call config.reset '{"reboot": true}'

# ── EXPORT POOL ──────────────────────────────────────────────
# ⚠️ Pool-ul devine inaccesibil pana la re-import
# CONFIRMARE EXPLICITA MIHAI OBLIGATORIE
zpool export <pool>

# ── SCRUB FORTAT (poate degrada performanta