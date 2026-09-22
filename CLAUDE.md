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

- `pre-commit` runs `eslint` on staged `frontend/**/*.{ts,tsx}` files and `ruff`
  on staged `*.py` files — fast, per-commit checks. Blocks the commit on any
  error (skip with `git commit --no-verify` if truly needed).
- `pre-push` runs the full backend test suite (`pytest tests/`). Slower
  (~45s), so it only runs before push rather than every commit. Blocks the
  push on any failure (skip with `git push --no-verify` if truly needed).
