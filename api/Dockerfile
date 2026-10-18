# syntax=docker/dockerfile:1

FROM python:3.14-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.12.24 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations


FROM base AS api

RUN uv sync --frozen --no-dev

USER app
EXPOSE 8000
CMD ["transcributed"]


FROM base AS worker

ARG WHISPER_MODEL=small

ENV WHISPER_MODEL=${WHISPER_MODEL}

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN uv sync --frozen --no-dev --extra worker

ENV WHISPER_MODEL_DIR=/models \
    WHISPER_LOCAL_FILES_ONLY=true \
    HF_HUB_DISABLE_TELEMETRY=1

RUN mkdir -p /models \
    && python -c "from faster_whisper import WhisperModel; WhisperModel('${WHISPER_MODEL}', device='cpu', compute_type='int8', download_root='/models')" \
    && chown -R app:app /models

USER app
CMD ["transcributed-worker"]
