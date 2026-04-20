# nanite-protocols
version: 1.0
os: nixos
loaded_when: nanite install, nanite deploy, nanite role, nanite protocol, install pe nanite, fa nanite, nixos live

## REGULA FUNDAMENTALA: NixOS live ISO = READ-ONLY
- NU merge: nix-env, apt, yum, pacman, pip install - NIMIC post-boot
- NU merge: systemctl enable/start servicii noi
- NU merge: modificare /etc persistent
- CE MERGE: executie scripturi, scriere in /tmp si /home, download fisiere, python3/bash
- ORICE pachet nou sau configurare persistenta = REBUILD ISO din configuration.nix
- Daca userul cere instalare pachet pe nanite live: raspunde "trebuie rebuild ISO" NU incerca sa instalezi

## BOOT SEQUENCE (automatic, fara interventie)
Ordine stricta:
1. `00-hardware-detect.sh` - CPU, RAM, disks, GPU, NICs din /proc si /sys (zero retea)
2. `01-network-passive.sh` - IP propriu, gateway, DNS, ARP table existenta (zero trafic generat)
3. `02-masquerade.sh` - MAC random, hostname generic, sysctl Debian fingerprint, fake /etc/os-release
4. `03-announce-tailscale.sh` - connect Tailscale, POST /api/nanite/announce la ARGOS
5. `nanite_daemon.py` - heartbeat la 5 min, command poll la 5s (serviciu persistent)
6. `honeypot_ssh.py` - port 22 fake Debian SSH (serviciu persistent)
7. `watcher.sh` - iptables scan detection + ARP pasiv (serviciu persistent)

Dupa boot, nanite e GATA si asteapta comenzi de la ARGOS.
Nu face nimic activ pe retea. Nu se anunta pe LAN. Doar Tailscale outbound.

## COMUNICARE CU NANITE
MEREU prin API, NICIODATA SSH direct (chiar daca e posibil):
```
ARGOS -> POST /api/nanite/nodes/{node_id}/cmd {"command":"...", "timeout":120}
nanite_daemon polls -> GET /api/nanite/commands/{node_id}
nanite executa local -> POST /api/nanite/command-result {returncode, stdout, stderr}
```
Node ID: se obtine automat din GET /api/nanite/nodes (nu hardcodat de user)

## ROLURI SI PROTOCOALE

### SCOUT (default la boot)
Ce face: boot, detect, announce, asteapta
Comenzi disponibile: orice din ISO (nmap, lspci, lsblk, ip, curl, python3, etc.)
Exemplu: "scaneaza reteaua 192.168.1.0/24"
Protocol: trimite comanda "nmap -sn 192.168.1.0/24" prin API
Rezultat: lista hosturi active vine inapoi prin command-result

### PENTESTER
Ce face: scanare securitate completa
Toate toolurile sunt DEJA in ISO: nmap, tcpdump, wireshark-cli, arp-scan, mtr
NU necesita rebuild, NU necesita instalare
Protocol:
1. Trimite: "bash /etc/nanite/playbooks/roles/pentester/full-scan.sh 192.168.1.0/24"
2. Nanite executa local (nmap discovery + port scan + vuln check)
3. Rezultat: JSON summary + fisiere detaliate in /tmp/nanite-results/
4. Dupa raport: scramble-light.sh (sterge datele) sau seppuku.sh (distruge tot)

### DIAGNOSTIC
Ce face: verificare sanatate retea
Tooluri in ISO: mtr, nmap, iftop, nethogs, ethtool, arp-scan
Protocol:
1. DNS check: "dig @GATEWAY google.com && dig @8.8.8.8 google.com"
2. Latency map: "mtr -rwn -c 10 8.8.8.8"
3. ARP scan: "arp-scan --localnet"
4. Port conflicts: "nmap -sn SUBNET"
Rezultat: raport text/JSON trimis prin command-result

### SENTINEL
Ce face: monitorizeaza reteaua discret pe termen lung
Protocol:
1. Watcher.sh ruleaza continuu (iptables + ARP)
2. Honeypots active (SSH port 22 + SMB port 445)
3. Heartbeat la 5 min - "inca sunt aici"
4. La detectie anomalie: alert ARGOS cu detalii
5. Reactie configurabila: QUIET / DEFENSIVE (schimba MAC+IP) / PANIC (seppuku)
Nu necesita comenzi suplimentare - ruleaza autonom dupa activare

### ARGOS NODE - CALE DIRECTA (masina modesta)
Cand: userul spune explicit "instaleaza ca ARGOS node" SAU hardware modest (desktop/laptop/mini PC)
Detectie hardware modest: < 16 CPU cores, < 32GB RAM, 1-2 diskuri
Protocol:
1. Nanite pregateste totul:
   - Verifica diskuri disponibile (lsblk)
   - Verifica conexiune Tailscale activa
   - Verifica acces la ARGOS API
   - Genereaza configuration.nix clona ARGOS worker
