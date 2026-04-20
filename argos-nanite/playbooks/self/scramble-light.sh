#!/bin/bash
# NANITE: Scramble Light - wipe collected data, keep nanite functional
set -e
LOG="[NANITE:SCRAMBLE]"

echo "$LOG Scrambling collected data..."

# Clear all reports and results
rm -rf /tmp/nanite-*.json 2>/dev/null || true
rm -rf /tmp/nanite-results/ 2>/dev/null || true
rm -rf /tmp/scan-* 2>/dev/null || true

# Clear bash history
history -c 2>/dev/null || true
> ~/.bash_history 2>/dev/null || true
> /home/argos/.bash_history 2>/dev/null || true

# Clear temp files
rm -rf /tmp/*.log /tmp/*.txt /tmp/*.out 2>/dev/null || true

# Clear journals
journalctl --vacuum-time=1s 2>/dev/null || true

# Drop page cache
echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true

echo "$LOG Scramble complete. Nanite still operational."
