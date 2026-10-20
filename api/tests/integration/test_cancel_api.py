import asyncio
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from fastapi.testclient import TestClient

from transcributed.config import get_settings
from transcributed.db import SessionLocal
from transcributed.worker.main import TaskDisposition, process_task, sync_database_url
from transcributed.worker.transcriber import FakeTranscriber, TaskCancelled

DSN = sync_database_url(get_settings().database_url)


def _create_project(client: TestClient, **defaults: Any) -> str:
    payload: dict[str, Any] = {"name": "Cancel test"}
    if defaults:
        payload["defaults"] = defaults
    response = client.post("/api/v1/projects", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def _add_items(client: TestClient, project_id: str, paths: list[str]) -> None:
    response = client.post(
        f"/api/v1/projects/{project_id}/items",
        json={"items": [{"path": path} for path in paths]},
    )
    assert response.status_code == 201
    assert response.json()["accepted"] == len(paths)


def _start(client: TestClient, project_id: str) -> dict[str, Any]:
    response = client.post(f"/api/v1/projects/{project_id}/start")
    assert response.status_code == 202
    return response.json()


def _process(task_id: str, transcriber: Any | None = None) -> TaskDisposition:
    selected = transcriber if transcriber is not None else FakeTranscriber()

    async def run() -> TaskDisposition:
        async with SessionLocal() as session:
            outcome = await process_task(session, UUID(task_id), transcriber=selected)
            return outcome.disposition

    return asyncio.run(run())


def test_cancel_queued_task(client: TestClient, sample_video: str) -> None:
    project_id = _create_project(client)
    _add_items(client, project_id, [sample_video])
    start = _start(client, project_id)
    task_id = start["task_ids"][0]

    response = client.post(f"/api/v1/tasks/{task_id}/cancel")

    assert response.status_code == 200
    task = response.json()
    assert task["status"] == "cancelled"
    assert task["error"] == "cancelled by user"

    assert client.get(f"/api/v1/runs/{start['run']['id']}").json()["status"] == "cancelled"
    assert client.get(f"/api/v1/projects/{project_id}").json()["status"] == "cancelled"
    assert client.post(f"/api/v1/projects/{project_id}/start").status_code == 202


def test_cancel_run_cancels_all_tasks(
    client: TestClient,
    sample_videos: list[str],
) -> None:
    project_id = _create_project(client)
    _add_items(client, project_id, sample_videos)
    start = _start(client, project_id)

    response = client.post(f"/api/v1/runs/{start['run']['id']}/cancel")

    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "cancelled"
    assert {task["status"] for task in run["tasks"]} == {"cancelled"}
    assert client.get(f"/api/v1/projects/{project_id}").json()["status"] == "cancelled"


def test_cancel_finished_task_returns_conflict(
    client: TestClient,
    sample_video: str,
) -> None:
    project_id = _create_project(client)
    _add_items(client, project_id, [sample_video])
    task_id = _start(client, project_id)["task_ids"][0]
    assert _process(task_id) == TaskDisposition.SUCCEEDED

    response = client.post(f"/api/v1/tasks/{task_id}/cancel")

    assert response.status_code == 409


def test_cancelled_task_is_not_processed(
    client: TestClient,
    sample_video: str,
) -> None:
    project_id = _create_project(client)
    _add_items(client, project_id, [sample_video])
    task_id = _start(client, project_id)["task_ids"][0]
    assert client.post(f"/api/v1/tasks/{task_id}/cancel").status_code == 200

    assert _process(task_id) == TaskDisposition.NOOP
    task = client.get(f"/api/v1/tasks/{task_id}").json()
    assert task["status"] == "cancelled"
    assert task["artifacts"] == []


class CancellingTranscriber:
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id

    def transcribe(
        self,
        input_path: Path,
        spec: dict[str, Any],
        *,
        should_cancel: Any | None = None,
        on_progress: Any | None = None,
    ) -> dict[str, str]:
        with psycopg.connect(DSN, autocommit=True) as connection:
            connection.execute(
                "UPDATE tasks SET status = 'cancelled' WHERE id = %s",
                (self.task_id,),
            )
        if should_cancel is not None and should_cancel():
            raise TaskCancelled("cancelled by user")
        return {"txt": "should not be stored\n"}


def test_worker_stops_when_task_is_cancelled_mid_processing(
    client: TestClient,
    sample_video: str,
) -> None:
    project_id = _create_project(client)
    _add_items(client, project_id, [sample_video])
    start = _start(client, project_id)
    task_id = start["task_ids"][0]

    disposition = _process(task_id, CancellingTranscriber(task_id))

    assert disposition == TaskDisposition.CANCELLED
    task = client.get(f"/api/v1/tasks/{task_id}").json()
    assert task["status"] == "cancelled"
    assert task["artifacts"] == []
    assert client.get(f"/api/v1/runs/{start['run']['id']}").json()["status"] == "cancelled"


def test_cancel_unknown_task_returns_not_found(client: TestClient) -> None:
    response = client.post("/api/v1/tasks/00000000-0000-0000-0000-000000000000/cancel")
    assert response.status_code == 404
