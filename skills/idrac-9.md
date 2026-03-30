# idrac-9
version: 9.x
os: idrac
loaded_when: iDRAC detectat, server Dell PowerEdge

## Detectie
```bash
racadm getsysinfo
racadm getversion
curl -sk https://<idrac-ip>/redfish/v1/Systems/System.Embedded.1
```

## Info sistem
```bash
racadm getsysinfo
racadm getversion -m idrac
racadm getsensorinfo
racadm getled
```

## Power management
```bash
racadm serveraction powerdown
racadm serveraction powerup
racadm serveraction powercycle
racadm serveraction graceshutdown
racadm serveraction hardreset
```

## iDRAC remote (din exterior)
```bash
racadm -r <idrac-ip> -u root -p <pass> getsysinfo
racadm -r <idrac-ip> -u root -p <pass> serveraction powerup
```

## Redfish API
```bash
# Info sistem
curl -sk -u root:<pass> https://<idrac-ip>/redfish/v1/Systems/System.Embedded.1 | python3 -m json.tool

# Power state
curl -sk -u root:<pass> https://<idrac-ip>/redfish/v1/Systems/System.Embedded.1 | python3 -m json.tool | grep PowerState

# Power on
curl -sk -u root:<pass> -X POST https://<idrac-ip>/redfish/v1/Systems/System.Embedded.1/Actions/ComputerSystem.Reset \
  -H 'Content-Type: application/json' -d '{"ResetType":"On"}'

# Graceful shutdown
curl -sk -u root:<pass> -X POST https://<idrac-ip>/redfish/v1/Systems/System.Embedded.1/Actions/ComputerSystem.Reset \
  -H 'Content-Type: application/json' -d '{"ResetType":"GracefulShutdown"}'
```

## Virtual Console / KVM
```bash
# Lanseaza Virtual Console (Java/HTML5)
# https://<idrac-ip>/console
# racadm getkvminfo
racadm set iDRAC.VirtualConsole.PluginType HTML5
```

## Logs
```bash
racadm getsel               # System Event Log
racadm getlclog             # Lifecycle Controller log
racadm clrsel               # Sterge SEL - CONFIRMARE NECESARA
```

## Network iDRAC
```bash
racadm getniccfg -n idrac
racadm setniccfg -n idrac -s        # DHCP
racadm setniccfg -n idrac <ip> <mask> <gw>  # Static
```

## Firmware update
```bash
racadm update -f <firmware.exe> -d /tmp -a TRUE
```

## BIOS settings
```bash
racadm get BIOS.SysInformation
racadm set BIOS.ProcSettings.ProcVirtualization Enabled
racadm jobqueue create BIOS.Setup.1-1
```

## Gotchas
- racadm local = fara -r flag, direct pe server
- racadm remote = cu -r <ip> -u <user> -p <pass>
- Redfish e recomandat fata de WSMAN pentru iDRAC9
- Default creds: root / calvin (schimba imediat)
- Virtual Console necesita HTML5 pe browsere moderne (nu mai exista Java applet)
- SEL plin poate bloca logarea de noi evenimente
- jobqueue create obligatoriu dupa modificari BIOS
