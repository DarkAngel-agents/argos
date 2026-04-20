#!/bin/bash
# NANITE BOOT: Masquerade as generic Debian box
set -e
LOG="[NANITE:MASK]"

echo "$LOG Applying masquerade..."

# Hostname generic (configurable via env)
FAKE_HOST="${NANITE_HOSTNAME:-srv01}"
hostname "$FAKE_HOST" 2>/dev/null || true
echo "$FAKE_HOST" > /proc/sys/kernel/hostname 2>/dev/null || true

# MAC randomize pe interfata principala
IFACE=$(ip route | grep default | awk '{print $5}' | head -1)
if [ -n "$IFACE" ]; then
    # Generate random locally-administered MAC
    NEW_MAC=$(python3 -c "
import random
b=[random.randint(0,255) for _ in range(6)]
b[0]=(b[0]&0xfe)|0x02  # locally administered, unicast
print(':'.join(f'{x:02x}' for x in b))
")
    ip link set "$IFACE" down 2>/dev/null || true
    ip link set "$IFACE" address "$NEW_MAC" 2>/dev/null || true
    ip link set "$IFACE" up 2>/dev/null || true
    echo "$LOG MAC changed to $NEW_MAC on $IFACE"
fi

# TCP/IP fingerprint tweaks - look like Debian 12 kernel
sysctl -w net.ipv4.ip_default_ttl=64 >/dev/null 2>&1 || true
sysctl -w net.ipv4.tcp_window_scaling=1 >/dev/null 2>&1 || true
sysctl -w net.ipv4.tcp_timestamps=1 >/dev/null 2>&1 || true
sysctl -w net.ipv4.tcp_sack=1 >/dev/null 2>&1 || true
sysctl -w net.ipv4.tcp_ecn=0 >/dev/null 2>&1 || true

# Disable ALL network announcements
sysctl -w net.ipv4.conf.all.arp_announce=2 >/dev/null 2>&1 || true
sysctl -w net.ipv4.conf.all.arp_ignore=1 >/dev/null 2>&1 || true

# Kill any mDNS/avahi/NetBIOS if somehow running
pkill -f avahi 2>/dev/null || true
pkill -f nmbd 2>/dev/null || true
pkill -f mdnsd 2>/dev/null || true

# Fake /etc/os-release (for anyone who SSH-es in and checks)
cat > /tmp/fake-os-release << 'FAKEEOF'
PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"
NAME="Debian GNU/Linux"
VERSION_ID="12"
VERSION="12 (bookworm)"
ID=debian
HOME_URL="https://www.debian.org/"
FAKEEOF
mount --bind /tmp/fake-os-release /etc/os-release 2>/dev/null || true

echo "$LOG Masquerade active: hostname=$FAKE_HOST, Debian 12 fingerprint"
