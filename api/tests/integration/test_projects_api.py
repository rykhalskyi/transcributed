import asyncio
from uuid import UUID

from fastapi.testclient import TestClient

from transcributed.db import SessionLocal
from transcributed.worker.main import process_task
from transcributed.worker.transcriber import FakeTranscriber


def test_project_add_start_and_process(
    client: TestClient,
    sample_video: str,
) -> None:
    response = client.post(
        "/api/v1/projects",
        json={"name": "Lectures set 1", "defaults": {"language": "de"}},
    )
    assert response.status_code == 201
    project_id = response.json()["id"]

    response = client.post(
        f"/api/v1/projects/{project_id}/items",
        json={"items": [{"path": sample_video}]},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["accepted"] == 1
    assert body["rejected"] == 0

    response = client.post(f"/api/v1/projects/{project_id}/start")
    assert response.status_code == 202
    start_body = response.json()
    assert start_body["enqueued"] == 0
    assert start_body["not_enqueued"] == 1
    task_id = start_body["task_ids"][0]

    response = client.post(f"/api/v1/projects/{project_id}/start")
    assert response.status_code == 409

    async def run_worker() -> None:
        async with SessionLocal() as session:
            await process_task(session, UUID(task_id), transcriber=FakeTranscriber())

    asyncio.run(run_worker())

    response = client.get(f"/api/v1/tasks/{task_id}")
    assert response.status_code == 200
    task = response.json()
    assert task["status"] == "succeeded"
    assert task["progress"] == 100
    assert len(task["artifacts"]) == 2

    response = client.get(f"/api/v1/tasks/{task_id}/files/txt")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert "Fake transcript" in response.text

    response = client.get(f"/api/v1/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"

    response = client.get(f"/api/v1/runs/{start_body['run']['id']}")
    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "completed"
    assert run["tasks"][0]["status"] == "succeeded"

    response = client.get(f"/api/v1/projects/{project_id}/items")
    assert response.status_code == 200
    item = response.json()[0]
    assert item["latest_task_status"] == "succeeded"
    assert item["latest_task_progress"] == 100
    assert item["latest_task_artifacts"]
    assert {artifact["format"] for artifact in item["latest_task_artifacts"]} == {
        "txt",
        "metadata",
    }
    assert all(
        "content" not in artifact for artifact in item["latest_task_artifacts"]
    )


def test_only_requested_formats_are_written(
    client: TestClient,
    sample_video: str,
) -> None:
    response = client.post(
        "/api/v1/projects",
        json={"name": "VTT only", "defaults": {"output_formats": ["vtt"]}},
    )
    project_id = response.json()["id"]

    client.post(
        f"/api/v1/projects/{project_id}/items",
        json={"items": [{"path": sample_video}]},
    )
    start = client.post(f"/api/v1/projects/{project_id}/start").json()
    task_id = start["task_ids"][0]

    async def run_worker() -> None:
        async with SessionLocal() as session:
            await process_task(session, UUID(task_id), transcriber=FakeTranscriber())

    asyncio.run(run_worker())

    task = client.get(f"/api/v1/tasks/{task_id}").json()
    formats = {artifact["format"] for artifact in task["artifacts"]}
    assert formats == {"vtt", "metadata"}

    response = client.get(f"/api/v1/tasks/{task_id}/files/vtt")
    assert response.status_code == 200
    assert response.text.startswith("WEBVTT")


def test_txt_timestamps_defaults_are_rendered(
    client: TestClient,
    sample_video: str,
) -> None:
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Timestamped TXT",
            "defaults": {"output_formats": ["txt"], "txt_timestamps": True},
        },
    )
    assert response.status_code == 201
    project_id = response.json()["id"]

    client.post(
        f"/api/v1/projects/{project_id}/items",
        json={"items": [{"path": sample_video}]},
    )
    start = client.post(f"/api/v1/projects/{project_id}/start").json()
    task_id = start["task_ids"][0]

    async def run_worker() -> None:
        async with SessionLocal() as session:
            await process_task(session, UUID(task_id), transcriber=FakeTranscriber())

    asyncio.run(run_worker())

    task = client.get(f"/api/v1/tasks/{task_id}").json()
    assert task["spec"]["txt_timestamps"] is True

    response = client.get(f"/api/v1/tasks/{task_id}/files/txt")
    assert response.status_code == 200
    assert response.text.startswith("[00:00:00.000 --> 00:00:05.000] ")


def test_run_tasks_follow_project_item_order(
    client: TestClient,
    sample_videos: list[str],
) -> None:
    project_id = client.post("/api/v1/projects", json={"name": "Ordered"}).json()["id"]
    client.post(
        f"/api/v1/projects/{project_id}/items",
        json={"items": [{"path": path} for path in sample_videos]},
    )

    items = client.get(f"/api/v1/projects/{project_id}/items").json()
    start = client.post(f"/api/v1/projects/{project_id}/start").json()
    run = client.get(f"/api/v1/runs/{start['run']['id']}").json()

    assert [task["project_item_id"] for task in run["tasks"]] == [
        item["id"] for item in items
    ]


def test_add_items_reports_invalid_paths(
    client: TestClient,
    sample_video: str,
) -> None:
    response = client.post("/api/v1/projects", json={"name": "Mixed"})
    project_id = response.json()["id"]

    response = client.post(
        f"/api/v1/projects/{project_id}/items",
        json={
            "items": [
                {"path": sample_video},
                {"path": "missing.mp4"},
                {"path": "../escape.mp4"},
            ]
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["accepted"] == 1
    assert body["rejected"] == 2
    assert body["results"][0]["created"] is True
    assert body["results"][1]["accepted"] is False


def test_duplicate_item_is_not_created_twice(
    client: TestClient,
    sample_video: str,
) -> None:
    response = client.post("/api/v1/projects", json={"name": "Duplicates"})
    project_id = response.json()["id"]

    first = client.post(
        f"/api/v1/projects/{project_id}/items",
        json={"items": [{"path": sample_video}]},
    )
    second = client.post(
        f"/api/v1/projects/{project_id}/items",
        json={"items": [{"path": sample_video}]},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["results"][0]["created"] is False
