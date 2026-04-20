#!/bin/bash
# NANITE BOOT: Announce to ARGOS via Tailscale only
set -e
LOG="[NANITE:ANN]"

ARGOS_URL="${ARGOS_URL:-}"
NODE_ID="${NANITE_NODE_ID:-nanite-$(cat /etc/machine-id | head -c 8)}"

if [ -z "$ARGOS_URL" ]; then
    echo "$LOG ERROR: ARGOS_URL not set"
    exit 1
fi

# Wait for Tailscale
TS_IP=""
for i in $(seq 1 30); do
    TS_IP=$(tailscale ip -4 2>/dev/null || echo "")
    [ -n "$TS_IP" ] && break
    sleep 1
done

# Load hardware + network reports from previous boot steps
HW_REPORT="/tmp/nanite-hw.json"
NET_REPORT="/tmp/nanite-net.json"

HW="{}"
NET="{}"
[ -f "$HW_REPORT" ] && HW=$(cat "$HW_REPORT")
[ -f "$NET_REPORT" ] && NET=$(cat "$NET_REPORT")

# Build announce payload
PAYLOAD=$(python3 -c "
import json
hw = json.loads('''$HW''')
net = json.loads('''$NET''')
payload = {
    'node_id': '$NODE_ID',
    'ip': net.get('ip', ''),
    'hostname': '$(hostname)',
    'arch': hw.get('arch', ''),
    'uefi': hw.get('uefi', False),
    'cpu_model': hw.get('cpu_model', ''),
    'cpu_cores': hw.get('cpu_cores', 0),
    'cpu_threads': hw.get('cpu_cores', 0),
    'ram_mb': hw.get('ram_mb', 0),
    'disks': hw.get('disks', []),
    'gpu': hw.get('gpu', ''),
    'network_interfaces': hw.get('network_interfaces', []),
    'nanite_version': '2.0',
    'tailscale_ip': '$TS_IP',
    'tailscale_name': '$NODE_ID',
}
print(json.dumps(payload))
")

# Announce with retries
for i in 1 2 3 4 5; do
    RESP=$(curl -sf -X POST "$ARGOS_URL/api/nanite/announce" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" --connect-timeout 5 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo "$LOG Announced OK: $RESP"
        # Display on console
        echo ""
        echo "======================================"
        echo "  ARGOS NANITE v2.0"
        echo "  Node:  $NODE_ID"
        echo "  LAN:   $(echo "$NET" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("ip","?"))' 2>/dev/null)"
        echo "  TS:    $TS_IP"
        echo "  ARGOS: $ARGOS_URL"
        echo "======================================"
        echo ""
        exit 0
    fi
    echo "$LOG Retry $i..."
    sleep 3
done

echo "$LOG Announce failed after 5 retries"
exit 1
