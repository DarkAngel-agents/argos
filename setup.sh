#!/usr/bin/env bash
# ARGOS Public Setup Script - Template v1.0
# First complete argos-setup.yaml, then run this script.

echo "=== ARGOS Public Setup ==="

if [ "$(id -u)" -eq 0 ]; then
    echo "Do not run as root. Use normal user."
    exit 1
fi

mkdir -p ~/.argos/argos-core ~/.argos/docker ~/.argos/config ~/.argos/backups/db ~/.ssh

echo "→ Copying files from public repo..."

# Files will be copied here from the public repo

echo "→ Initial configuration completed."
echo "Complete ~/.argos/config/argos-setup.yaml and run setup.sh again."
echo "=== SETUP TEMPLATE READY ==="
