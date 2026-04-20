# proxmox-8
version: 8.x
os: proxmox
loaded_when: host Proxmox VE detectat

## Detectie
```bash
pveversion
pvesh get /nodes
qm list
```

## VM management
```bash
qm list
qm status <vmid>
qm start <vmid>
qm stop <vmid>
qm shutdown <vmid>
qm destroy <vmid>          # DISTRUCTIV - create_job obligatoriu
qm config <vmid>
```

## VM creare
```bash
qm create <vmid> --name <name> --memory 2048 --cores 2 --net0 virtio,bridge=vmbr0
qm importdisk <vmid> <disk.img> local-lvm
qm set <vmid> --scsi0 local-lvm:vm-<vmid>-disk-0
qm set <vmid> --ide2 local:iso/<iso.iso>,media=cdrom
qm set <vmid> --boot order=scsi0
```

## Storage
```bash
pvesm status
pvesm list local-lvm
qm disk list <vmid>
```

## Backup
```bash
vzdump <vmid> --storage local --mode snapshot
pvesm list local | grep backup
```

## LXC
```bash
pct list
pct start <ctid>
pct stop <ctid>
pct enter <ctid>
```

## Network
```bash
cat /etc/network/interfaces
brctl show
```

## Gotchas
- qm destroy = IREVERSIBIL, foloseste create_job cu risk_level=critical
- ISO path: /var/lib/vz/template/iso/
- VM IDs: conventie Zeus 100-199, Ares 200-299
- snapshot inainte de orice operatie majora


## Nanite Deploy on Zeus
```bash
# Upload ISO
scp ~/ISO/argos-nanite-*.iso root@11.11.11.11:/var/lib/vz/template/iso/

# Create VM with custom specs
ssh root@11.11.11.11 "qm create VMID --name nanite-VMID --memory RAM_MB --cores CORES --net0 virtio,bridge=vmbr0 --scsihw virtio-scsi-single --scsi0 local-zfs:DISK_GB --cdrom local:iso/ISO_NAME --boot order=ide2 --ostype l26"

# Start
ssh root@11.11.11.11 "qm start VMID"

# Verify
ssh root@11.11.11.11 "qm status VMID"

# Get IP (after boot)
ssh root@11.11.11.11 "arp-scan --localnet 2>/dev/null | grep -i nanite || qm guest exec VMID ip a"
```

## Zeus specifics
- Storage: local-zfs (default for VM disks)
- Network: vmbr0 (bridged, DHCP available)
- VM ID range: 100-199
- ISO path: /var/lib/vz/template/iso/
- SSH: root@11.11.11.11
