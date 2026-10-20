# AGENTS.md — agent context for `petzy`

Petzy is a pet health diary: a Progressive Web App (React 18, Vite, antd-mobile, TypeScript) over a Flask and MongoDB backend. The interface is Russian. `README.md` lists what the app does, `PRODUCT.md` says who it is for and how it sounds, `DESIGN.md` is the design system. `AGENTS.md` and `CLAUDE.md` are the same file (`CLAUDE.md` is a symlink): edit `AGENTS.md`.

This file is what you need to work on the project without reading all of it.

## Run / build / test

Backend, from the repository root (the virtualenv is `.venv`):

```bash
.venv/bin/python -m pytest tests -q --no-cov       # the full suite, about 100 seconds
.venv/bin/python -m pytest tests -q --no-cov -n auto   # the same in parallel, about 25 seconds
.venv/bin/ruff check . && .venv/bin/ruff format .  # line length 120
```

Frontend, from `frontend/`:

```bash
npx tsc -b        # the real typecheck; `tsc --noEmit -p .` checks nothing here
npm run lint
npm test          # vitest: the app's own logic, the tests in frontend/tests/unit/
```

A local copy of the production stack (the same nginx, headers and build; the files go to a local S3, never to the real bucket), and then the demo data:

```bash
docker compose -p petzy-local -f docker-compose.yml -f docker-compose.local.yml up -d --build
.venv/bin/python scripts/seed_demo.py
```

The app is at http://localhost:3000. After any change to the interface or the backend, rebuild (`... up -d --build frontend web`), read the whole build output, and check that the container was really recreated: a failed build leaves the old one running, and the browser checks then pass against old code.

A second copy of the stack on port 3001 (`docker compose -p petzy-local-2`, with the variables at the top of `docker-compose.local.yml`, seeded by `.venv/bin/python scripts/seed_demo.py --base http://localhost:3001`) lets the browser checks run in two lines. The pre-push hook uses it when it answers, and runs one line when it does not.

Browser checks: `.venv/bin/python e2e/run.py [filter]` (Playwright, phone viewport). They need the local stand and are not part of `pytest` or CI.

The git hooks live in `.githooks/` (versioned) rather than in `.git/hooks/` (not versioned). Enable them once per clone:

```bash
git config core.hooksPath .githooks
```

- `pre-commit` runs `eslint` on the staged `frontend/**/*.{ts,tsx}` files and `ruff check` plus `ruff format --check` on the staged `*.py` files: fast, per-commit checks.
- `pre-push` runs `ruff check` plus `ruff format --check` over the whole backend, the full backend test suite (`pytest tests/`), a full frontend lint (`npm run lint`) and every browser check (`e2e/run.py`, about eight minutes in one line, about five in two). The suite and the lint run alongside the browser checks. It is slower, so it runs before a push only. The browser checks need the local stand: if it is down the push stops and the hook prints how to start it, because a push that silently went without them is worse than one that waited. To push once without them: `PETZY_SKIP_E2E=1 git push`, and that skip belongs in the commit message. Never `--no-verify`: fix the cause.

The backend code is formatted with `ruff format` (line length 120, in `pyproject.toml` and `.ruff.toml`). The hooks and the `Ruff` job in CI both enforce it.

## Where things live

