```markdown
# idrac-dell
version: iDRAC9 (detected: 7.x – see `racadm getconfig -f idrac.cfg` or UI)
os: bare-metal (Dell PowerEdge, IPMI/RACADM over network sau local)
loaded_when: Dell PowerEdge server with iDRAC9 detected in network or explicitly mentioned

---

## Detectie

```bash
# Versiune firmware iDRAC (local sau SSH)
racadm getversion

# Alternativ via SSH la iDRAC
ssh root@<idrac-ip> racadm getversion

# From host OS (if racadm is installed)
racadm -r <idrac-ip> -u root -p <pass> getversion

# Via IPMI (din OS)
ipmitool -I lanplus -H <idrac-ip> -U root -P <pass> mc info

# Via Redfish API
curl -sk https://<idrac-ip>/redfish/v1/Managers/iDRAC.Embedded.1 \
  -u root:<pass> | python3 -m json.tool | grep FirmwareVersion
```

---

## Comenzi de baza

```bash
# === CONECTARE ===
ssh root@<idrac-ip>                          # SSH direct la iDRAC
racadm -r <idrac-ip> -u root -p <pass> <cmd> # Remote RACADM

# === STATUS GENERAL ===
racadm getsysinfo                            # Info sistem complet
racadm getversion                            # Versiune firmware
racadm getsensorinfo                         # Senzori (temp, fan, voltaj)
racadm getsel                                # System Event Log
racadm lclog view                            # Lifecycle Controller Log

# === POWER MANAGEMENT ===
racadm serveraction powerdown                # Graceful shutdown
racadm serveraction powerup                  # Pornire
racadm serveraction powercycle               # Power cycle (hard)
racadm serveraction gracefulreboot           # Graceful reboot
racadm serveraction hardreset                # Reset hard

# Verificare stare power
racadm get system.power.status

# === iDRAC NETWORK ===
racadm get iDRAC.IPv4                        # Current IP config
racadm set iDRAC.IPv4.Address <ip>           # Setare IP static
racadm set iDRAC.IPv4Static.Address <ip>     # ⚠ Use IPv4Static (not IPv4)
racadm set iDRAC.IPv4Static.Netmask <mask>
racadm set iDRAC.IPv4Static.Gateway <gw>
racadm set iDRAC.IPv4.DHCPEnable 0           # Dezactivare DHCP

# === UTILIZATORI ===
racadm get iDRAC.Users                       # Lista utilizatori
racadm set iDRAC.Users.2.Password <newpass>  # Change password for user 2 (root)
racadm set iDRAC.Users.2.Enable 1            # Activare user

# === FIRMWARE UPDATE ===
racadm update -f <firmware.exe> -e <type>    # Update firmware
racadm jobqueue view                          # Check job queue
racadm jobqueue delete -i <JID>              # Delete job

# === EXPORT / IMPORT CONFIG (SCP) ===
racadm get -t xml -f idrac_config.xml        # Export full config
racadm set -t xml -f idrac_config.xml        # Import config

# === RESET iDRAC ===
racadm racreset                              # Restart iDRAC (no OS impact)
racadm racreset soft                         # Soft reset

# === VIRTUAL CONSOLE / KVM ===
# Acces prin browser: https://<idrac-ip>
# Launch Console -> HTML5 sau Java

# === STORAGE ===
racadm storage get controllers               # Liste controllere RAID
racadm storage get pdisks -t pd             # Discuri fizice
racadm storage get vdisks -t vd            # Volume virtuale (RAID)
racadm storage get enclosures               # Enclosures

# === REDFISH API ===
# Inventar sisteme
curl -sk https://<idrac-ip>/redfish/v1/Systems/System.Embedded.1 \
  -u root:<pass> | python3 -m json.tool

# Power state
curl -sk https://<idrac-ip>/redfish/v1/Systems/System.Embedded.1 \
  -u root:<pass> | python3 -m json.tool | grep PowerState

# === LOGS ===
racadm getsel                                # SEL (System Event Log)
racadm lclog view -n 50                     # Last 50 LC Log entries
racadm getsel -c                             # Number of SEL entries
```

---

## Fisiere importante

```
# No traditional filesystem accessible; configuration is in iDRAC NV-RAM.
# Export/import se face prin SCP (Server Configuration Profile) XML/JSON.

# Export full config locally
racadm get -t xml -f /tmp/idrac_full_config.xml --clone

# Export config to NFS/CIFS share
racadm get -t xml -f idrac_config.xml \
  -l //192.168.1.100/share -u user -p pass

# Import config
racadm set -t xml -f /tmp/idrac_config.xml

# Lifecycle Controller Log (export)
racadm lclog export -f lc_log.xml \
  -l //192.168.1.100/share -u user -p pass

# RACADM local config file (if using racadm locally on OS)
/etc/sysconfig/racadm          # Linux – client configuration
C:\Program Files\Dell\SysMgt\rac5\racadm.cfg  # Windows

# Firmware update files (local staging)
/tmp/                          # iDRAC shell – staging temporar firmware

# Useful Redfish locations
https://<idrac-ip>/redfish/v1/                          # Root
https://<idrac-ip>/redfish/v1/Managers/iDRAC.Embedded.1  # iDRAC manager
https://<idrac-ip>/redfish/v1/Systems/System.Embedded.1   # Server system
https://<idrac-ip>/redfish/v1/Chassis/System.Embedded.1   # Chassis/hardware
https://<idrac-ip>/redfish/v1/UpdateService               # Firmware update
```

---

## Periculos / Ireversibil

> ⚠ **WARNING** – Commands below are destructive or irreversible.
> Confirm EXPLICITLY before execution. Do not run automatically.

```bash
# ============================================================
# ⛔ SYSTEM ERASE – DELETES EVERYTHING: OS, data, iDRAC config, LC Log
# ============================================================
# REQUIRES EXPLICIT CONFIRMATION
racadm systemerase -f

# Erase selectiv (PERICULOS)
racadm systemerase lcdata         # Delete Lifecycle Controller data
racadm systemerase overwritepd    # Suprascrie discuri fizice (IREVERSIBIL)
racadm systemerase cryptographicerase  # Cryptographic erase of drives (IRREVERSIBLE)

# ⚠ KNOWN BUG: DO NOT run `reinstallfw` immediately after `lcdata`
# May prevent creation of network firmware jobs
# First update/rollback network firmware
