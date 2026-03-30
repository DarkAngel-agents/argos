```markdown
# vmware-esxi
version: 8.0
os: VMware ESXi (Hypervisor bare-metal)
loaded_when: sistem detectat ca "OK vmware-esxi-8"

## Detectie
```bash
esxcli system version get
# Output contine: Version, Release, Build Number

esxcli software vib list | grep -i esx-base
# Confirma build exact si patch level

uname -a
# Arata kernel ESXi

esxcli system hostname get
# Hostname, domain, FQDN
```

## Comenzi de baza

### Informatii sistem
```bash
esxcli system version get                  # Versiune ESXi si build
esxcli system hostname get                 # Hostname / FQDN
esxcli hardware platform get              # Producator, model, serial, BIOS
esxcli hardware cpu list                  # Lista CPU-uri
esxcli hardware memory get                # Informatii memorie RAM
esxcli hardware pci list                  # Dispozitive PCI
esxcli system settings advanced list      # Setari avansate host
```

### Networking
```bash
esxcli network nic list                          # NIC-uri fizice (status, viteza, driver)
esxcli network ip interface list                 # Interfete VMkernel (vmk0, vmk1...)
esxcli network vswitch standard list             # vSwitch-uri standard si port groups
esxcli network firewall get                      # Status firewall
esxcli network firewall ruleset list             # Reguli firewall active
esxcli network firewall set --enabled true|false # Activa/dezactiveaza firewall
```

### Storage
```bash
esxcli storage core adapter list                 # Adaptoare HBA / iSCSI / NVMe
esxcli storage core device list                  # Dispozitive storage detectate
esxcli storage core path list                    # Cai catre dispozitive (multipath)
esxcli storage filesystem list                   # Filesystem-uri montate (VMFS, NFS) cu capacitate
esxcli storage core adapter rescan --all         # Rescan toate adaptoarele
esxcli storage vmfs extent list                  # Volume VMFS
esxcli storage core claimrule list               # Reguli claim storage
esxcli storage core device vaai status get -d <device>  # Status VAAI / UNMAP pe device
```

### Virtual Machines
```bash
esxcli vm process list                           # VMs care ruleaza + World ID
vim-cmd vmsvc/getallvms                          # Toate VM-urile inregistrate + cale .vmx
vim-cmd vmsvc/power.getstate <vmid>              # Stare power VM
vim-cmd vmsvc/power.on <vmid>                    # Pornire VM
vim-cmd vmsvc/power.off <vmid>                   # Oprire VM (fortat)
vim-cmd vmsvc/power.shutdown <vmid>              # Shutdown graceful VM
vim-cmd vmsvc/snapshot.get <vmid>                # Lista snapshot-uri VM
```

### Monitorizare / Troubleshooting
```bash
esxtop                                           # Monitor interactiv (C=CPU, M=Mem, D=Disk, N=Net)
esxtop -a -b -d 2 -n 100 > /tmp/capture.csv     # Capture batch pentru analiza
# In esxtop: %READY >5% = contention CPU | DAVG >20ms = problema storage
# MCTLSZ >0 = ballooning memorie | SWCUR >0 = swap activ (critic)

esxcli system maintenanceMode get                # Verifica status maintenance mode
```

### Maintenance Mode
```bash
esxcli system maintenanceMode set --enable true   # Intra in maintenance mode
esxcli system maintenanceMode set --enable false  # Iesi din maintenance mode
```

### Logs
```bash
tail -f /var/log/vmkernel.log      # Evenimente storage, paths, APD/PDL, drivere
tail -f /var/log/hostd.log         # Agent management, operatiuni VM
tail -f /var/log/syslog.log        # Initializare sistem, DCUI
tail -f /var/log/vmkwarning.log    # Avertismente si alerte
cat /var/run/log/vmksummary.log    # Istoric boot/reboot
cat /var/log/esxcli.log            # Comenzi esxcli esuate
```

### Servicii
```bash
/etc/init.d/hostd restart          # Restart agent hostd (daca host nu raspunde in vCenter)
/etc/init.d/vpxa restart           # Restart agent vCenter (vpxa)
chkconfig --list                   # Lista servicii si starea lor la boot
```

## Fisiere importante

| Fisier / Cale | Rol |
|---|---|
| `/etc/vmware/esx.conf` | Baza de date configuratie host (storage, network, hardware). **In-memory la runtime.** |
| `/bootbank/state.tgz` | Arhiva persistenta a /etc/ (extrasa in RAM la boot). Actualizata orar de auto-backup.sh |
| `/bootbank/boot.cfg` | Configuratie bootloader (module, optiuni kernel) |
| `/etc/vmware/hostd/config.xml` | Configuratie serviciu hostd |
| `/etc/vmware/hostd/vmInventory.xml` | Inventar VM-uri inregistrate |
| `/etc/vmware/hostd/vmAutoStart.xml` | Ordinea de autostart VM-uri |
| `/etc/vmware/ssl/rui.crt` | Certificat SSL host |
| `/etc/vmware/ssl/rui.key` | Cheie privata SSL host |
| `/etc/vmware/passthru.map` | Mapari PCI passthrough |
| `/vmfs/volumes/<ds>/<vm>/<vm>.vmx` | Configuratie VM (per VM) |
| `/vmfs/volumes/<ds>/<vm>/<vm>.vmdk` | Descriptor disk virtual |
| `/vmfs/volumes/<ds>/<vm>/<vm>-flat.vmdk` | Date disk virtual (raw, poate fi zeci de GB) |
| `/vmfs/volumes/<ds>/<vm>/<vm>.nvram` | Setari BIOS/EFI ale VM |
| `/var/log/vmkernel.log` | Log principal VMkernel |
| `/var/log/hostd.log` | Log management agent |

### Backup configuratie host
```bash
/sbin/auto-backup.sh               # Salveaza /etc/ in /bootbank/state.tgz
# Copiere backup extern:
scp root@<esxi-ip>:/bootbank/state.tgz /backup/esxi-config-$(date +%F).tgz
```

## Periculos / Ireversibil

> ⚠️ **TOATE comenzile din aceasta sectiune necesita confirmare explicita din partea lui Mihai inainte de executie.**

### Shutdown / Reboot (fara prompt de confirmare!)
```bash
# PERICULOS - executia este imediata, fara confirmare
esxcli system shutdown reboot -r "motiv"   # Reboot host
esxcli system shutdown poweroff            # Oprire host

# Recomandat: intra intai in maintenance mode
esxcli system maintenanceMode set --enable true
# ...asteapta migrarea VM-urilor...
esxcli system shutdown reboot -r "planned maintenance"
```

### Oprire fortata VM
```bash
# PERICULOS - echivalent cu scoaterea din priza, poate corupe date in VM
esxcli vm process kill --type hard