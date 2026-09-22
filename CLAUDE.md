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

`pre-commit` runs `eslint` on staged `frontend/**/*.{ts,tsx}` files and blocks
the commit on any error (skip with `git commit --no-verify` if truly needed).
