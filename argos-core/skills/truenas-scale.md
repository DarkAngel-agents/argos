# truenas-scale
version: 24.x (Dragonfish/Electric Eel)
os: truenas-scale
loaded_when: TrueNAS SCALE detectat, NAS storage

## Detectie
```bash
cat /etc/version
cli system info
midclt call system.info
```

## CLI principal (midclt)
```bash
midclt call system.info
midclt call pool.query
midclt call dataset.query
midclt call disk.query
midclt call service.query
```

## Pool & Storage
```bash
zpool list
zpool status
zpool status -v            # verbose, erori
zfs list
zfs list -t snapshot
zfs get all <pool/dataset>
```

## Datasets
```bash
zfs create pool/dataset
zfs set compression=lz4 pool/dataset
zfs set quota=100G pool/dataset
zfs snapshot pool/dataset@snap1
zfs rollback pool/dataset@snap1    # DISTRUCTIV
zfs destroy pool/dataset@snap1
```

## Shares
```bash
midclt call sharing.smb.query      # SMB shares
midclt call sharing.nfs.query      # NFS shares
midclt call sharing.iscsi.target.query
```

## Services
```bash
midclt call service.query
midclt call service.start '["cifs"]'    # SMB
midclt call service.start '["nfs"]'
midclt call service.start '["ssh"]'
systemctl status middlewared
```

## Apps (Kubernetes / Docker)
```bash
midclt call chart.release.query
k3s kubectl get pods -A
k3s kubectl get nodes
```

## Replicare & Snapshots
```bash
midclt call replication.query
midclt call pool.snapshottask.query
```

## Alerts
```bash
midclt call alert.list
midclt call alert.dismiss '["<uuid>"]'
```

## Users & Groups
```bash
midclt call user.query
midclt call group.query
```

## Network
```bash
midclt call interface.query
midclt call network.configuration.config
midclt call route.system_routes
```

## Update
```bash
midclt call update.check_available
midclt call update.update          # CONFIRMARE NECESARA - reboot
```

## Debug & Logs
```bash
journalctl -u middlewared -n 100 --no-pager
tail -f /var/log/middlewared.log
midclt call system.debug           # genereaza debug bundle
```

## Backup config
```bash
# Din UI: System -> General -> Save Config
midclt call config.save            # salveaza in /data/freenas-v1.db
```

## Gotchas
- TrueNAS SCALE = Debian + ZFS + Kubernetes (nu FreeBSD ca TrueNAS CORE)
- midclt = middleware client, interfata principala CLI
- NU modifica fisiere de sistem direct - totul prin midclt sau UI
- Apps ruleaza pe k3s (Kubernetes lightweight)
- ZFS ARC = RAM cache - normal sa consume mult RAM
- scrub periodic recomandat: luna pe toate pool-urile
- zfs destroy = IREVERSIBIL fara snapshot anterior
- Electric Eel (24.10+): Apps migrate de la k3s la Docker Compose
