#!/bin/bash
# Manual MongoDB backup script
# Run this script to manually trigger a one-time backup

set -e

cd "$(dirname "$0")/.."

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found"
    exit 1
fi

# Check if containers are running
if ! docker-compose ps db 2>/dev/null | grep -q "Up"; then
    echo "Error: MongoDB container is not running"
    echo "Please start containers first: docker-compose up -d"
    exit 1
fi

echo "Creating manual backup..."

# Run a one-time backup
docker-compose run --rm mongo-backup sh -c "
  MONGO_USER=\${MONGO_USER:-admin}
  MONGO_PASS=\${MONGO_PASS:-password}
  MONGO_DB=\${MONGO_DB:-cat_health}
  MONGO_HOST=\${MONGO_HOST:-db}
  MONGO_PORT=\${MONGO_PORT:-27017}
  
  TIMESTAMP=\$(date +%Y%m%d_%H%M%S)
  BACKUP_DIR=\"/backups/backup-manual-\$TIMESTAMP\"
  
  echo \"Starting manual backup...\"
  mongodump \\
    --host=\"\$MONGO_HOST\" \\
    --port=\"\$MONGO_PORT\" \\
    --username=\"\$MONGO_USER\" \\
    --password=\"\$MONGO_PASS\" \\
    --authenticationDatabase=admin \\
    --db=\"\$MONGO_DB\" \\
    --out=\"\$BACKUP_DIR\" \\
    --gzip
  
  if [ \$? -eq 0 ]; then
    BACKUP_SIZE=\$(du -sh \"\$BACKUP_DIR\" | cut -f1)
    echo \"Manual backup completed successfully!\"
    echo \"Backup location: \$BACKUP_DIR\"
    echo \"Backup size: \$BACKUP_SIZE\"
    ls -lh /backups/ | grep backup-manual
  else
    echo \"ERROR: Manual backup failed!\"
    exit 1
  fi
"

echo ""
echo "Backup completed! Check ./backups directory"

