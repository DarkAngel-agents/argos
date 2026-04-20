# debian-12
version: 12 (bookworm) / 13 (trixie)
os: debian
loaded_when: Debian machine detected

## Packages
```bash
apt update && apt upgrade -y
apt install <package>
apt remove <package>
dpkg -l | grep <package>
apt-cache search <keyword>
```

## Services
```bash
systemctl status <service>
systemctl enable --now <service>
systemctl restart <service>
journalctl -u <service> -n 50 --no-pager
```

## Firewall
```bash
ufw status
ufw allow <port>
iptables -L -n
# Add insecure docker registry
echo '{"insecure-registries":["<IP>:5000"]}' > /etc/docker/daemon.json
systemctl restart docker
```

## User management - Debian 13 (Trixie) specifics
```bash
# useradd exists, adduser may not be installed
useradd -m -s /bin/bash <user>
echo '<user>:<password>' | chpasswd
# Add to sudo group - usermod may be missing, use sed on /etc/group directly:
sed -i 's/sudo:x:27:/sudo:x:27:<user>/' /etc/group
# Or install sudo first:
apt install -y sudo
# Then add user:
usermod -aG sudo <user>
# If usermod still not found:
sed -i 's/sudo:x:27:/sudo:x:27:<user>/' /etc/group
```

## SSH
```bash
# Enable root login (Debian 13 disables it by default)
sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
systemctl restart ssh
# Copy SSH key
ssh-copy-id <user>@<host>
scp ~/.ssh/id_ed25519 <user>@<host>:/home/<user>/.ssh/
```

## NFS client
```bash
apt install -y nfs-common
mkdir -p /mount/point
mount <server-IP>:/exported/path /mount/point
# Persistent (fstab):
echo '<server-IP>:/exported/path /mount/point nfs ro,sync,_netdev 0 0' >> /etc/fstab
```

## Docker on Debian
```bash
curl -fsSL https://get.docker.com | sh
# Add user to docker group
usermod -aG docker <user>
# Insecure registry
echo '{"insecure-registries":["<IP>:5000"]}' > /etc/docker/daemon.json
systemctl restart docker
# Join Swarm
docker swarm join --token <token> <manager-IP>:2377
```

## PostgreSQL on Debian
```bash
# Install (Debian 13 has pg17)
apt install -y postgresql-17
systemctl stop postgresql
# Setup as streaming replication standby:
rm -rf /var/lib/postgresql/17/main/*
PGPASSWORD=<password> pg_basebackup -h <primary-IP> -U replicator -D /var/lib/postgresql/17/main -P -Xs -R
chown -R postgres:postgres /var/lib/postgresql/17/main
systemctl start postgresql
# Check replication status (on primary):
docker exec argos-db psql -U claude -d claudedb -c "SELECT client_addr, state FROM pg_stat_replication;"
```

## Gotchas Debian 13 (Trixie)
- Root SSH disabled by default — enable via sshd_config
- sudo not installed by default in minimal install
- usermod may be missing — use sed on /etc/group as fallback
- adduser may not be installed — use useradd
- postgresql-16 not available — use postgresql-17
- rsync not installed by default — apt install rsync
- curl not installed by default — apt install curl

## ARGOS on Hermes (11.11.11.98) — Debian 13
- Swarm worker node
- Docker 29.3.1 installed
- argos-swarm_argos replica running (code via NFS from Beasty)
- NFS mount: 11.11.11.111:/home/darkangel/.argos/argos-core -> /home/darkangel/.argos/argos-core (ro)
- PostgreSQL 17 standby (streaming replication from 11.11.11.111)
- SSH keys: /home/darkangel/.ssh/id_ed25519 (copied from Beasty)
- insecure-registries: ["11.11.11.111:5000"] in /etc/docker/daemon.json
