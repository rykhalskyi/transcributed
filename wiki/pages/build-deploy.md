---
created: 2026-10-17
type: build-deploy
summary: Build, test, lint, and deploy commands for the project.
---

# Build & Deploy

No build system is configured yet (no `pyproject.toml`, `setup.py`, `requirements.txt`,
`Makefile`, or CI config).

## Build

Not defined.

## Test

Not defined. `.gitignore` anticipates pytest (`.pytest_cache/`), so once tests exist:

```bash
pytest
```

## Lint / typecheck

Not defined. `.gitignore` anticipates ruff (`.ruff_cache/`) and mypy (`.mypy_cache/`):

```bash
ruff check .
mypy .
```

## Deploy

Not defined.

## Wiki maintenance

Node.js is required. Run from the project root:

```bash
node scripts/wiki.mjs index     # regenerate wiki/index.md
node scripts/wiki.mjs lint      # check frontmatter and links
node scripts/wiki.mjs log <action> "<description>"
node scripts/wiki.mjs decision "<decision> — because <reason>"
```

Equivalent npm script (requires `npm run` from project root): `npm run wiki -- index`.
