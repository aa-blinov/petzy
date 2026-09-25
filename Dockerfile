FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY web ./web
# Only the reminders service's own entrypoint — not the rest of
# scripts/, which is dev/ops tooling (local seed data with a hardcoded
# dev password, one-off audit and migration scripts, screenshot
# helpers) that has no business in a shipped image.
COPY scripts/send_medication_reminders.py ./scripts/send_medication_reminders.py
# Run by the deploy after every start: moves any file still in GridFS to
# object storage (idempotent, a no-op once everything has moved).
COPY scripts/migrate_files_to_s3.py ./scripts/migrate_files_to_s3.py
COPY gunicorn.conf.py ./