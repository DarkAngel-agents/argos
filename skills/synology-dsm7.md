# synology-dsm7
version: DSM 7.x
os: synology
loaded_when: Synology NAS detectat, DSM 7

## Detectie
```bash
cat /etc.defaults/VERSION
uname -a
synopkg list | head -10
```

## Info sistem
```bash
cat /etc.defaults/VERSION
uname -a
uptime
df -h
free -h
```

## Storage & RAID
```bash
cat /proc/mdstat                    # status RAID
mdadm --detail /dev/md0
mdadm --detail /dev/md1
synoraid --enum
synodiskport -d all
hdparm -I /dev/sda | grep -E "Model|Serial|capacity"
```

## Volume & Shares
```bash
df -h | grep volume
ls /volume1/
synoshare --enum                    # lista share-uri
synoshare --get <share>
```

## Servicii
```bash
synoservice --list
synoservice --status <service>
synoservice --restart <service>
# servicii comune: nginx, smbd, nfsd, sshd, synomkthumbd
```

## Pachete (Package Center)
```bash
synopkg list
synopkg status <package>
synopkg start <package>
synopkg stop <package>
synopkg install <package.spk>      # instalare manuala
```

## Users & Groups
```bash
synouser --enum local
synogroup --enum local
synouser --add <user> <pass> "" 0 "" 0 0
```

## Network
```bash
ip a
ip r
cat /etc/resolv.conf
synonet --list-iface
```

## Logs
```bash
tail -f /var/log/messages
cat /var/log/synopkg.log
dmesg | tail -30
synologging --level err            # system logs
```

## Backup & Snapshot
```bash
# Snapshot (Btrfs volumes)
btrfs subvolume list /volume1
btrfs subvolume snapshot /volume1/<share> /volume1/.snapshot/<name>
# Hyper Backup: /var/packages/HyperBackup/
```

## Docker (Container Manager)
```bash
docker ps
docker images
docker logs <container>
docker exec -it <container> bash
# config: /volume1/docker/
```

## SSH hardening
```bash
# /etc/ssh/sshd_config
# Port 22 -> custom
# PermitRootLogin no
synoservice --restart sshd
```

## Permissions
```bash
synoacltool -get /volume1/<share>
chmod -R 770 /volume1/<share>
chown -R <user>:<group> /volume1/<share>
```

## Update DSM
```bash
# Din UI: Control Panel -> Update & Restore
# CLI:
synoupgrade --check
# Update manual: upload .pat file din UI
```

## Gotchas
- DSM 7 = Linux custom (kernel Synology) + busybox + overlay
- NU apt/yum - foloseste Entware pentru pachete extra (opkg)
- Root SSH disponibil doar daca activat explicit din Control Panel
- Btrfs = snapshot native, EXT4 = fara snapshot
- RAID Synology Hybrid (SHR) diferit de mdadm standard
- /volume1 = datastore principal, /volumeUSB = USB attached
- Container Manager = Docker oficial din DSM 7.2+
- synoservice restart smbd = restart SMB fara reboot
- Dupa modificari /etc/samba/smb.conf: synoservice restart smbd