| Path | What it holds |
| --- | --- |
| `web/` | The Flask app. One module per area (`pets.py`, `events.py`, `medications.py`, `medical_card*.py`, `medical_records.py`, `documents.py`, `medical_share.py`, `push*.py`, ...). The request and response models are in `web/schemas.py` (pydantic, served as OpenAPI at `/api/docs`); the error codes and their Russian texts are in `web/errors.py`. The medical card PDF is `web/medical_card_pdf.py` (fpdf2, DejaVu Sans in `web/fonts`). |
| `frontend/src/` | `pages/` (one file per screen), `components/` (the shared pieces), `hooks/`, `utils/`, `content/help.ts` (the help inside the app), `styles/globals.css` (the tokens), `sw.ts` (the service worker). |
| `frontend/vite.config.ts` | The dev server, and the `/api` proxy to `http://localhost:5001`. |
| `mcp/petzy_mcp/` | The MCP server for assistants: the API client, the tools, the HTTP app and the stdio mode. |
| `tests/stateless/` | The tests that need no database. |
| `tests/stateful/` | The tests with mongomock and moto for S3. |
| `tests/mcp/` | The tests of the MCP server, which import it by name (`pytest.ini` puts `mcp` on the path). |
| `e2e/` | The browser checks against a local stack, not part of `pytest` or CI (see `e2e/README.md`). |
| `scripts/` | The demo seeding, the reminders, the backups, the audits. |
| `nginx/` | The nginx of the app, and the one that runs in production. |
| `gunicorn.conf.py` | The web server's configuration in production: the worker class, the count, the threads, the recycling. |
| `.github/workflows/` | CI, the deployment and the service workflows. |
| `docs/ux/` | The audit of the user paths, one file per screen, with the routes and the findings. |
| `docs/qa/` | The QA checklist, ten documents. |

## Traps

- **The pre-push hook outlives the SSH connection.** Git opens the SSH connection **before** it runs `pre-push`, so a hook that takes eight minutes leaves the connection idle and it dies. The push then ends with code 141 (SIGPIPE), no error and no ref update, after the hook has already printed `ALL PASS`, which is what makes it look like the push worked. Keep the connection alive once per clone: `git config core.sshCommand "ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=80"`.
- **A failed build leaves the old container running.** Rebuild with `... up -d --build frontend web`, read the whole output and check the container was recreated. Otherwise the browser checks pass against the old code and report a green run for a change that never reached the stand.
- **`tsc --noEmit -p .` checks nothing here.** The real typecheck is `npx tsc -b`.
- **Node ships its own inert `localStorage`, which shadows the page's.** A test that touches it takes `window._localStorage` first.
- **jsdom gives every element zero size.** A test of an open layer has to stub `getClientRects`.
- **Chrome cannot draw HEIC.** Anything that previews a picked file goes through `utils/drawableImage.ts`, which asks `POST /api/images/preview` for a WebP and stores nothing.
- **Multipart form values stay text** (`keep_form_text_as_text()` in `web/pydantic_helpers.py`): a pet named "7" or a document titled "2025" must not be read as a number.
- **The reminders service is a service of its own on purpose.** `web` runs several gunicorn worker processes (see `gunicorn.conf.py`), and a thread inside it would send every reminder once per worker.
- **`nginx/nginx.conf.server` is not what runs on the host.** The host nginx terminates TLS and proxies everything to `127.0.0.1:3000`, where the Docker nginx listens. The headers, the real client address and `X-Forwarded-Proto` are fixed in `nginx/nginx.conf`. Flask trusts one proxy hop (`ProxyFix(x_for=1)`). The deploy user has no sudo, so the host nginx cannot be changed from CI.
- **The rate limits are counted by client address.** The sign-in refuses the eleventh wrong password in a minute from one address, and a correct password is not counted. Each login counts its own wrong passwords on top of that: ten of them within fifteen minutes lock that login for fifteen minutes, and while it is locked even the right password gets the answer a wrong one gets. The browser checks all come from the same address, so one run spends the hourly quota; the checks reset the counters through `POST /api/dev/reset-limits`, which exists only on the local stand.
- **setuptools is pinned to 81.** Version 82 dropped `pkg_resources`, which mongomock imports (the tests and `scripts/dev_local.py`).
- **Dates and times travel as the person sees them** (`YYYY-MM-DD`, `HH:MM`), never through `toISOString()`, which is UTC. A record keeps the time zone it was typed in.
- **The demo data belongs to a person.** Do not alter what was made by hand, and delete anything throwaway a test created. The checks make their own pet "Тест-М" or read the demo pet "Рекс", and clean up after themselves.
- **The UI text is Russian, and the help names the labels exactly as they are on screen.** Keep the wording of a label exactly as it is shown.

