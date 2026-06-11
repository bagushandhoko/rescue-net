#!/bin/sh
set -eu

TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="/volume1/docker/backup-rescue-net-prod-$TS"

echo "Creating backup: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

echo "Backup web..."
tar -czf "$BACKUP_DIR/rescue-net-web.tar.gz" -C /volume1/web rescue-net

echo "Backup api..."
tar -czf "$BACKUP_DIR/rescue-net-api.tar.gz" -C /volume1/docker rescue-net-api

echo "Backup database dump..."
if sudo docker ps --filter name=postgres-main --format '{{.Names}}' | grep -q '^postgres-main$'; then
  sudo docker exec postgres-main pg_dump -U postgres rescuenet_db > "$BACKUP_DIR/rescuenet_db.sql"
else
  echo "WARN: postgres-main not running, database dump skipped"
fi

echo "Backup metadata..."
cat > "$BACKUP_DIR/README.txt" <<META
Rescue-Net production backup
Created: $TS

Includes:
- rescue-net-web.tar.gz
- rescue-net-api.tar.gz
- rescuenet_db.sql if postgres-main was running

Restore web:
tar -xzf rescue-net-web.tar.gz -C /volume1/web

Restore api:
tar -xzf rescue-net-api.tar.gz -C /volume1/docker

Restore db example:
cat rescuenet_db.sql | sudo docker exec -i postgres-main psql -U postgres -d rescuenet_db
META

echo "✅ Backup complete: $BACKUP_DIR"
