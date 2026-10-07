# Working in this repo

Petzy is a pet health diary: a PWA (React 18, Vite, antd-mobile, TypeScript) on a Flask + MongoDB
backend. The interface is Russian. `README.md` lists what the app does, `PRODUCT.md` says who it is
for and how it sounds, `DESIGN.md` is the design system. `AGENTS.md` and `CLAUDE.md` are the same
file (`CLAUDE.md` is a symlink): edit `AGENTS.md`.

## Rules for the history

- Never add a `Co-Authored-By: Claude ...` (or similar AI-attribution) trailer to git commit
  messages or pull request descriptions. Commits and PRs here are attributed only to the human
  author (aa-blinov): no mentions of Claude, Anthropic, or any AI assistant in git history.
- Work in `master`: no feature branches, no pull requests. Commit locally as each piece is done.
- Push only when the owner says so. Every push to `master` runs CI and deploys to production
  (GitHub Actions: `CI` and `Deploy to Server`), which is slow and costs money, so changes are
  batched. After a push, check both runs with `gh run list --branch master`.
- Never skip hooks (`--no-verify`) to get past a failure: fix the cause.
- The repo and its CI logs are public: no secrets, tokens or personal data in code, commits or output.

## Layout

- `web/`: Flask app. One module per area (`pets.py`, `events.py`, `medications.py`,
  `medical_card*.py`, `medical_records.py`, `documents.py`, `medical_share.py`, `push*.py`, ...).
  Request and response models are in `web/schemas.py` (pydantic, served as OpenAPI at `/api/docs`);
  error codes and their Russian texts are in `web/errors.py`. The medical card PDF is
  `web/medical_card_pdf.py` (fpdf2, DejaVu Sans in `web/fonts`).
- `frontend/src/`: `pages/` (one file per screen), `components/` (shared pieces), `hooks/`,
  `utils/`, `content/help.ts` (the in-app FAQ), `styles/globals.css` (tokens), `sw.ts` (service worker).
- `tests/stateless/` (no database) and `tests/stateful/` (mongomock, moto S3).
- `e2e/`: browser checks against a local stack, not part of `pytest` or CI (see `e2e/README.md`).
- `scripts/`: demo seeding, reminders, backups, audits. `nginx/`: the Docker nginx that runs on production.

## Running things

Backend, from the repo root (the virtualenv is `.venv`):

```bash
.venv/bin/python -m pytest tests -q --no-cov       # full suite, about 100 seconds
.venv/bin/python -m pytest tests -q --no-cov -n auto   # the same in parallel, about 25 seconds
.venv/bin/ruff check . && .venv/bin/ruff format .  # line length 120
```

Frontend, from `frontend/`:

```bash
npx tsc -b        # the real typecheck; `tsc --noEmit -p .` checks nothing here
npm run lint
```

Local copy of the production stack (same nginx, headers and build; files go to a local S3, never
to the real bucket), then demo data:

```bash
docker compose -p petzy-local -f docker-compose.yml -f docker-compose.local.yml up -d --build
.venv/bin/python scripts/seed_demo.py
```

The app is at http://localhost:3000. After any UI or backend change rebuild
(`... up -d --build frontend web`), read the whole build output, and check the container was
really recreated: a failed build leaves the old one running and the browser checks then pass
against old code.

Browser checks: `.venv/bin/python e2e/run.py [filter]` (Playwright, phone viewport). The demo
login allows 5 attempts a minute, so use one login per script. The checks create their own
test pet «Тест-М» or read the demo pet «Рекс», and clean up after themselves. Do not alter the
demo data a person made by hand, and delete any throwaway data a test created.

## Git hooks

Hooks live in `.githooks/` (versioned) rather than `.git/hooks/` (not versioned).
Enable them once per clone:

```bash
git config core.hooksPath .githooks
```

- `pre-commit` runs `eslint` on staged `frontend/**/*.{ts,tsx}` files and
  `ruff check` + `ruff format --check` on staged `*.py` files: fast, per-commit checks.
