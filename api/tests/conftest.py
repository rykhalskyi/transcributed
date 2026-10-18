import asyncio
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

TEST_DB = "transcributed_test"
ADMIN_URL = "postgresql://transcributed:transcributed@localhost:5432/postgres"
TEST_DATABASE_URL = (
    "postgresql+psycopg://transcributed:transcributed@localhost:5432/transcributed_test"
)
TEST_ROOT = Path(tempfile.mkdtemp(prefix="transcributed-tests-"))

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["RABBITMQ_ENABLED"] = "false"
os.environ["NAS_INPUT_ROOT"] = str(TEST_ROOT / "samples")
os.environ["LOG_LEVEL"] = "WARNING"

(TEST_ROOT / "samples").mkdir(parents=True, exist_ok=True)

with psycopg.connect(ADMIN_URL, autocommit=True) as connection:
    exists = connection.execute(
        "SELECT 1 FROM pg_database WHERE datname = %s",
        (TEST_DB,),
    ).fetchone()
    if not exists:
        connection.execute(f'CREATE DATABASE "{TEST_DB}"')

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from transcributed.api.app import app  # noqa: E402
from transcributed.db import engine  # noqa: E402
from transcributed.models import Base  # noqa: E402


async def _reset_schema() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)


async def _truncate() -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE artifacts, tasks, runs, project_items, projects, videos "
                "RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture(scope="session", autouse=True)
def database_schema() -> Iterator[None]:
    asyncio.run(_reset_schema())
    yield


@pytest.fixture(autouse=True)
def clean_database() -> Iterator[None]:
    asyncio.run(_truncate())
    yield


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_video() -> str:
    path = TEST_ROOT / "samples" / "lecture-01.mp4"
    path.write_bytes(b"fake video content")
    return "lecture-01.mp4"
