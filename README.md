# Petzy

**Petzy** is a pet health diary: a Progressive Web App (installable on a phone) with a Flask + MongoDB API behind it. Feeding, weight, litter, eye drops and any event type a household adds, medication courses with doses, stock and reminders, documents and scans, shared between the people who look after the pet.

- Production: https://petzy.duckdns.org
- API reference: https://petzy.duckdns.org/api/docs

## Features

- **Records.** Built-in event types (feeding, weight, defecation, litter, eye drops, tooth brushing, ear cleaning, asthma) and custom ones with their own fields, visible to the household that made them. A feed, a history with filters and trend charts, unusual-value alerts, export to CSV, TSV, HTML, Markdown or a ZIP of everything.
- **Medications.** Courses with a schedule, today's next dose on the feed («Принять», «Уже дали в 08:00», «Пропустить»), intake times that can be corrected, stock that counts down and says when to buy more, undo for a dose marked by mistake.
- **Documents.** Photos and PDFs up to 10 MB, scans and archives up to 500 MB uploaded straight to object storage, expiry reminders. A 2 GB quota per pet owner.
- **Pets and sharing.** 12 species (and «другой питомец») with their own tiles and fields, photos, sharing by invitation (the other person accepts, and can leave later).
- **Accounts.** Open sign-up (can be closed), password recovery by a one-time link to a confirmed email, email and password in Settings, an admin panel for disabling accounts.
- **Notifications.** Web Push for doses, expiring documents and unusual values, to everyone with access to the pet.
- **App.** Installable PWA that updates itself, dark theme, per-account form defaults, reorderable «+» tiles, in-app help (Настройки → «Справка»).

## Stack

- **Backend:** Python 3.12, Flask, flask-pydantic-spec (validation and the OpenAPI spec), pymongo, gunicorn, Flask-Limiter, boto3 (Backblaze B2, S3 API), pywebpush, Pillow.
- **Frontend:** React 18, TypeScript, Vite, antd-mobile, TanStack Query, React Router, React Hook Form + Zod, vite-plugin-pwa (Workbox, `injectManifest`).
- **Infrastructure:** Docker Compose, nginx, MongoDB, GitHub Actions (CI, deploy on push to `master`).

## API

The reference is published at **https://petzy.duckdns.org/api/docs** (ReDoc) with the spec at **/api/openapi.json** (OpenAPI 3.1). It covers signing in from a native app (tokens in the body for requests without an `Origin` header, `Authorization: Bearer`), the error format, date and time conventions, uploads and limits. The spec is generated from the routes' pydantic schemas and completed in `web/openapi_doc.py`; responses are validated against those schemas at runtime.

## Running locally

The quickest way needs no MongoDB or Docker: `scripts/dev_local.py` runs the API against an in-memory database (mongomock), seeds demo pets and two months of history, and keeps outgoing mail in memory.

```sh
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python scripts/dev_local.py        # API on http://localhost:5001

cd frontend && npm install && npm run dev    # app on http://localhost:5173
```

Sign in as `admin` / `test1234` (local runner only). The Vite dev server proxies `/api` to port 5001.

- Files go to the same bucket as production under `dev/` when `S3_*` keys are in `.env`, or to an in-memory S3 with `DEV_STORAGE=memory`.
- Letters (confirmation, password reset) are listed at http://localhost:5001/api/dev/outbox. The endpoint answers 404 anywhere else.
- `/apidoc/redoc` and `/api/docs` both show the API reference.

### Tests and checks

```sh
.venv/bin/python -m pytest tests          # backend, mongomock and moto, no network
.venv/bin/ruff check . && .venv/bin/ruff format --check .
cd frontend && npm run lint && npm run build
```

Git hooks run these for you: enable them once with `git config core.hooksPath .githooks` (see `CLAUDE.md`).

## Running with Docker

```sh
cp .env.example .env    # then fill it in, see below
docker compose up -d --build
```

| Service | What it does |
|---|---|
| `db` | MongoDB, on `127.0.0.1:27017` only |
| `web` | the API (gunicorn), on `127.0.0.1:5001` |
| `frontend` | builds the app and copies it into a shared volume |
| `nginx` | serves the app and forwards `/api/` to `web`, on `127.0.0.1:3000` |
| `reminders` | sends push reminders for doses and expiring documents |
| `backup` | daily database backup to the bucket |

In production a host nginx terminates TLS and forwards everything to `127.0.0.1:3000`; security headers, the real client address and the Secure cookie flag are set by `nginx/nginx.conf`.

### Environment

`.env.example` lists every variable with comments. The ones that matter:

