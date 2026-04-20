#!/usr/bin/env bash
BACKUP_DIR="/home/darkangel/.argos/backups/db"
mkdir -p "$BACKUP_DIR"
OUTFILE="$BACKUP_DIR/claudedb-$(date +%Y%m%d-%H%M).sql.gz"
docker exec argos-db pg_dump -U claude claudedb | gzip > "$OUTFILE"
# Pastreaza doar ultimele 3
ls -t "$BACKUP_DIR"/claudedb-*.sql.gz 2>/dev/null | tail -n +4 | xargs rm -f
echo "[BACKUP] DB backup done: $(ls -lh $OUTFILE | awk '{print $5, $9}')"
