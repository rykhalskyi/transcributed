import asyncio
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from transcributed.config import get_settings
from transcributed.db import SessionLocal
from transcributed.enums import TaskStatus
from transcributed.models import Task
from transcributed.worker.main import ProgressReporter, process_task, sync_database_url
from transcributed.worker.transcriber import FakeTranscriber


def _started_work(
    client: TestClient,
    paths: list[str],
) -> tuple[str, str, list[str]]:
    response = client.post(
        "/api/v1/projects",
        json={"name": "Workers", "defaults": {"language": "ru"}},
    )
    assert response.status_code == 201
    project_id = response.json()["id"]

    response = client.post(
        f"/api/v1/projects/{project_id}/items",
        json={"items": [{"path": path} for path in paths]},
    )
    assert response.status_code == 201

    response = client.post(f"/api/v1/projects/{project_id}/start")
    assert response.status_code == 202
    start = response.json()
    return project_id, start["run"]["id"], start["task_ids"]


def _mark_processing(task_id: str, pod: str, node: str) -> None:
    async def run() -> None:
        async with SessionLocal() as session:
            task = await session.get(Task, UUID(task_id))
            assert task is not None
            task.status = TaskStatus.PROCESSING
            task.started_at = datetime.now(UTC)
            task.worker_pod = pod
            task.worker_node = node
            task.progress = 42
            await session.commit()

    asyncio.run(run())


def test_workers_lists_processing_tasks_and_counts(
    client: TestClient,
    sample_videos: list[str],
) -> None:
    project_id, run_id, task_ids = _started_work(client, sample_videos)
    _mark_processing(task_ids[0], "worker-pod-1", "node-a")

    response = client.get("/api/v1/workers")
    assert response.status_code == 200
    body = response.json()
    assert body["active"] == 1
    assert body["queued"] == 1
    assert len(body["workers"]) == 1

    worker = body["workers"][0]
    assert worker["task_id"] == task_ids[0]
    assert worker["run_id"] == run_id
    assert worker["project_id"] == project_id
    assert worker["project_name"] == "Workers"
    assert worker["path"] == sample_videos[0]
    assert worker["status"] == "processing"
    assert worker["node"] == "node-a"
    assert worker["pod"] == "worker-pod-1"
    assert worker["progress"] == 42

    response = client.get("/api/v1/workers", params={"project_id": project_id})
    assert response.status_code == 200
    assert response.json()["active"] == 1

    response = client.get("/api/v1/workers", params={"run_id": run_id})
    assert response.status_code == 200
    assert response.json()["active"] == 1

    response = client.get(
        "/api/v1/workers",
        params={"project_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 200
    assert response.json() == {"active": 0, "queued": 0, "workers": []}


def test_cancelling_tasks_clears_workers(
    client: TestClient,
    sample_videos: list[str],
) -> None:
    _, _, task_ids = _started_work(client, sample_videos)
    _mark_processing(task_ids[0], "worker-pod-1", "node-a")

    for task_id in task_ids:
        response = client.post(f"/api/v1/tasks/{task_id}/cancel")
        assert response.status_code == 200

    response = client.get("/api/v1/workers")
    assert response.status_code == 200
    assert response.json() == {"active": 0, "queued": 0, "workers": []}


def test_worker_records_pod_and_node(
    client: TestClient,
    sample_video: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POD_NAME", "worker-pod-42")
    monkeypatch.setenv("NODE_NAME", "node-7")
    project_id, _, task_ids = _started_work(client, [sample_video])
    task_id = task_ids[0]

    async def run_worker() -> None:
        async with SessionLocal() as session:
            await process_task(session, UUID(task_id), transcriber=FakeTranscriber())

    asyncio.run(run_worker())

    response = client.get(f"/api/v1/tasks/{task_id}")
    assert response.status_code == 200
    task = response.json()
    assert task["worker_pod"] == "worker-pod-42"
    assert task["worker_node"] == "node-7"

    response = client.get(f"/api/v1/tasks/{task_id}/files/metadata")
    assert response.status_code == 200
    assert "worker-pod-42" in response.text
    assert "node-7" in response.text

    response = client.get(f"/api/v1/projects/{project_id}/items")
    assert response.status_code == 200
    item = response.json()[0]
    assert item["latest_task_status"] == "succeeded"
    assert item["latest_task_progress"] == 100


def test_progress_reporter_updates_task(
    client: TestClient,
    sample_video: str,
) -> None:
    _, _, task_ids = _started_work(client, [sample_video])
    task_id = UUID(task_ids[0])
    reporter = ProgressReporter(
        task_id,
        sync_database_url(get_settings().database_url),
    )
    try:
        reporter(10)
        reporter(10)
        reporter(55)
    finally:
        reporter.close()

    response = client.get(f"/api/v1/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json()["progress"] == 55
