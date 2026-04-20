#!/bin/bash
# NANITE WATCHER: Passive intrusion detection
# Monitors iptables logs for port scans + ARP for new devices
# Runs as daemon, alerts ARGOS on suspicious activity
set -e
LOG="[NANITE:WATCH]"

ARGOS_URL="${ARGOS_URL:-}"
NODE_ID="${NANITE_NODE_ID:-unknown}"
REACTION="${NANITE_REACTION:-QUIET}"
ARP_SNAPSHOT="/tmp/nanite-arp-baseline.json"
CHECK_INTERVAL=30

echo "$LOG Starting watcher (reaction=$REACTION)..."

# Setup iptables logging on honeypot ports (if not already set)
setup_iptables() {
    # Log any SYN to common ports (except our honeypots which handle themselves)
    for port in 21 23 80 135 139 443 3389 5900 8080 8443; do
        iptables -C INPUT -p tcp --dport $port --syn -j LOG \
            --log-prefix "NANITE_SCAN:" --log-level 4 2>/dev/null || \
        iptables -A INPUT -p tcp --dport $port --syn -j LOG \
            --log-prefix "NANITE_SCAN:" --log-level 4 2>/dev/null || true
    done
    # DROP after log (don't respond)
    for port in 21 23 80 135 139 443 3389 5900 8080 8443; do
        iptables -C INPUT -p tcp --dport $port --syn -j DROP 2>/dev/null || \
        iptables -A INPUT -p tcp --dport $port --syn -j DROP 2>/dev/null || true
    done
    echo "$LOG iptables scan detection configured"
}

# Take ARP baseline
take_arp_baseline() {
    python3 -c "
import json
neighbors=[]
with open('/proc/net/arp') as f:
    next(f)
    for line in f:
        parts=line.split()
        if len(parts)>=6 and parts[2]!='0x0':
            neighbors.append({'ip':parts[0],'mac':parts[3]})
with open('$ARP_SNAPSHOT','w') as f:
    json.dump(neighbors, f)
print(f'ARP baseline: {len(neighbors)} neighbors')
" 2>/dev/null
}

# Check for new ARP entries
check_arp_changes() {
    python3 -c "
import json, os, urllib.request, time

baseline_file = '$ARP_SNAPSHOT'
if not os.path.exists(baseline_file):
    exit(0)

with open(baseline_file) as f:
    baseline = {n['ip']:n['mac'] for n in json.load(f)}

current = {}
with open('/proc/net/arp') as f:
    next(f)
    for line in f:
        parts = line.split()
        if len(parts) >= 6 and parts[2] != '0x0':
            current[parts[0]] = parts[3]

new_devices = []
for ip, mac in current.items():
    if ip not in baseline:
        new_devices.append({'ip': ip, 'mac': mac})
    elif baseline[ip] != mac:
        new_devices.append({'ip': ip, 'mac': mac, 'old_mac': baseline[ip], 'type': 'mac_changed'})

if new_devices:
    print(f'[NANITE:WATCH] New/changed devices: {json.dumps(new_devices)}')
    argos_url = '$ARGOS_URL'
    node_id = '$NODE_ID'
    if argos_url:
        try:
            data = json.dumps({
                'node_id': node_id,
                'status': 'alert',
                'cpu_pct': -1, 'mem_pct': -1,
                'tailscale_ip': '',
            }).encode()
            req = urllib.request.Request(
                argos_url.rstrip('/') + '/api/nanite/heartbeat',
                data=data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            urllib.request.urlopen(req, timeout=5)
        except:
            pass
" 2>/dev/null
}

# Check kernel log for scan attempts
check_scan_log() {
    # Check last 30 seconds of kernel log
    SCANS=$(dmesg -T 2>/dev/null | grep "NANITE_SCAN:" | tail -5)
    if [ -n "$SCANS" ]; then
        echo "$LOG Port scan detected:"
        echo "$SCANS"
        # Clear to avoid re-alerting
        dmesg -C 2>/dev/null || true

        if [ "$REACTION" = "PANIC" ]; then
            echo "$LOG PANIC reaction!"
            /etc/nanite/playbooks/self/panic.sh &
            exit 0
        elif [ "$REACTION" = "DEFENSIVE" ]; then
            echo "$LOG DEFENSIVE: rotating identity..."
            /etc/nanite/playbooks/boot/02-masquerade.sh
        fi
    fi
}

# Main
setup_iptables
take_arp_baseline

while true; do
    check_scan_log
    check_arp_changes
    sleep $CHECK_INTERVAL
done
