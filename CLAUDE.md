# Working in this repo

- Never add a `Co-Authored-By: Claude ...` (or similar AI-attribution) trailer to
  git commit messages or pull request descriptions. Commits and PRs in this repo
  are attributed only to the human author (aa-blinov) — no mentions of Claude,
  Anthropic, or any AI assistant in git history.

## Git hooks

Hooks live in `.githooks/` (versioned) rather than `.git/hooks/` (not versioned).
Enable them once per clone:

```bash
git config core.hooksPath .githooks
```

- `pre-commit` runs `eslint` on staged `frontend/**/*.{ts,tsx}` files and
  `ruff check` + `ruff format --check` on staged `*.py` files — fast,
  per-commit checks. Blocks the commit on any error (skip with
  `git commit --no-verify` if truly needed).
- `pre-push` runs `ruff check` + `ruff format --check` over the whole
  backend, the full backend test suite (`pytest tests/`), and a full
  frontend lint (`npm run lint`, all files, not just staged ones). Slower
  (~45s), so it only runs before push rather than every commit. Blocks the
  push on any failure (skip with `git push --no-verify` if truly needed).

Backend code is formatted with `ruff format` (line length 120, see
`pyproject.toml`). Both the hooks above and CI's `Ruff` job enforce it —
run `ruff format .` locally if either one complains.
