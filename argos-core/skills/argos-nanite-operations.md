# argos-nanite-operations
version: 2.0
os: nixos
loaded_when: nanite, iso, deploy nanite, build nanite, boot agent

## Ce este Nanite
Agent bootabil minimal pe USB/ISO. Boot pe orice masina, detecteaza hardware, conecteaza la ARGOS via Tailscale, asteapta comenzi. Semi-autonom cu playbooks locale.

## Fisiere
- config: /home/darkangel/.argos/argos-nanite/configuration.nix
- daemon: /home/darkangel/.argos/argos-nanite/nanite_daemon.py
- playbooks: /home/darkangel/.argos/argos-nanite/playbooks/
- honeypots: /home/darkangel/.argos/argos-nanite/honeypots/
- watcher: /home/darkangel/.argos/argos-nanite/watcher.sh
- API server: /home/darkangel/.argos/argos-core/api/nanite.py

## Build ISO

### Pre-requisite
Tailscale auth key trebuie sa fie in DB:
```sql
SELECT value FROM settings WHERE key='tailscale_auth_key';
```
Daca e gol, NU construi ISO. Intreaba userul sa seteze cheia.

### Pas 1: Injecteaza tailscale key in config
```bash
TS_KEY=$(docker exec argos-db psql -U claude -d claudedb -t -c "SELECT value FROM settings WHERE key='tailscale_auth_key';")
TS_KEY=$(echo "$TS_KEY" | tr -d ' ')
sed "s|@TAILSCALE_AUTH_KEY@|$TS_KEY|g" /home/darkangel/.argos/argos-nanite/configuration.nix > /tmp/nanite-build.nix
```

### Pas 2: Build ISO pe Beasty (NixOS)
```bash
cd /home/darkangel/.argos/argos-nanite
nix-build '<nixpkgs/nixos>' -A config.system.build.isoImage -I nixos-config=/tmp/nanite-build.nix -o /tmp/nanite-result
```
Dureaza 5-15 minute. ISO rezultat in /tmp/nanite-result/iso/

### Pas 3: Copiaza ISO
```bash
ls -lh /tmp/nanite-result/iso/*.iso
cp /tmp/nanite-result/iso/*.iso /home/darkangel/ISO/
```

### Cleanup dupa build
```bash
rm -f /tmp/nanite-build.nix
```
NU lasa fisierul cu tailscale key pe disk.

## Deploy pe Proxmox (Zeus)

### Upload ISO pe Zeus
```bash
scp /home/darkangel/ISO/argos-nanite-*.iso root@11.11.11.11:/var/lib/vz/template/iso/
```

### Creaza VM pe Zeus
```bash
ssh root@11.11.11.11 "qm create VMID --name nanite-test --memory 2048 --cores 2 --net0 virtio,bridge=vmbr0 --cdrom local:iso/ISONAME --boot order=ide2 --ostype l26"
ssh root@11.11.11.11 "qm start VMID"
```
VMID: urmatorul ID liber (verifica cu `qm list`).
ISONAME: numele exact al fisierului ISO uploadat.

### Verifica deploy
Dupa boot (30-60s), nanite apare automat in:
- API: curl http://11.11.11.111:666/api/nanite/nodes
- Fleet UI: nodul apare ca "announced"
- DB: SELECT * FROM nanite_nodes ORDER BY last_seen DESC LIMIT 1;

## Deploy pe USB fizic
```bash
sudo dd if=/home/darkangel/ISO/argos-nanite-*.iso of=/dev/sdX bs=4M status=progress
sync
```
ATENTIE: /dev/sdX = device-ul USB. VERIFICA cu `lsblk` inainte. Comanda DISTRUCTIVA.

## Playbooks disponibile
- boot/00-hardware-detect.sh - detectie hardware la boot
- boot/01-network-passive.sh - scan retea pasiv (zero trafic)
- boot/02-masquerade.sh - masca ca Debian 12 (hostname, MAC, fingerprint)
- boot/03-announce-tailscale.sh - announce la ARGOS prin Tailscale
- roles/pentester/full-scan.sh TARGET - scan complet retea + vulnerabilitati
- self/seppuku.sh - wipe USB + RAM + shutdown (IREVERSIBIL)
- self/scramble-light.sh - wipe doar date colectate
- self/panic.sh - seppuku IMEDIAT fara confirmare

## Trimitere comanda la nanite
```bash
curl -X POST http://11.11.11.111:666/api/nanite/nodes/NODE_ID/cmd \
  -H "Content-Type: application/json" \
  -d '{"command":"bash /etc/nanite/playbooks/roles/pentester/full-scan.sh 192.168.1.0/24","timeout":300}'
```

## Periculos / Ireversibil
- `self/seppuku.sh` - distruge complet nanite-ul si USB-ul. INTOTDEAUNA confirmare explicita Mihai.
- `self/panic.sh` - la fel dar FARA confirmare. Doar in situatii de compromis.
- `dd if= of=/dev/sdX` - scriere USB. Verifica device-ul OBLIGATORIU.
- `qm destroy` - sterge VM. Confirmare obligatorie.

## API Endpoints relevante
- GET /api/nanite/nodes - lista nanite active
- GET /api/nanite/nodes/{node_id} - detalii nod
- POST /api/nanite/announce - nanite se anunta
- POST /api/nanite/heartbeat - nanite raporteaza status
- POST /api/nanite/nodes/{node_id}/cmd - trimite comanda
- GET /api/nanite/commands/{node_id} - nanite cere comenzi pending
- DELETE /api/nanite/nodes/{node_id} - decommission

## Gotchas
- Build ISO dureaza 5-15 min, nu intrerupe
- Tailscale auth key TREBUIE sa fie reusable si pre-authorized
- Dupa build, sterge /tmp/nanite-build.nix (contine cheia)
- Nanite hostname e mascat (srv01), nu "nanite" - asta e intentional
- MAC se schimba la fiecare boot - normal, nu e bug
- Heartbeat la 5 minute, nu la 2s ca heartbeat.py normal
- nanite_daemon.py e zero dependinte externe (doar Python stdlib)
