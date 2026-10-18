import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient

from transcributed.api.app import app
from transcributed.api.deps import get_publisher
from transcributed.db import SessionLocal
from transcributed.worker.main import TaskDisposition, TaskOutcome, process_task
from transcributed.worker.transcriber import FakeTranscriber


class FakePublisher:
    enabled = True

    def __init__(
        self,
        ensure_ready: bool = True,
        fail_on_call: int | None = None,
    ) -> None:
        self.ensure_ready = ensure_ready
        self.fail_on_call = fail_on_call
        self.published: list[tuple[UUID, UUID]] = []

    async def ensure_connected(self) -> bool:
        return self.ensure_ready

    async def publish_task(self, task_id: UUID, run_id: UUID) -> bool:
        self.published.append((task_id, run_id))
        failing = self.fail_on_call is not None and len(self.published) >= self.fail_on_call
        return not failing


class AlwaysFailTranscriber:
    def transcribe(
        self,
        input_path: Path,
        spec: dict[str, Any],
        *,
        should_cancel: Any | None = None,
    ) -> dict[str, str]:
        raise RuntimeError("transcription failed")


@contextmanager
def publisher_override(publisher: FakePublisher) -> Iterator[None]:
    app.dependency_overrides[get_publisher] = lambda: publisher
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_publisher, None)


def _process(task_id: str, transcriber: Any | None = None) -> TaskOutcome:
    selected = transcriber if transcriber is not None else FakeTranscriber()

    async def run() -> TaskOutcome:
        async with SessionLocal() as session:
            return await process_task(session, UUID(task_id), transcriber=selected)

    return asyncio.run(run())


def _create_project(client: TestClient, **defaults: Any) -> str:
    payload: dict[str, Any] = {"name": "Lectures"}
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


def test_invalid_model_is_rejected_at_the_edge(client: TestClient) -> None:
    response = client.post(
        "/api/v1/projects",
        json={"name": "Bad model", "defaults": {"model": "gpt"}},
    )
    assert response.status_code == 422

    project_id = _create_project(client)
    response = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"defaults": {"model": "gpt"}},
    )
    assert response.status_code == 422


def test_batch_size_limit_returns_validation_error(
    client: TestClient,
    sample_video: str,
) -> None:
    project_id = _create_project(client)
    response = client.post(
        f"/api/v1/projects/{project_id}/items",
        json={"items": [{"path": sample_video}] * 501},
    )
    assert response.status_code == 422


def test_publish_failure_returns_503_and_removes_the_run(
    client: TestClient,
    sample_videos: list[str],
) -> None:
    project_id = _create_project(client)
    _add_items(client, project_id, sample_videos)

    publisher = FakePublisher(fail_on_call=1)
    with publisher_override(publisher):
        response = client.post(f"/api/v1/projects/{project_id}/start")

    assert response.status_code == 503
    assert client.get(f"/api/v1/projects/{project_id}/runs").json() == []
    project = client.get(f"/api/v1/projects/{project_id}").json()
    assert project["status"] == "draft"


def test_unavailable_queue_returns_503_before_creating_a_run(
    client: TestClient,
    sample_video: str,
) -> None:
    project_id = _create_project(client)
    _add_items(client, project_id, [sample_video])

    publisher = FakePublisher(ensure_ready=False)
    with publisher_override(publisher):
        response = client.post(f"/api/v1/projects/{project_id}/start")

    assert response.status_code == 503
    assert publisher.published == []
    assert client.get(f"/api/v1/projects/{project_id}/runs").json() == []


def test_enqueue_success_sets_enqueued_at(
    client: TestClient,
    sample_videos: list[str],
) -> None:
    project_id = _create_project(client)
    _add_items(client, project_id, sample_videos)

    publisher = FakePublisher()
    with publisher_override(publisher):
        response = client.post(f"/api/v1/projects/{project_id}/start")

    assert response.status_code == 202
    body = response.json()
    assert body["enqueued"] == 2
    assert body["not_enqueued"] == 0

    for task_id in body["task_ids"]:
        task = client.get(f"/api/v1/tasks/{task_id}").json()
        assert task["enqueued_at"] is not None


