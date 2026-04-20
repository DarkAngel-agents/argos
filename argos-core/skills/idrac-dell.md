```markdown
# idrac-dell
version: iDRAC9 (detectată: 7.x – vezi `racadm getconfig -f idrac.cfg` sau UI)
os: bare-metal (Dell PowerEdge, IPMI/RACADM over network sau local)
loaded_when: server Dell PowerEdge cu iDRAC9 detectat în rețea sau menționat explicit

---

## Detectie

```bash
# Versiune firmware iDRAC (local sau SSH)
racadm getversion

# Alternativ via SSH la iDRAC
ssh root@<idrac-ip> racadm getversion

# Din OS-ul host (dacă are racadm instalat)
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
racadm serveraction powerdown                # Oprire grațioasă
racadm serveraction powerup                  # Pornire
racadm serveraction powercycle               # Power cycle (hard)
racadm serveraction gracefulreboot           # Reboot grațios
racadm serveraction hardreset                # Reset hard

# Verificare stare power
racadm get system.power.status

# === REȚEA iDRAC ===
racadm get iDRAC.IPv4                        # Config IP curentă
racadm set iDRAC.IPv4.Address <ip>           # Setare IP static
racadm set iDRAC.IPv4Static.Address <ip>     # ⚠ Folosiți IPv4Static (nu IPv4)
racadm set iDRAC.IPv4Static.Netmask <mask>
racadm set iDRAC.IPv4Static.Gateway <gw>
racadm set iDRAC.IPv4.DHCPEnable 0           # Dezactivare DHCP

# === UTILIZATORI ===
racadm get iDRAC.Users                       # Lista utilizatori
racadm set iDRAC.Users.2.Password <newpass>  # Schimbare parolă user 2 (root)
racadm set iDRAC.Users.2.Enable 1            # Activare user

# === FIRMWARE UPDATE ===
racadm update -f <firmware.exe> -e <type>    # Update firmware
racadm jobqueue view                          # Verificare coadă joburi
racadm jobqueue delete -i <JID>              # Ștergere job

# === EXPORT / IMPORT CONFIG (SCP) ===
racadm get -t xml -f idrac_config.xml        # Export config completă
racadm set -t xml -f idrac_config.xml        # Import config

# === RESET iDRAC ===
racadm racreset                              # Restart iDRAC (fără impact OS)
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
racadm lclog view -n 50                     # Ultimele 50 intrări LC Log
racadm getsel -c                             # Număr intrări SEL
```

---

## Fisiere importante

```
# NU există filesystem tradițional accesibil; configurația este în NV-RAM iDRAC.
# Export/import se face prin SCP (Server Configuration Profile) XML/JSON.

# Export config completă local
racadm get -t xml -f /tmp/idrac_full_config.xml --clone

# Export config în share NFS/CIFS
racadm get -t xml -f idrac_config.xml \
  -l //192.168.1.100/share -u user -p pass

# Import config
racadm set -t xml -f /tmp/idrac_config.xml

# Lifecycle Controller Log (export)
racadm lclog export -f lc_log.xml \
  -l //192.168.1.100/share -u user -p pass

# RACADM config file local (dacă se folosește racadm local pe OS)
/etc/sysconfig/racadm          # Linux – configurație client
C:\Program Files\Dell\SysMgt\rac5\racadm.cfg  # Windows

# Firmware update files (local staging)
/tmp/                          # iDRAC shell – staging temporar firmware

# Locații utile Redfish
https://<idrac-ip>/redfish/v1/                          # Root
https://<idrac-ip>/redfish/v1/Managers/iDRAC.Embedded.1  # iDRAC manager
https://<idrac-ip>/redfish/v1/Systems/System.Embedded.1   # Server system
https://<idrac-ip>/redfish/v1/Chassis/System.Embedded.1   # Chassis/hardware
https://<idrac-ip>/redfish/v1/UpdateService               # Firmware update
```

---

## Periculos / Ireversibil

> ⚠️ **ATENȚIE MIHAI** – Comenzile de mai jos sunt distructive sau ireversibile.
> Confirmă EXPLICIT înainte de execuție. Nu rula automat.

```bash
# ============================================================
# ⛔ SYSTEM ERASE – ȘTERGE TOT: OS, date, config iDRAC, LC Log
# ============================================================
# NECESITĂ CONFIRMARE EXPLICITĂ MIHAI
racadm systemerase -f

# Erase selectiv (PERICULOS)
racadm systemerase lcdata         # Șterge Lifecycle Controller data
racadm systemerase overwritepd    # Suprascrie discuri fizice (IREVERSIBIL)
racadm systemerase cryptographicerase  # Ștergere criptografică discuri (IREVERSIBIL)

# ⚠️ BUG CUNOSCUT: NU rula `reinstallfw` imediat după `lcdata`
# Poate preveni crearea joburilor pentru firmware de rețea
# Întâi actualizează/rollback firmware reț