| Variable | |
|---|---|
| `MONGO_USER`, `MONGO_PASS`, `MONGO_DB` | database |
| `FLASK_SECRET_KEY`, `JWT_SECRET_KEY` | a long random value; the app refuses to start with an example one |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH` | the admin account (bcrypt hash) |
| `S3_ENDPOINT`, `S3_REGION`, `S3_BUCKET`, `S3_KEY_ID`, `S3_SECRET_KEY` | object storage for every file and the backups |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | mail for password recovery; without it the app says recovery goes through the admin |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIMS_EMAIL` | Web Push (`python -m scripts.generate_vapid_keys`) |
| `REGISTRATION_ENABLED` | `false` closes sign-up |
| `STORAGE_QUOTA_MB` | documents per pet owner, default 2048 |

A bcrypt hash for the admin password:

```sh
python -c "import bcrypt; print(bcrypt.hashpw(b'your_password', bcrypt.gensalt()).decode())"
```

## Deploying

A push to `master` runs CI and deploys to the server (`.github/workflows/deploy.yaml`): it pulls, writes the secrets below into the server's `.env`, rebuilds and restarts the stack. One deploy runs at a time. It can also be started by hand, e.g. after changing a secret:

```sh
gh workflow run "Deploy to Server"
```

Repository secrets: `SERVER_PETZY_HOST`, `SERVER_PETZY_USER`, `SERVER_PETZY_SSH_KEY`, `S3_KEY_ID`, `S3_SECRET_KEY`, `VAPID_*`, `SMTP_*`. Set one with `gh secret set NAME` (it asks for the value).

Other workflows (all run by hand):

- **Diagnose server:** containers, disk, nginx, which settings are set (never their values), mail login, backups, optionally a restore check.
- **Storage check:** the bucket and its keys.
- **Inspect DB:** document counts, never the data.
- **Migrate events:** one-off data migrations.
- **Cleanup refresh tokens:** removes expired sessions.

The repository is public, and so are the Actions logs: workflows print counts and presence, never user data or secrets.

## Backups

The `backup` service (`backup/Dockerfile`, `scripts/backup_to_s3.py`) backs up the database to the bucket once a day:

- dumps it with `mongodump` into one gzipped archive and checks it reads back (`mongorestore --dryRun`);
- uploads it to `backups/mongo/<db>-YYYYMMDD-HHMMSS.archive.gz`, apart from users' files (`users/`) and local runs (`dev/`), and checks the stored size;
- only then deletes all but the newest `BACKUP_KEEP` (3) backups, every version of them.

A failed attempt keeps the older backups and is retried an hour later. When the service starts and the newest backup is more than a day old, it backs up at once. Files (photos, documents, scans) are in the bucket already and are not part of the dump.

A backup right now:

```sh
docker compose run --rm backup python3 scripts/backup_to_s3.py --once
```

**Restoring** (overwrites the collections it restores; pick the file from the list the Diagnose workflow prints):

```sh
# 1. Download it into the current directory (or from the Backblaze web console)
docker compose run --rm -v "$PWD:/out" backup python3 -c "from web import storage; \
  storage._client().download_file(storage._bucket(), 'backups/mongo/<file>.archive.gz', '/out/b.archive.gz')"
# 2. Restore it into the running database
docker compose cp b.archive.gz db:/tmp/b.archive.gz
docker compose exec db mongorestore -u "$MONGO_USER" -p "$MONGO_PASS" --authenticationDatabase admin \
  --archive=/tmp/b.archive.gz --gzip --drop
```

To look at a backup without touching the live data, restore it under another name with `--nsFrom '<db>.*' --nsTo 'restored.*'` instead of `--drop`.

## Project structure

```text
web/                     Flask API
  app.py                 app, blueprints, security headers, rate limits
  auth.py                sign-in, sign-up, refresh, logout
  account.py             email, password, recovery by email
  security.py            tokens, sessions, access decorators
  pets.py                pets, photos, sharing and invitations
  events.py              records, event types, feed, stats
  builtin_event_types.py the built-in types and their order
  medications.py         courses, intakes, stock, upcoming doses
  documents.py           documents, scans, quota
  storage.py             object storage (keys, signed URLs)
  push.py, push_delivery.py  Web Push
  export.py              exports
  users.py               users, search, form defaults
  mail.py                SMTP
  openapi_doc.py         the published API reference
  schemas.py             pydantic request and response models
frontend/src/            React app (pages, components, services, hooks, utils)
  content/help.ts        the in-app help
  sw.ts                  the service worker
nginx/                   the app's nginx (nginx.conf, security-headers.conf)
scripts/                 dev_local.py, reminders sender, backups, migrations, checks
tests/                   backend tests (stateless and stateful)
.github/workflows/       CI, deploy, maintenance
```

## License

MIT. See the [LICENSE](https://opensource.org/license/mit) text.