def test_project_is_editable_between_runs(
    client: TestClient,
    sample_videos: list[str],
) -> None:
    project_id = _create_project(client)
    _add_items(client, project_id, sample_videos)

    start = client.post(f"/api/v1/projects/{project_id}/start")
    assert start.status_code == 202
    task_ids = start.json()["task_ids"]

    item_id = client.get(f"/api/v1/projects/{project_id}/items").json()[0]["id"]

    assert client.patch(f"/api/v1/projects/{project_id}", json={"name": "X"}).status_code == 409
    assert (
        client.patch(
            f"/api/v1/projects/{project_id}/items/{item_id}",
            json={"included": False},
        ).status_code
        == 409
    )
    assert client.delete(f"/api/v1/projects/{project_id}/items/{item_id}").status_code == 409
    assert client.delete(f"/api/v1/projects/{project_id}").status_code == 409

    for task_id in task_ids:
        assert _process(task_id).disposition == TaskDisposition.SUCCEEDED

    assert client.get(f"/api/v1/projects/{project_id}").json()["status"] == "completed"

    response = client.patch(f"/api/v1/projects/{project_id}", json={"name": "Renamed"})
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"

    items = client.get(f"/api/v1/projects/{project_id}/items").json()
    item_id = items[0]["id"]
    response = client.patch(
        f"/api/v1/projects/{project_id}/items/{item_id}",
        json={"included": False},
    )
    assert response.status_code == 200
    assert response.json()["included"] is False

    assert client.delete(f"/api/v1/projects/{project_id}/items/{items[1]['id']}").status_code == 204

    assert client.post(f"/api/v1/projects/{project_id}/start").status_code == 409

    response = client.patch(
        f"/api/v1/projects/{project_id}/items/{item_id}",
        json={"included": True},
    )
    assert response.status_code == 200

    second_start = client.post(f"/api/v1/projects/{project_id}/start")
    assert second_start.status_code == 202
    assert len(second_start.json()["task_ids"]) == 1
    assert len(client.get(f"/api/v1/projects/{project_id}/runs").json()) == 2


def test_failed_task_retries_then_fails(
    client: TestClient,
    sample_video: str,
) -> None:
    project_id = _create_project(client, max_attempts=2)
    _add_items(client, project_id, [sample_video])

    start = client.post(f"/api/v1/projects/{project_id}/start")
    assert start.status_code == 202
    task_id = start.json()["task_ids"][0]

    first = _process(task_id, AlwaysFailTranscriber())
    assert first.disposition == TaskDisposition.RETRY
    assert first.retry_routing_key == "transcription.retry.1m"

    task = client.get(f"/api/v1/tasks/{task_id}").json()
    assert task["status"] == "queued"
    assert task["attempts"] == 1
    assert "transcription failed" in task["error"]
    assert client.get(f"/api/v1/runs/{start.json()['run']['id']}").json()["status"] == "queued"

    second = _process(task_id, AlwaysFailTranscriber())
    assert second.disposition == TaskDisposition.FAILED

    task = client.get(f"/api/v1/tasks/{task_id}").json()
    assert task["status"] == "failed"
    assert task["attempts"] == 2
    assert client.get(f"/api/v1/runs/{start.json()['run']['id']}").json()["status"] == "failed"
    assert client.get(f"/api/v1/projects/{project_id}").json()["status"] == "failed"


def test_concurrent_tasks_finish_the_run(
    client: TestClient,
    sample_videos: list[str],
) -> None:
    project_id = _create_project(client)
    _add_items(client, project_id, sample_videos)
    start = client.post(f"/api/v1/projects/{project_id}/start")
    task_ids = start.json()["task_ids"]

    async def run_both() -> None:
        async def run_one(task_id: str) -> None:
            async with SessionLocal() as session:
                await process_task(session, UUID(task_id), transcriber=FakeTranscriber())

        await asyncio.gather(*(run_one(task_id) for task_id in task_ids))

    asyncio.run(run_both())

    run = client.get(f"/api/v1/runs/{start.json()['run']['id']}").json()
    assert run["status"] == "completed"
    assert {task["status"] for task in run["tasks"]} == {"succeeded"}
    assert client.get(f"/api/v1/projects/{project_id}").json()["status"] == "completed"


def test_unknown_artifact_format_returns_404(
    client: TestClient,
    sample_video: str,
) -> None:
    project_id = _create_project(client)
    _add_items(client, project_id, [sample_video])
    start = client.post(f"/api/v1/projects/{project_id}/start")
    task_id = start.json()["task_ids"][0]
    assert _process(task_id).disposition == TaskDisposition.SUCCEEDED

    assert client.get(f"/api/v1/tasks/{task_id}/files/pdf").status_code == 404
