# Architecture

How Petzy is put together.

A Progressive Web App over a Flask API and MongoDB. The app is the only
part a person touches, and it talks to one origin: the nginx in front of
the API.

```
phone (PWA) -> nginx -> Flask API -> MongoDB
                     |    |
                     |    +-> object storage (photos, documents, backups)
                     |
                     +-> MCP server -> the same API, with a personal token
```

## The shape

| Module | What it is responsible for |
| --- | --- |
| `web/app.py` | The application: the blueprints, the security headers, the rate limits and the request log. |
| `web/auth.py` | The sign-in, the registration, the refresh and the sign-out. |
| `web/security.py` | The tokens, the sessions and the access decorators. |
| `web/decorators.py` | `require_pet_access` and `require_record_access`, the two checks every route that touches a pet uses. |
| `web/pets.py` | The pets, the photos, the sharing and the invitations. |
| `web/events.py` | The records, the event types, the feed and the statistics. |
| `web/builtin_event_types.py` | The 34 built-in event types and their order. |
| `web/medications.py` | The courses, the doses, the stock and the nearest dose. |
| `web/documents.py` | The documents, the scans and the quota. |
| `web/medical_card.py`, `web/medical_card_full.py`, `web/medical_card_pdf.py` | The medical card, its full form and the PDF for the vet. |
| `web/medical_records.py` | The vaccinations, the treatments, the visits and the operations. |
| `web/medical_share.py` | The read-only link for a vet. |
| `web/vaccines.py` | The catalogue of the vaccines and the preparations. |
| `web/storage.py` | The object storage: the keys and the signed URLs. |
| `web/push.py`, `web/push_delivery.py` | Web Push: the subscriptions and the delivery. |
| `web/export.py` | The export to CSV, TSV, HTML, Markdown and the ZIP. |
| `web/legal.py` | The privacy policy and the consent with its version. |
| `web/schemas.py` | The pydantic request and response models. |
| `web/errors.py` | The error codes and their Russian texts. |
| `web/db.py` | The Mongo client and `ensure_indexes`. |
| `web/openapi_doc.py` | The OpenAPI specification and the published reference. |
| `frontend/src/pages/` | One file per screen. |
| `frontend/src/components/` | The shared pieces. |
| `frontend/src/services/` | One file per API area. |
| `frontend/src/hooks/`, `frontend/src/utils/` | The hooks and the helpers. |
| `frontend/src/styles/globals.css` | The tokens of the design system. |
| `frontend/src/sw.ts` | The service worker. |
| `mcp/petzy_mcp/` | The MCP server: the client, the tools, the HTTP app and the stdio mode. |
| `nginx/` | The nginx of the app and the security headers. |
| `scripts/` | The demo seeding, the reminders, the backups, the migrations and the audits. |
| `tests/stateless/`, `tests/stateful/` | The backend tests: without a database, and with mongomock and moto. |
| `e2e/` | The browser checks, which need the local stand. |

## The data flow

A record:

```
phone -> POST /api/events
  access token -> sessions -> user
  the pet of the record -> require_record_access
  the value, the time as it was typed and the time zone it was typed in
  MongoDB
```

A photo:

```
phone -> POST /api/pets/{id}/photo
  the file is converted to WebP at the upload
  the bytes go to the bucket, the key to MongoDB
  the app reads the file back through a signed URL
```

The medical card is not a separate questionnaire. It is read from the
records and the pet's profile when it is opened, and the PDF for the vet is
rendered from the same data with fpdf2 and the bundled DejaVu Sans.

## Decisions worth knowing about

### The events are the spine of the app

An event type is a set of fields, and the catalogue holds 34 of them. The
family adds its own types, and only the family that created them sees
them.

The cost: the medical card, the history, the charts, the export and the
statistics are all read from the records. A change to the shape of a record
reaches every one of them.

### A record keeps the time as it was typed

The value, the time and the time zone the time was typed in are all stored.
Nothing goes through `toISOString()`, which is UTC.

The cost: the history and the charts say the same thing on two phones in
two zones, and a comparison between two records has to normalise them
first.

### The medical card is assembled, not stored

It is read from the records and the profile when it is opened, and the PDF
is rendered from the same data.

The cost: there is no table of the card, so a change to the shape of a
record changes the card and the PDF with it, and the PDF has to be
regenerated to see the change.

### The access check is a decorator

`require_pet_access` and `require_record_access` sit on the routes that
touch a pet or a record, and the cleanup of a pet and the deletion of an
account keep lists of the collections that have to be swept.

The cost: a new collection has to be added to `collections_to_clean` in
`web/pets.py` and to `AUTHORED_COLLECTIONS` in `web/account_deletion.py`,
and the indexes have to be added to `ensure_indexes` in `web/db.py`.

### The reminders are a service of their own

`web` runs several gunicorn workers, and a thread inside it would send
every reminder once per worker.

The cost: the reminders live in their own container, and they read the
database rather than the API.

### The API is written once and runs twice

The same application answers on a phone and through the MCP server. The
MCP server publishes no port of its own, is reached at `/mcp` through
nginx, and takes no secrets: every request carries a personal token with
one of four scopes.

The cost: a change to the API reaches the assistants too, and the scopes
have to be kept in step with the routes.

### The rate limits are counted by address

The sign-in refuses the eleventh wrong password in a minute from one
address, and a correct password is not counted. Each login also counts
its own wrong passwords, and ten of them within fifteen minutes lock that
login for fifteen minutes.

The cost: the browser checks all come from one address, so one run spends
the hourly quota. The local stand resets the counters.

### The nginx on the host is not the nginx in the repository

The host nginx terminates TLS and proxies everything to
`127.0.0.1:3000`, where the nginx of the repository listens. The headers,
the real client address and `X-Forwarded-Proto` are fixed in
`nginx/nginx.conf`, and Flask trusts one proxy hop with `ProxyFix`.

The cost: the deploy user has no sudo, so the host nginx cannot be
changed from CI, and a change to the headers has to be made in the
repository.

## Boundaries

- `web/schemas.py` holds the request and response models, and the
  specification is assembled from them. A route that changes its shape
  changes the published reference with it.
- `web/errors.py` holds the error codes and their Russian texts. A route
  never writes an error message of its own.
- `web/decorators.py` holds the access checks. A route that touches a pet
  or a record uses the decorator and does not query the access itself.
- `web/storage.py` holds the object storage. The rest of the application
  deals with keys and never with a bucket.
- `web/db.py` holds the Mongo client and the indexes. The indexes have a
  test in `tests/stateful/test_indexes.py`.
- `frontend/src/services/` holds the calls to the API. A page calls a
  service and does not build a URL.
- `frontend/src/components/` holds the shared pieces. A screen uses them
  and does not write another one.
- `mcp/petzy_mcp/` calls the same API over HTTP and holds no rules of its
  own.
