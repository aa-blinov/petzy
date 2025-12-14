#!/bin/bash
# MongoDB backup script
# This script runs inside the mongo-backup container
# Environment variables are loaded from .env via docker-compose env_file

set -e

# Set default values if not provided (from .env file)
MONGO_USER=${MONGO_USER:-admin}
MONGO_PASS=${MONGO_PASS:-password}
MONGO_DB=${MONGO_DB:-cat_health}
MONGO_HOST=${MONGO_HOST:-db}
MONGO_PORT=${MONGO_PORT:-27017}
BACKUP_RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-7}


echo "=========================================="
echo "MongoDB Backup Script"
echo "=========================================="
echo "Database: $MONGO_DB"
echo "Host: $MONGO_HOST:$MONGO_PORT"
echo "Backup retention: $BACKUP_RETENTION_DAYS days"
echo "=========================================="

while true; do
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_DIR="/backups/backup-$TIMESTAMP"
    
    echo ""
    echo "[$(date)] Starting backup..."
    
    # Create backup
    mongodump \
        --host="$MONGO_HOST" \
        --port="$MONGO_PORT" \
        --username="$MONGO_USER" \
        --password="$MONGO_PASS" \
        --authenticationDatabase=admin \
        --db="$MONGO_DB" \
        --out="$BACKUP_DIR" \
        --gzip
    
    if [ $? -eq 0 ]; then
        BACKUP_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
        echo "[$(date)] Backup completed successfully!"
        echo "Backup location: $BACKUP_DIR"
        echo "Backup size: $BACKUP_SIZE"
    else
        echo "[$(date)] ERROR: Backup failed!"
    fi
    
    # Clean up old backups (older than retention days)
    echo "[$(date)] Cleaning up backups older than $BACKUP_RETENTION_DAYS days..."
    find /backups -name 'backup-*' -type d -mtime +$BACKUP_RETENTION_DAYS -exec rm -rf {} + 2>/dev/null || true
    
    # List current backups
    echo "[$(date)] Current backups:"
    ls -lh /backups/ | grep backup- || echo "  No backups found"
    
    echo "[$(date)] Next backup in 24 hours..."
    echo "=========================================="
    
    # Wait 24 hours before next backup
    sleep 86400
done

