# Transcributed API

FastAPI control plane and worker for the Transcributed lecture transcription system.

## Requirements

- Python 3.14 and `uv`
- PostgreSQL 16
- RabbitMQ 3.13 (optional for local API-only work)

## Local setup

```bash
cd api
cp .env.example .env
uv sync

# Starts PostgreSQL and RabbitMQ
docker compose -f ../docker-compose.dev.yml up -d

# Apply the schema
uv run alembic upgrade head
```

Run the API:

```bash
uv run transcributed
```

Run one worker iteration (one message, or exit when the queue is empty):

```bash
uv run transcributed-worker
```

## Tests

Tests use the `transcributed_test` database and apply the real Alembic migrations:

```bash
docker compose -f ../docker-compose.dev.yml up -d postgres
uv run pytest
uv run ruff check .
uv run mypy src tests
```

## Behaviour notes

- `NAS_INPUT_ROOT` must contain the lecture files referenced by NAS-relative paths.
  The default `./samples` directory is ignored by git.
- A project is a living list: it can be edited and restarted whenever no run is
  `queued` or `running`. Every start creates a new run snapshot.
- When `RABBITMQ_ENABLED=true`, starting a project requires a reachable broker.
  If the broker is unavailable or a publish fails, the API returns `503` and removes
  the newly created run and tasks.
- `RABBITMQ_ENABLED=false` is an explicit development mode: starts succeed without
  publishing and report `not_enqueued` in the response.
- Failed tasks are retried through `transcription.retry.1m` and
  `transcription.retry.10m` up to `max_attempts`; terminal failures are routed to
  the `transcription.dead` queue.
- Cancel a task with `POST /api/v1/tasks/{id}/cancel` or a whole run with
  `POST /api/v1/runs/{id}/cancel`. Cancelling marks non-terminal tasks `cancelled`,
  discards any in-progress output, and unlocks the project for a new run. Workers
  check the task status about every 30 seconds of audio and stop cooperatively.
