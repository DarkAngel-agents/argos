# mikrotik-routeros
version: 6.x / 7.x
os: routeros
loaded_when: MikroTik RouterOS detectat, switch/router MikroTik

## Detectie
```bash
/system resource print
/system identity print
/system routerboard print
```

## Info sistem
```bash
/system resource print
/system identity print
/system clock print
/system routerboard print
/system package print
```

## IP & Routing
```bash
/ip address print
/ip route print
/ip dns print
/ip arp print
/ip neighbor print         # LLDP/CDP neighbors
```

## Interfaces
```bash
/interface print
/interface ethernet print
/interface bridge print
/interface vlan print
/interface wireless print  # daca are WiFi
```

## VLAN (switch chip / bridge)
```bash
/interface bridge vlan print
/interface bridge port print
/interface ethernet switch vlan print   # ROS6 switch chip
/interface vlan print                   # VLAN interfaces
```

## Firewall
```bash
/ip firewall filter print
/ip firewall nat print
/ip firewall mangle print
/ip firewall address-list print
```

## DHCP
```bash
/ip dhcp-server print
/ip dhcp-server lease print
/ip dhcp-client print
```

## Wireless
```bash
/interface wireless print
/interface wireless registration-table print
/caps-man manager print    # CAPsMAN controller
```

## Users & SSH
```bash
/user print
/ip service print
/ip ssh print
```

## Logs
```bash
/log print
/log print where topics~"error"
/log print where topics~"dhcp"
```

## Backup & Export
```bash
/system backup save name=backup-$(date +%Y%m%d)
/export file=config-export         # text export, human readable
/export compact file=config-compact
```

## Update
```bash
/system package update check-for-updates
/system package update download
/system package update install     # REBOOT automat
```

## Reboot / Shutdown
```bash
/system reboot
/system shutdown
```

## Scripting
```bash
/system script add name=test source={ /log info "hello" }
/system script run test
/system scheduler print
```

## Traffic monitoring
```bash
/interface monitor-traffic ether1 once
/tool bandwidth-test address=<ip> direction=both
/ip traffic-flow print
```

## Gotchas
- ROS6 vs ROS7: sintaxa bridge VLAN difera substantial
- ROS7: /interface bridge vlan este metoda principala
- ROS6: switch chip e separat de bridge
- Winbox = GUI proprietar, alternativa la CLI/SSH
- API port 8728 (plain) / 8729 (SSL)
- Default creds: admin / (fara parola) - schimba imediat
- /export nu salveaza parole - backup binar pentru restore complet
- safe mode: Ctrl+X in terminal - rollback automat daca se pierde conexiunea