## Style / safety rails

- **Never add an AI-attribution trailer** (`Co-Authored-By: Claude ...` or the like) to a commit message or a pull request description. Commits and pull requests here are attributed only to the human author (aa-blinov): no mention of Claude, Anthropic or any AI assistant in the git history.
- **Work in `master`:** no feature branches, no pull requests. Commit locally as each piece is done.
- **Push only when the owner says so.** Every push to `master` runs CI and deploys to production (GitHub Actions: `CI` and `Deploy to Server`), which is slow and costs money, so changes are batched. After a push, check both runs with `gh run list --branch master`.
- **Never skip the hooks (`--no-verify`) to get past a failure:** fix the cause.
- **The repository and its CI logs are public:** no secrets, tokens or personal data in the code, the commits or the output.
- **No "·" (or any other glyph) joining two facts.** Put them side by side with the layout (`gap`) or with a comma.
- **No long dash "—" or "–" outside number ranges:** use a comma, a colon, a full stop or a rephrase.
- **A line of the interface (a toast, a hint, a note, a dialog, an empty state) ends without a period**, while the sentences inside the line keep theirs. Abbreviations («шт.») and ellipses stay. Reading text (the help in `content/help.ts`, the privacy text), the PDF and the emails are documents and keep ordinary punctuation.
- **Before committing work on the interface, grep `·` in `frontend/src`.**
- **Gaps come from the `--spacing-*` tokens**, one value per kind of gap (stacked buttons 12px, list items 12px, a section header to its content 8px, the fields to the closing button 24px, and so on): the table is under "Spacing rules" in `DESIGN.md`. Use `.form-actions` or `.form-sticky-action` for the buttons that close a form instead of setting margins by hand. The type sizes come from `--text-*`, and the smallest touch target is `--touch-min` (44px).
- **Reuse the shared pieces instead of writing another:** `Fab` and `useFabAway` for the round "+", `DraggableSheetBody` for the sheets, `DatePickerField`, `SpinnerButton`, `FieldNote`, `ChoiceChips`, `SwipeableRow` with `deferredDelete` and `undo` for a delete with an undo.
- **Forms use react-hook-form with zod**, `useUnsavedChangesGuard` for the question about unsaved changes, and Enter moves between the fields (`utils/enterKey.ts`).
- **The antd-mobile parts get their accessibility fixes in `utils/antdA11y.ts`**; check a new popup or dialog against it.
- **Every route that touches a pet checks the access** (`require_pet_access`), and a record of a pet checks `require_record_access`. Pet cleanup and account deletion keep lists that have to be extended when a new collection appears (`collections_to_clean` in `web/pets.py`, `AUTHORED_COLLECTIONS` in `web/account_deletion.py`), and the indexes live in `ensure_indexes` in `web/db.py`, with a test in `tests/stateful/test_indexes.py`.
- **A name, a title or a label is one line:** line breaks and runs of spaces inside become one space.
- **Images are converted to WebP at the upload** (`optimize_image`, HEIC through `pillow-heif`).
- **New behaviour comes with a test, and a test for a rule should fail when the rule is removed.**
- **Do not create accounts or enter credentials on production.**

## Production

The request path is the host nginx (TLS), then the Docker nginx on `127.0.0.1:3000` (`nginx/nginx.conf` and `nginx/security-headers.conf`, rebuilt on every deploy), then gunicorn.

The deploy frees the disk first (fresh builds left old images and the build cache behind until MongoDB stopped writing), then pulls, writes the secrets into the server's `.env`, rebuilds and restarts the stack. It runs one at a time, and it can be started by hand with `gh workflow run "Deploy to Server"`.

## Where the product truth lives

`PRODUCT.md` holds it. Read it before changing the behaviour of the app, and write the change there when the behaviour changes.
