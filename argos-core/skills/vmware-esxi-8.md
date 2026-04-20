# vmware-esxi-8
version: 8.x
os: esxi
loaded_when: VMware ESXi detectat, vSphere hypervisor

## Detectie
```bash
vmware -v
esxcli system version get
vim-cmd vmsvc/getallvms
```

## VM management
```bash
vim-cmd vmsvc/getallvms                    # lista toate VM-urile
vim-cmd vmsvc/power.getstate <vmid>
vim-cmd vmsvc/power.on <vmid>
vim-cmd vmsvc/power.off <vmid>             # hard off
vim-cmd vmsvc/power.shutdown <vmid>        # graceful
vim-cmd vmsvc/power.reboot <vmid>
vim-cmd vmsvc/snapshot.get <vmid>
vim-cmd vmsvc/snapshot.create <vmid> <name> <desc> 0 0
vim-cmd vmsvc/snapshot.removeall <vmid>    # DISTRUCTIV
```

## esxcli - comenzi principale
```bash
esxcli system hostname get
esxcli system uptime get
esxcli hardware cpu list
esxcli hardware memory get
esxcli storage filesystem list
esxcli storage core device list
esxcli network nic list
esxcli network ip interface list
esxcli network ip address list
```

## Networking
```bash
esxcli network vswitch standard list
esxcli network vswitch standard portgroup list
esxcli network ip interface list
esxcfg-vmknic -l
esxcfg-vswitch -l
```

## Storage (datastores)
```bash
esxcli storage filesystem list
ls /vmfs/volumes/
df -h /vmfs/volumes/
esxcli storage core device list
esxcli storage core path list
```

## Logs
```bash
tail -f /var/log/vmkernel.log
tail -f /var/log/hostd.log
tail -f /var/log/vpxa.log          # vCenter agent
cat /var/log/syslog.log
```

## Servicii
```bash
esxcli system maintenanceMode get
esxcli system maintenanceMode set --enable true
chkconfig --list | grep on         # servicii active
/etc/init.d/hostd restart
/etc/init.d/vpxa restart
```

## Performance
```bash
esxtop                              # interactiv (ca top)
esxtop -b -n 1 > /tmp/esxtop.csv   # batch mode
vscsiStats -s                      # SCSI stats
```

## Certificates & Licenses
```bash
vim-cmd vimsvc/license --show
esxcli software profile get        # versiune instalata
```

## Update (ESXi offline bundle)
```bash
esxcli software profile update -p <profile> -d <bundle.zip>
esxcli software vib install -d <bundle.zip>
esxcli software vib list
```

## Backup VM (fara vCenter)
```bash
vim-cmd vmsvc/power.shutdown <vmid>
cp -r /vmfs/volumes/<datastore>/<vmdir>/ /vmfs/volumes/<backup-ds>/
```

## SSH & Management
```bash
# Activare SSH din console:
vim-cmd hostsvc/enable_ssh
vim-cmd hostsvc/start_ssh
# sau din UI: Host -> Actions -> Services -> SSH
```

## Gotchas
- ESXi nu are package manager standard - totul prin esxcli sau VIB
- Maintenance mode obligatoriu inainte de update/reboot in cluster vSphere
- snapshot.removeall = IREVERSIBIL, foloseste create_job
- /scratch si /tmp = RAM disk, nu persista dupa reboot
- hostd crash = UI mort, dar VM-urile ruleaza in continuare
- vCenter Agent (vpxa) separat de hostd - poate crasha independent
- ESXi 8 free license = fara vMotion/HA/DRS (standalone only)
- VMFS6 suporta 512e (4K native) disks, VMFS5 nu
