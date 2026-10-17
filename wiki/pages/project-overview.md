---
created: 2026-10-17
type: overview
summary: Project purpose, tech stack, folder layout, and key concepts.
---

# Project Overview

**Transcributed** — repository initialized with an MIT license (© 2026 rykhalskyi).
No application source code exists yet; the project is at the scaffolding stage.

## Tech stack

- **Language:** Python (inferred from `.gitignore`, which covers `__pycache__`, `*.py[codz]`,
  virtualenvs, pytest, mypy, and ruff caches).
- **Tooling expectations:** pytest, mypy, ruff, and one of uv/poetry/pipenv for dependency
  management (per the `.gitignore` entries). None are configured yet.
- **Wiki tooling:** Node.js runs `scripts/wiki.mjs` to maintain this wiki.

## Architecture

The first control-plane slice is specified in the
[control-plane spec](specs/control-plane.md): users explicitly add NAS lecture
files to a project, start a run, and one task per lecture is queued. No
application code exists yet.

## Folder structure

```
.
├── .gitignore          # Python-oriented ignore rules
├── LICENSE             # MIT
├── scripts/
│   └── wiki.mjs        # wiki maintenance helper
└── wiki/               # this knowledge base
    ├── AGENTS.md
    ├── SCHEMA.md
    ├── index.md
    ├── log.md
    ├── decisions.md
    └── pages/
```

## Key concepts

- **Project:** a named, user-selected list of lectures.
- **Run:** one explicit execution of a project.
- **Task:** one lecture processed by one worker Job.
- **Artifact:** a transcript file on the NAS, indexed in PostgreSQL.

## Open questions

- Which Python version and dependency manager will be used?
- See the [control-plane spec](specs/control-plane.md) for domain-model questions.
