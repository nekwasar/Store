#!/bin/sh
set -e

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/fastapi_shop-$TIMESTAMP.archive"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting MongoDB backup..."
mongodump \
    --uri="${MONGODB_URL:-mongodb://mongo:27017}" \
    --db="${MONGODB_DB:-fastapi_shop}" \
    --archive="$BACKUP_FILE" \
    --gzip

echo "[$(date)] Backup saved: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"

# Remove old backups
find "$BACKUP_DIR" -name "*.archive" -mtime "+$RETENTION_DAYS" -delete 2>/dev/null || true

echo "[$(date)] Cleaned backups older than $RETENTION_DAYS days"
echo "[$(date)] Done"
