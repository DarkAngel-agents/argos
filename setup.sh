#!/usr/bin/env bash
# ARGOS Public Setup Script - Template
# Completează argos-setup.yaml mai întâi

echo "=== ARGOS Public Setup ==="

# Verificări de bază
if [ "$(id -u)" -eq 0 ]; then
    echo "Nu rula ca root. Folosește user normal."
    exit 1
fi

echo "→ Creare directoare..."
mkdir -p ~/.argos/argos-core ~/.argos/docker ~/.argos/config ~/.argos/backups/db ~/.ssh

echo "→ Copiere fișiere..."
# Aici se vor copia fișierele din repo (Dockerfile, swarm-stack.yml etc.)

echo "→ Completează argos-setup.yaml mai întâi!"
echo "Apoi rulează: bash ~/.argos/argos-core/setup.sh"

echo "=== SETUP TEMPLATE GATA ==="
