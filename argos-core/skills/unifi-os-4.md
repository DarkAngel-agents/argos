# unifi-os-4
version: 4.x
os: unifi-os
loaded_when: UDM Pro / UniFi OS detectat

## API - functioneaza (testat)
```
GET /proxy/network/api/s/default/stat/sta          # clienti conectati
GET /proxy/network/api/s/default/stat/device       # device-uri full
GET /proxy/network/api/s/default/stat/device-basic # device-uri summary
GET /proxy/network/api/s/default/stat/event        # events
```
Header: X-API-KEY: <key>

## API - SKIP (nu functioneaza pe UDM Pro)
```
POST /proxy/network/api/s/default/cmd/devmgr restart → HTTP 500
POST /api/system/reboot → Unauthorized
```
Restart UDM Pro = DOAR manual fizic sau din UI.

## Exemple curl
```bash
curl -sk -H "X-API-KEY: <key>" https://10.0.10.1/proxy/network/api/s/default/stat/sta | python3 -m json.tool | head -50
curl -sk -H "X-API-KEY: <key>" https://10.0.10.1/proxy/network/api/s/default/stat/device-basic | python3 -m json.tool
```

## Diagnostice retea
- Rogue DHCP: cauta device cu multe IP-uri in stat/sta
- IP conflict: compara lease-uri cu rezervari statice
- Loop: verifica STP status pe switch-uri
- LXC rogue DHCP: pct list pe Proxmox, verifica LXC cu dnsmasq

## Gotchas
- API key in header X-API-KEY, nu Bearer
- HTTPS cu cert self-signed: curl -sk
- CITESTE inainte de orice actiune, VERIFICA dupa, rollback 30s

## SSH UDM Pro (ultima varianta, doar cand API nu merge)
```bash
ssh root@10.0.10.1
# parola din system_credentials DB label='UDM Pro SSH'
```

### Comenzi SSH utile pe UDM Pro
```bash
# Firewall rules iptables
iptables -L -n --line-numbers
iptables -I FORWARD -p tcp --dport 41337 -j ACCEPT

# Port forwarding status
iptables -t nat -L -n

# Servicii
systemctl list-units --state=running

# Network interfaces
ip addr show
ip route show

# UniFi logs
tail -f /var/log/messages
journalctl -u unifi -n 50
```

### Regula firewall manuala via SSH
```bash
# Allow port 41337 WAN_IN (persistent via iptables-save)
iptables -I FORWARD 1 -i eth8 -p tcp --dport 41337 -j ACCEPT
iptables-save > /etc/iptables/rules.v4
```

## Gotchas SSH UDM
- Foloseste SSH DOAR daca API esueaza complet
- iptables rules nu persista dupa reboot fara iptables-save
- Regulile sistem (3001, 3002) nu sunt vizibile via API — sunt hardcodate
- Port forwarding genereaza automat reguli iptables interne pe versiuni recente
- SSH root permis, port 22
