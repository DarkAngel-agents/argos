# cisco-ios
version: IOS / IOS-XE / IOS-XR
os: cisco-ios
loaded_when: Cisco switch/router detectat, IOS CLI

## Detectie
```
show version
show inventory
show ip interface brief
```

## Moduri CLI
```
>          User EXEC mode
#          Privileged EXEC mode (enable)
(config)#  Global config mode (configure terminal)
(config-if)# Interface config mode
```

## Info sistem
```
show version
show inventory
show running-config
show startup-config
show clock
show users
```

## Interfaces
```
show ip interface brief
show interfaces
show interfaces status          # pe switch-uri
show interfaces trunk
show interfaces <gi0/0> counters
```

## Routing
```
show ip route
show ip route summary
show ip protocols
show ip ospf neighbor
show ip bgp summary
show ip eigrp neighbors
```

## VLAN (switch)
```
show vlan brief
show vlan id <id>
show interfaces trunk
show spanning-tree vlan <id>
show mac address-table
show mac address-table vlan <id>
```

## Config VLAN
```
configure terminal
  vlan <id>
    name <name>
  interface <gi1/0/1>
    switchport mode access
    switchport access vlan <id>
  interface <gi1/0/24>
    switchport mode trunk
    switchport trunk allowed vlan <id1>,<id2>
```

## IP pe interface
```
configure terminal
  interface <gi0/0>
    ip address <ip> <mask>
    no shutdown
```

## SSH & Management
```
show ip ssh
crypto key generate rsa modulus 2048
ip ssh version 2
line vty 0 4
  transport input ssh
  login local
```

## ACL
```
show ip access-lists
show access-lists
ip access-list extended BLOCK-X
  deny ip <src> <wildcard> any
  permit ip any any
interface <gi0/0>
  ip access-group BLOCK-X in
```

## Logs & Debug
```
show logging
show logging | include error
debug ip ospf events          # ATENTIE: flood pe consola
no debug all                  # opreste toate debug-urile
terminal monitor              # vede log-uri in SSH session
```

## Save config
```
copy running-config startup-config
write memory                  # echivalent
```

## Reload & Recovery
```
reload                        # REBOOT - confirmare necesara
reload in 5                   # reboot in 5 minute (safeguard)
reload cancel                 # anuleaza reload programat
```

## CDP / LLDP Neighbors
```
show cdp neighbors
show cdp neighbors detail
show lldp neighbors
show lldp neighbors detail
```

## Spanning Tree
```
show spanning-tree
show spanning-tree vlan <id>
show spanning-tree summary
```

## Gotchas
- NICIODATA debug fara 'terminal monitor' off dupa - poate bloca sesiunea
- 'reload in 10' inainte de modificari majore - safeguard rollback
- copy run start OBLIGATORIU dupa modificari - RAM vs NVRAM
- IOS-XE vs IOS-XR: sintaxa difera pentru BGP/OSPF avansat
- enable secret vs enable password: foloseste secret (MD5)
- Wildcard mask = inversa subnet mask (0.0.0.255 pt /24)
- no debug all daca terminalul devine inutilizabil
