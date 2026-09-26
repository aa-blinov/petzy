#!/usr/bin/env bash
# End-to-end check of the backup service's image, the same in CI and
# locally: needs Docker only, never touches the real bucket.
#
#   scripts/backup_e2e.sh
#
# Builds backup/Dockerfile, starts MongoDB and an in-memory S3 (moto) on
# a private Docker network, seeds some data, makes four backups with the
# production settings (newest three kept), restores the newest into a
# fresh database and compares it with the original. The S3 side is
# driven with the backup image's own Python, so nothing is installed on
# the host.
set -euo pipefail

cd "$(dirname "$0")/.."

NET=petzy-backup-e2e
IMAGE=petzy-backup-e2e
BUCKET=petzy-e2e
# A quote and an @ on purpose: the password travels in a config file and
# has to survive its quoting.
export MONGO_PASS='p@ss"word'

cleanup() { docker rm -f "$NET-mongo" "$NET-s3" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

echo "== build"
docker build -q -f backup/Dockerfile -t "$IMAGE" . >/dev/null
docker network create "$NET" >/dev/null
docker run -d --name "$NET-mongo" --network "$NET" \
  -e MONGO_INITDB_ROOT_USERNAME=root -e MONGO_INITDB_ROOT_PASSWORD="$MONGO_PASS" mongo:latest >/dev/null
docker run -d --name "$NET-s3" --network "$NET" motoserver/moto:latest >/dev/null

# The backup image, pointed at this network's MongoDB and S3.
in_image() {
  # -i: the Python steps below come in on stdin.
  docker run -i --rm --network "$NET" \
    -e MONGO_HOST="$NET-mongo" -e MONGO_PORT=27017 -e MONGO_USER=root -e MONGO_PASS -e MONGO_DB=petzy \
    -e S3_ENDPOINT="http://$NET-s3:5000" -e S3_REGION=us-east-1 -e S3_BUCKET="$BUCKET" \
    -e S3_KEY_ID=e2e -e S3_SECRET_KEY=e2e -e BACKUP_KEEP=3 \
    "$@"
}
mongosh_() { docker exec "$NET-mongo" mongosh --quiet -u root -p "$MONGO_PASS" --authenticationDatabase admin "$@"; }

echo "== wait for MongoDB and S3"
for _ in $(seq 1 60); do
  mongosh_ --eval 'db.adminCommand("ping").ok' 2>/dev/null | grep -q 1 && break
  sleep 1
done
in_image "$IMAGE" python3 - <<'PY'
import time
from web import storage
for _ in range(60):
    try:
        storage._client().create_bucket(Bucket=storage._bucket())
        break
    except Exception as e:
        last = e
        time.sleep(1)
else:
    raise SystemExit(f"S3 never came up: {last}")
PY

echo "== seed"
mongosh_ petzy --eval '
  db.pets.insertMany([{ name: "Рекс" }, { name: "Барсик" }]);
  db.events.insertMany(Array.from({ length: 500 }, (_, i) => ({ i })));' >/dev/null

echo "== four backups, the newest three kept"
for _ in 1 2 3 4; do
  in_image "$IMAGE" python3 scripts/backup_to_s3.py --once </dev/null 2>&1 | sed -E 's/^[0-9-]+ [0-9:,]+ - backup - /  /'
  sleep 1.1  # backup keys are per second
done

echo "== restore the newest into a fresh database"
in_image -v "$PWD:/out" "$IMAGE" python3 - <<'PY'
import sys
sys.path.insert(0, "scripts")
from web import storage
import backup_to_s3 as backup

keys = [b["key"] for b in backup.list_backups(storage)]
print("  in the bucket:", keys)
assert len(keys) == 3 and all(k.startswith("backups/mongo/petzy-") for k in keys), keys
storage._client().download_file(storage._bucket(), keys[0], "/out/.e2e-newest.archive.gz")
PY
docker cp .e2e-newest.archive.gz "$NET-mongo:/tmp/newest.archive.gz"
rm -f .e2e-newest.archive.gz
docker exec "$NET-mongo" mongorestore -u root -p "$MONGO_PASS" --authenticationDatabase admin \
  --archive=/tmp/newest.archive.gz --gzip --nsFrom 'petzy.*' --nsTo 'restored.*' --quiet

counts() { mongosh_ "$1" --eval 'print(db.pets.countDocuments() + "/" + db.events.countDocuments() + " " + db.pets.find().toArray().map(p => p.name).sort().join(","))'; }
original="$(counts petzy)"
restored="$(counts restored)"
echo "  original: $original"
echo "  restored: $restored"
[ "$restored" = "2/500 Барсик,Рекс" ] && [ "$original" = "$restored" ]
echo "OK: backed up, rotated to three, restored intact"