- `pre-push` runs `ruff check` + `ruff format --check` over the whole backend, the full backend
  test suite (`pytest tests/`), a full frontend lint (`npm run lint`) and every browser check
  (`e2e/run.py`, all 43, about ten minutes). Slower, so it runs before push only. The browser
  checks need the local stand: if it is down the push stops and the hook prints how to start it,
  because a push that silently went without them is worse than one that waited. To push once
  without them: `PETZY_SKIP_E2E=1 git push`, and that skip belongs in the commit message. Never
  `--no-verify`: fix the cause.
- Git opens the SSH connection **before** it runs `pre-push`, so a hook this long leaves the
  connection idle for many minutes and it dies: the push then ends with code 141 (SIGPIPE),
  no error and no ref update. The hook had already printed `ALL PASS`, which is what makes it
  look like the push worked. Keep the connection alive once per clone:
  `git config core.sshCommand "ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=80"`.

Backend code is formatted with `ruff format` (line length 120, see `pyproject.toml`); the hooks
and CI's `Ruff` job both enforce it.

## Interface text

Russian, calm and direct (see `PRODUCT.md`). The owner has confirmed these rules:

- No « · » (or any glyph) joining two facts. Put them side by side with layout (`gap`) or a comma.
- No long dash «—» or «–» outside number ranges: a comma, colon, full stop or a rephrase.
- A line of UI (toast, hint, note, dialog, empty state) ends without a period; sentences inside
  the line keep theirs. Abbreviations («шт.») and ellipses stay. Reading text (the FAQ in
  `content/help.ts`, privacy text), the PDF and the emails are documents and keep ordinary punctuation.
- Before committing UI work, grep `·` in `frontend/src`.

## Frontend conventions

- Gaps between blocks come from the `--spacing-*` tokens, one value per kind of gap (stacked
  buttons 12px, list items 12px, section header to content 8px, fields to the closing button
  24px, and so on): the table is under «Spacing rules» in `DESIGN.md`. Use `.form-actions` or
  `.form-sticky-action` for the buttons that close a form instead of hand-set margins. Type sizes
  come from `--text-*`, the minimum touch target is `--touch-min` (44px).
- Reuse the shared pieces instead of writing another: `Fab` and `useFabAway` for the round «+»,
  `DraggableSheetBody` for sheets, `DatePickerField`, `SpinnerButton`, `FieldNote`, `ChoiceChips`,
  `SwipeableRow` with `deferredDelete`/`undo` for delete-with-undo.
- Forms: react-hook-form with zod, `useUnsavedChangesGuard` for the unsaved-changes question,
  Enter moves between fields (`utils/enterKey.ts`).
- antd-mobile parts get their accessibility fixes in `utils/antdA11y.ts`; check a new
  popup or dialog against it.
- HEIC from a phone: Chrome cannot draw it. Anything that previews a picked file goes through
  `utils/drawableImage.ts` (it asks `POST /api/images/preview` for a WebP and stores nothing).

## Backend conventions

- Every route that touches a pet checks access (`require_pet_access`); records of a pet check
  `require_record_access`. Pet cleanup and account deletion have lists to extend when a new
  collection appears (`collections_to_clean` in `web/pets.py`, `AUTHORED_COLLECTIONS` in
  `web/account_deletion.py`), and indexes live in `ensure_indexes` in `web/db.py` with a test
  in `tests/stateful/test_indexes.py`.
- Multipart form values stay text (`keep_form_text_as_text()` in `web/pydantic_helpers.py`): a
  pet named «7» or a document titled «2025» must not be read as a number.
- A name, title or label is one line: line breaks and runs of spaces inside become one space.
- Images are converted to WebP at upload (`optimize_image`, HEIC through `pillow-heif`).
- New behaviour comes with a test, and a test for a rule should fail when the rule is removed.

## Production

The request path is host nginx (TLS) → Docker nginx on `127.0.0.1:3000` (`nginx/nginx.conf` and
`nginx/security-headers.conf`, rebuilt on every deploy) → gunicorn. Fix headers, the real client
address and `X-Forwarded-Proto` in `nginx/nginx.conf`: `nginx/nginx.conf.server` is not what runs
on the host. Flask trusts one proxy hop (`ProxyFix(x_for=1)`). The deploy user has no sudo, so
the host nginx cannot be changed from CI. Do not create accounts or enter credentials on production.
