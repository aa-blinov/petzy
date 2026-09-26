# The daily backup (scripts/backup_to_s3.py). The mongo image, so
# mongodump/mongorestore come from the same release as the database
# (docker-compose's `db`), plus Python and boto3 to talk to the bucket.
FROM mongo:latest
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-boto3 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
# Only what the backup needs: the storage module and the script.
COPY web/__init__.py web/storage.py ./web/
COPY scripts/backup_to_s3.py ./scripts/backup_to_s3.py
# Not the image's mongod entrypoint: this container never runs a server.
ENTRYPOINT []
CMD ["python3", "scripts/backup_to_s3.py"]
