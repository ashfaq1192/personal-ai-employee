#!/usr/bin/env bash
# Odoo backup script — PostgreSQL dump + filestore archive.
#
# Retention: 7 daily + 4 weekly backups.
# Install as cron: 0 2 * * * /opt/ai-employee/src/cloud/deploy/backup-odoo.sh
#
# Usage: bash src/cloud/deploy/backup-odoo.sh [--backup-dir /path/to/backups]

set -euo pipefail

BACKUP_DIR="${1:-/opt/odoo/backups}"
ODOO_DB="${ODOO_DB:-odoo}"
ODOO_FILESTORE="/opt/odoo/.local/share/Odoo/filestore/$ODOO_DB"
DATE=$(date +%Y-%m-%d_%H%M)
DAY_OF_WEEK=$(date +%u)

mkdir -p "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly"

echo "=== Odoo Backup: $DATE ==="

# PostgreSQL dump
echo "[1/3] Dumping PostgreSQL database '$ODOO_DB'..."
DUMP_FILE="$BACKUP_DIR/daily/${ODOO_DB}_${DATE}.sql.gz"
sudo -u odoo pg_dump "$ODOO_DB" | gzip > "$DUMP_FILE"
echo "  Database dump: $DUMP_FILE ($(du -h "$DUMP_FILE" | cut -f1))"

# Filestore archive
echo "[2/3] Archiving filestore..."
FILESTORE_ARCHIVE="$BACKUP_DIR/daily/${ODOO_DB}_filestore_${DATE}.tar.gz"
if [ -d "$ODOO_FILESTORE" ]; then
    tar -czf "$FILESTORE_ARCHIVE" -C "$(dirname "$ODOO_FILESTORE")" "$(basename "$ODOO_FILESTORE")"
    echo "  Filestore: $FILESTORE_ARCHIVE ($(du -h "$FILESTORE_ARCHIVE" | cut -f1))"
else
    echo "  No filestore found at $ODOO_FILESTORE — skipping"
fi

# Weekly backup (Sunday)
if [ "$DAY_OF_WEEK" -eq 7 ]; then
    echo "  Creating weekly backup copy..."
    cp "$DUMP_FILE" "$BACKUP_DIR/weekly/"
    [ -f "$FILESTORE_ARCHIVE" ] && cp "$FILESTORE_ARCHIVE" "$BACKUP_DIR/weekly/"
fi

# Cleanup: retain 7 daily + 4 weekly
echo "[3/3] Cleaning old backups..."
find "$BACKUP_DIR/daily" -name "*.gz" -mtime +7 -delete
find "$BACKUP_DIR/weekly" -name "*.gz" -mtime +28 -delete

# Verify latest backup
echo ""
echo "Verification:"
DUMP_SIZE=$(stat -c%s "$DUMP_FILE" 2>/dev/null || echo "0")
if [ "$DUMP_SIZE" -gt 1000 ]; then
    echo "  Database dump: OK ($DUMP_SIZE bytes)"
else
    echo "  WARNING: Database dump seems too small ($DUMP_SIZE bytes)"
fi

echo ""
echo "=== Backup complete ==="
echo "Daily backups:  $(ls -1 "$BACKUP_DIR/daily/" 2>/dev/null | wc -l) files"
echo "Weekly backups: $(ls -1 "$BACKUP_DIR/weekly/" 2>/dev/null | wc -l) files"
