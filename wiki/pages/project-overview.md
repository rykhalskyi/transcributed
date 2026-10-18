---
created: 2026-10-17
type: overview
summary: Project purpose, tech stack, folder layout, and key concepts.
---

# Project Overview

**Transcributed** — self-hosted lecture transcription control plane (MIT license,
© 2026 rykhalskyi).

## Tech stack

- **Language:** Python 3.14, managed with `uv`.
- **API:** FastAPI, SQLAlchemy (async), Alembic, Pydantic.
- **Data:** PostgreSQL/CloudNativePG for control-plane state and plain-text
  transcripts; RabbitMQ for task messages.
- **Tooling:** pytest, ruff, mypy.
- **Wiki tooling:** Node.js runs `scripts/wiki.mjs` to maintain this wiki.

## Architecture

The first control-plane slice is specified in the
[control-plane spec](specs/control-plane.md): users explicitly add NAS lecture
files to a project, start a run, and one task per lecture is queued. The NAS is
read-only input; plain-text transcripts are stored in PostgreSQL and downloaded
through the API.

## Folder structure

```
.
├── VERSION             # single version source for release/CI checks
├── api/                # FastAPI control plane, worker, migrations, tests
├── charts/
│   └── transcributed/  # Helm chart (API, KEDA ScaledJob, migration hook)
├── .github/workflows/  # image and chart release pipelines
├── docker-compose.dev.yml
├── scripts/
│   ├── version.py      # bump/check every version field
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
- **Artifact:** a transcript stored as text in PostgreSQL and downloaded through the API.

## Open questions

- See the [control-plane spec](specs/control-plane.md) for domain-model questions.