2. INTREABA USERUL: "Am pregatit instalare NixOS ARGOS node pe /dev/sda (250GB). Toate datele de pe disk vor fi sterse. Continui? (da/nu)"
3. Dupa confirmare:
   - Partitionare disk (GPT: EFI 512M + root ext4 rest)
   - nixos-install cu configuratie ARGOS worker
   - Setup Docker + join Swarm via Tailscale
   - Setup heartbeat.py ca systemd service
   - Reboot in NixOS instalat
4. Dupa reboot:
   - Noul nod se anunta la ARGOS (heartbeat)
   - Join Docker Swarm ca worker
   - Apare in Fleet ca "online"
5. Nanite ISO se autodistruge (seppuku pe USB-ul de boot)

### ARGOS NODE - CALE SERVER (hardware potent)
Cand: nanite detecteaza hardware server (Xeon, >= 32GB RAM, >= 4 diskuri, IPMI/iDRAC)
Detectie server: Xeon/EPYC CPU, ECC RAM, >= 32GB, RAID controller, multi-disk
>>> TODO: NECESITA TESTE - NU IMPLEMENTAT INCA <<<
Protocol planificat:
1. Nanite raporteaza: "Hardware server detectat: Xeon E5-2698, 64GB ECC, 8x 2TB SAS"
2. INTREABA: "Hardware potent. Recomand instalare Proxmox VE cu VM ARGOS. Continui?"
3. Dupa confirmare:
   - Instaleaza Proxmox VE pe bare metal
   - Creeaza VM cu config ARGOS (CPU/RAM/disk proportional)
   - Instaleaza NixOS ARGOS node in VM
   - Configureaza networking (bridge, Tailscale)
   - Noul Proxmox + ARGOS VM apar in Fleet
4. Nanite seppuku dupa install complet
>>> SFARSIT TODO <<<

### CUSTOM INSTALL (workstation/server specific)
Cand: userul specifica explicit "instaleaza NixOS desktop" sau "instaleaza Debian server cu X Y Z"
Protocol:
1. Nanite pregateste partitionare + configuratie
2. INTREABA: confirmare cu detalii (disk, config, pachete)
3. Instaleaza conform specificatiilor
4. Nanite seppuku dupa install
Nota: configuratia vine de la ARGOS, nu e predefinita in nanite

## SELF-DESTRUCT

### seppuku (complet, ireversibil)
Cand: misiune terminata, compromis detectat, ordin explicit
1. Trimite "goodbye" la ARGOS cu ultimele date
2. Asteapta confirmare ARGOS ca datele sunt salvate
3. Kill toate procesele nanite
4. Wipe USB/stick boot media (dd urandom 3 passes)
5. Clear RAM (drop_caches + fill memory)
6. Clear logs (journalctl vacuum + rm /var/log)
7. Poweroff

### panic (emergency, fara confirmare)
Cand: PANIC level pe honeypot, compromis cert
1. Kill -9 totul
2. Wipe USB + RAM in paralel
3. Poweroff imediat (sysrq)
Zero comunicare cu ARGOS - nu mai conteaza, pleaca acum

### scramble-light (sterge date, pastram nanite)
Cand: dupa scan/pentest, curatare periodica
1. Sterge /tmp/nanite-*.json, /tmp/nanite-results/
2. Clear bash history
3. Clear journals
4. Drop page cache
Nanite ramane operational

## PACHETE IN ISO (disponibile post-boot fara instalare)
Network: nmap, tcpdump, wireshark-cli, iftop, nethogs, mtr, arp-scan, ethtool, curl, wget
Storage: parted, gptfdisk, e2fsprogs, dosfstools, hdparm, smartmontools
System: vim, htop, mc, git, rsync, python3, jq, lsof, strace, file
Hardware: pciutils, usbutils, lshw, inxi, bc
Tailscale: tailscale (mesh VPN)

## CE NU E IN ISO (necesita rebuild)
- Samba, nginx, Apache, MySQL, PostgreSQL
- Docker, containerd
- GUI (Xorg, Wayland, GNOME, KDE)
- Compilatoare (gcc, go, rust)
- Orice altceva nelistat in sectiunea de mai sus

## GOTCHAS
- Node ID se schimba la fiecare rebuild ISO (bazat pe machine-id generat la boot)
- hostname mascat (srv01 nu nanite) - intentional, nu bug
- MAC random la fiecare boot - intentional, nu bug
- nanite_daemon.py trebuie sa fie in ISO (/etc/nanite/) nu copiat manual
- Tailscale auth key trebuie baked in ISO la build time
- Port 8000 nu exista - ARGOS API e pe 666
- writeScriptBin genereaza shebang #!/usr/bin/env bash - nu merge pe NixOS, foloseste ExecStart cu ${pkgs.bash}/bin/bash
