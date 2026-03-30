# linux-generic
version: any
os: linux
loaded_when: orice masina Linux necunoscuta

## Detectie
```bash
uname -a
cat /etc/os-release
hostnamectl
```

## Servicii
```bash
systemctl status <service>
systemctl list-units --failed
journalctl -u <service> -n 50 --no-pager
```

## Resurse
```bash
df -h
free -h
top -b -n1 | head -20
ps aux --sort=-%cpu | head -15
```

## Retea
```bash
ip a
ip r
ss -tlnp
netstat -tlnp
```

## Logs
```bash
journalctl -n 100 --no-pager
tail -f /var/log/syslog
dmesg | tail -20
```

## Fisiere mari
```bash
du -sh /* 2>/dev/null | sort -h | tail -20
find / -size +500M 2>/dev/null
```

## Gotchas
- sudo poate lipsi, verifica cu `which sudo`
- PATH poate fi incomplet in SSH non-interactive
- systemd nu e garantat pe toate distro-urile
