#!/bin/bash
# Test script to manually trigger MongoDB backup

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

echo "Creating test backup..."

# Run a one-time backup using the same script
docker-compose run --rm mongo-backup sh -c "
  MONGO_USER=\${MONGO_USER:-admin}
  MONGO_PASS=\${MONGO_PASS:-password}
  MONGO_DB=\${MONGO_DB:-cat_health}
  MONGO_HOST=\${MONGO_HOST:-db}
  MONGO_PORT=\${MONGO_PORT:-27017}
  
  TIMESTAMP=\$(date +%Y%m%d_%H%M%S)
  BACKUP_DIR=\"/backups/backup-test-\$TIMESTAMP\"
  
  echo \"Starting test backup...\"
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
    echo \"Test backup completed successfully!\"
    echo \"Backup location: \$BACKUP_DIR\"
    echo \"Backup size: \$BACKUP_SIZE\"
    ls -lh /backups/ | grep backup-test
  else
    echo \"ERROR: Test backup failed!\"
    exit 1
  fi
"

echo ""
echo "Backup completed! Check ./backups directory"

