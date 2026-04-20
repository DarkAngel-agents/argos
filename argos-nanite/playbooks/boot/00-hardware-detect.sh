#!/bin/bash
# NANITE BOOT: Hardware detection - ruleaza la fiecare boot, zero retea
set -e
LOG="[NANITE:HW]"
REPORT="/tmp/nanite-hw.json"

echo "$LOG Detecting hardware..."

# CPU
CPU_MODEL=$(grep "model name" /proc/cpuinfo | head -1 | sed 's/.*: //' | tr -d '\n')
CPU_CORES=$(grep -c "^processor" /proc/cpuinfo)

# RAM
RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
RAM_MB=$((RAM_KB / 1024))

# UEFI
UEFI="false"
[ -d /sys/firmware/efi ] && UEFI="true"

# Arch
ARCH=$(uname -m)

# GPU
GPU=$(lspci 2>/dev/null | grep -i "vga\|3d\|display" | sed 's/.*: //' | head -1 || echo "")

# Disks
DISKS="[]"
if command -v lsblk >/dev/null 2>&1; then
    DISKS=$(lsblk -J -b -o NAME,SIZE,TYPE,MODEL,ROTA 2>/dev/null | \
        python3 -c "
import sys,json
d=json.load(sys.stdin)
out=[]
for b in d.get('blockdevices',[]):
    if b.get('type')=='disk':
        t='ssd' if not b.get('rota') else 'hdd'
        if 'nvme' in b.get('name',''): t='nvme'
        out.append({'name':b['name'],'size_gb':round(int(b.get('size',0))/1e9,1),'type':t,'model':b.get('model','')})
print(json.dumps(out))
" 2>/dev/null || echo "[]")
fi

# NICs
NICS="[]"
if command -v ip >/dev/null 2>&1; then
    NICS=$(python3 -c "
import os,json
nics=[]
for n in os.listdir('/sys/class/net/'):
    if n=='lo': continue
    mac=open(f'/sys/class/net/{n}/address').read().strip() if os.path.exists(f'/sys/class/net/{n}/address') else ''
    nics.append({'name':n,'mac':mac})
print(json.dumps(nics))
" 2>/dev/null || echo "[]")
fi

# Build report
python3 -c "
import json
report = {
    'cpu_model': '''$CPU_MODEL''',
    'cpu_cores': $CPU_CORES,
    'ram_mb': $RAM_MB,
    'arch': '$ARCH',
    'uefi': $UEFI,
    'gpu': '''$GPU''',
    'disks': $DISKS,
    'network_interfaces': $NICS
}
with open('$REPORT', 'w') as f:
    json.dump(report, f, indent=2)
print(json.dumps(report, indent=2))
"

echo "$LOG Hardware report saved to $REPORT"
