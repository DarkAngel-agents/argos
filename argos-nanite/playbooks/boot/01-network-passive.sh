#!/bin/bash
# NANITE BOOT: Passive network detection - ZERO trafic generat
set -e
LOG="[NANITE:NET]"
REPORT="/tmp/nanite-net.json"

echo "$LOG Passive network detection..."

# Propria configuratie (nu genereaza trafic)
MY_IP=$(ip -4 addr show scope global | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1 || echo "")
MY_GW=$(ip route | grep default | awk '{print $3}' | head -1 || echo "")
MY_DNS=$(grep nameserver /etc/resolv.conf 2>/dev/null | head -1 | awk '{print $2}' || echo "")
MY_MAC=$(cat /sys/class/net/$(ip route | grep default | awk '{print $5}' | head -1)/address 2>/dev/null || echo "")
MY_SUBNET=$(ip -4 addr show scope global | grep -oP '\d+\.\d+\.\d+\.\d+/\d+' | head -1 || echo "")

# ARP table snapshot (ce stie kernelul fara sa intrebam)
ARP_NEIGHBORS="[]"
if [ -f /proc/net/arp ]; then
    ARP_NEIGHBORS=$(python3 -c "
import json
neighbors=[]
with open('/proc/net/arp') as f:
    next(f)  # skip header
    for line in f:
        parts=line.split()
        if len(parts)>=6 and parts[2]!='0x0':
            neighbors.append({'ip':parts[0],'mac':parts[3],'iface':parts[5]})
print(json.dumps(neighbors))
" 2>/dev/null || echo "[]")
fi

# Build report
python3 -c "
import json
report = {
    'ip': '$MY_IP',
    'gateway': '$MY_GW',
    'dns': '$MY_DNS',
    'mac': '$MY_MAC',
    'subnet': '$MY_SUBNET',
    'arp_neighbors': $ARP_NEIGHBORS,
    'mode': 'passive'
}
with open('$REPORT', 'w') as f:
    json.dump(report, f, indent=2)
print(json.dumps(report, indent=2))
"

echo "$LOG Network report saved to $REPORT (passive, zero traffic generated)"
