# The daily backup (scripts/backup_to_s3.py). The mongo image, so
# mongodump/mongorestore come from the same release as the database
# (docker-compose's `db`), plus Python and boto3 to talk to the bucket.
# The same major.minor as docker-compose's `db`: mongodump and mongorestore
# must match the server's release.
FROM mongo:8.2
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-boto3 python3-pip \
    && pip3 install --no-cache-dir --break-system-packages sentry-sdk==2.70.0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
# Only what the backup needs: the storage module and the script.
COPY web/__init__.py web/storage.py web/observability.py ./web/
COPY scripts/backup_to_s3.py ./scripts/backup_to_s3.py
# Not root, as in the app's Dockerfile: a hole in the script or a library
# gets an account that owns nothing here (the code is root's and read-only
# to it). The dump goes to the temporary directory, the one place every
# user may write to, so nothing else needs to be writable.
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin petzy
USER petzy
# Not the image's mongod entrypoint: this container never runs a server.
ENTRYPOINT []
CMD ["python3", "scripts/backup_to_s3.py"]
