#!/usr/bin/env bash
# ARGOS Public Setup Script - Template v1.0
# Completeaza argos-setup.yaml mai intai, apoi ruleaza acest script.

echo "=== ARGOS Public Setup ==="

if [ "$(id -u)" -eq 0 ]; then
    echo "Nu rula ca root. Foloseste user normal."
    exit 1
fi

mkdir -p ~/.argos/argos-core ~/.argos/docker ~/.argos/config ~/.argos/backups/db ~/.ssh

echo "→ Copiere fisiere din repo..."
# Aici se vor copia fisierele din repo-ul public

echo "→ Configurare initiala terminata."
echo "Completeaza ~/.argos/config/argos-setup.yaml si ruleaza din nou setup.sh"

echo "=== SETUP TEMPLATE GATA ==="
