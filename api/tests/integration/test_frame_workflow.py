import asyncio
import io
import os
import zipfile
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient

from transcributed.db import SessionLocal
from transcributed.worker.frames import (
    FakeFrameExtractor,
    FrameExtractionResult,
)
from transcributed.worker.main import TaskDisposition, TaskOutcome, process_task


class PartialFrameExtractor:
    def extract(
        self,
        input_path: Path,
        spec: dict[str, Any],
        *,
        should_cancel: Any | None = None,
        on_progress: Any | None = None,
    ) -> FrameExtractionResult:
        result = FakeFrameExtractor().extract(
            input_path,
            spec,
            should_cancel=should_cancel,
            on_progress=on_progress,
        )
        return FrameExtractionResult(result.frames[:1], ["00:00:20"])


class AllSkippedFrameExtractor:
    def extract(
        self,
        input_path: Path,
        spec: dict[str, Any],
        *,
        should_cancel: Any | None = None,
        on_progress: Any | None = None,
    ) -> FrameExtractionResult:
        return FrameExtractionResult([], ["00:00:10", "00:00:20"])


def _create_frame_project(client: TestClient) -> str:
    response = client.post(
        "/api/v1/projects",
        json={"name": "Frame project", "workflow": "frames"},
    )
    assert response.status_code == 201
    assert response.json()["workflow"] == "frames"
    assert response.json()["defaults"] == {}
    return response.json()["id"]


def _add_videos(client: TestClient, project_id: str, paths: list[str]) -> list[dict]:
    response = client.post(
        f"/api/v1/projects/{project_id}/items",
        json={"items": [{"path": path} for path in paths]},
    )
    assert response.status_code == 201
    assert response.json()["accepted"] == len(paths)
    return client.get(f"/api/v1/projects/{project_id}/items").json()


def _attach_timecodes(
    client: TestClient,
    project_id: str,
    items: list[dict],
    timecodes: list[str],
) -> None:
    for item, path in zip(items, timecodes, strict=True):
        response = client.put(
            f"/api/v1/projects/{project_id}/items/{item['id']}/timecode",
            json={"path": path},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["timecode_path"] == path
        assert body["timecode_status"] == "ok"


def _process(task_id: str, extractor: Any) -> TaskOutcome:
    async def run() -> TaskOutcome:
        async with SessionLocal() as session:
            return await process_task(
                session,
                UUID(task_id),
                frame_extractor=extractor,
            )

    return asyncio.run(run())


def test_frame_project_extracts_and_downloads_zip(
    client: TestClient,
    sample_videos: list[str],
    sample_timecodes: list[str],
) -> None:
    project_id = _create_frame_project(client)
    items = _add_videos(client, project_id, sample_videos)
    _attach_timecodes(client, project_id, items, sample_timecodes)

    response = client.post(f"/api/v1/projects/{project_id}/start")
    assert response.status_code == 202, response.text
    start = response.json()
    assert start["run"]["spec"]["kind"] == "frames"

    for task_id, expected in zip(start["task_ids"], [2, 3], strict=True):
        outcome = _process(task_id, FakeFrameExtractor())
        assert outcome.disposition == TaskDisposition.SUCCEEDED

        task = client.get(f"/api/v1/tasks/{task_id}").json()
        assert task["spec"]["kind"] == "frames"
        assert task["frames_extracted"] == expected
        assert task["frames_skipped"] == 0
        assert {artifact["format"] for artifact in task["artifacts"]} == {
            "manifest",
            "zip",
        }

        response = client.get(f"/api/v1/tasks/{task_id}/files/zip")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            names = archive.namelist()
            assert "manifest.json" in names
            assert len([name for name in names if name.endswith(".png")]) == expected

    assert client.get(f"/api/v1/projects/{project_id}").json()["status"] == "completed"

    items = client.get(f"/api/v1/projects/{project_id}/items").json()
    assert items[0]["latest_task_status"] == "succeeded"
    assert {artifact["format"] for artifact in items[0]["latest_task_artifacts"]} == {
        "manifest",
        "zip",
    }


def test_frame_project_requires_timecode_file(
    client: TestClient,
    sample_video: str,
) -> None:
    project_id = _create_frame_project(client)
    _add_videos(client, project_id, [sample_video])

    response = client.post(f"/api/v1/projects/{project_id}/start")

    assert response.status_code == 409
    details = response.json()["details"]
    assert details["items"][0]["error"] == "No timecode file attached"
    assert client.get(f"/api/v1/projects/{project_id}/runs").json() == []


def test_frame_project_rejects_changed_timecode_file(
    client: TestClient,
    sample_video: str,
    sample_timecode: str,
) -> None:
    project_id = _create_frame_project(client)
    items = _add_videos(client, project_id, [sample_video])
    _attach_timecodes(client, project_id, items, [sample_timecode])

    timecode_path = Path(os.environ["NAS_INPUT_ROOT"]) / sample_timecode
    timecode_path.write_text("00:00:10\n00:00:20\n00:00:30\n00:00:40\n")

    response = client.post(f"/api/v1/projects/{project_id}/start")

    assert response.status_code == 409
    assert "changed" in response.json()["details"]["items"][0]["error"]


def test_invalid_timecode_is_rejected_when_attached(
    client: TestClient,
    sample_video: str,
) -> None:
    project_id = _create_frame_project(client)
    items = _add_videos(client, project_id, [sample_video])
    invalid = Path(os.environ["NAS_INPUT_ROOT"]) / "invalid.txt"
    invalid.write_text("00:00:10\nnot-a-timecode\n")

    response = client.put(
        f"/api/v1/projects/{project_id}/items/{items[0]['id']}/timecode",
        json={"path": "invalid.txt"},
    )

    assert response.status_code == 422
    assert "Invalid timecode" in response.json()["detail"]


def test_partial_frame_failures_succeed_and_record_skips(
    client: TestClient,
    sample_video: str,
    sample_timecode: str,
) -> None:
    project_id = _create_frame_project(client)
    items = _add_videos(client, project_id, [sample_video])
    _attach_timecodes(client, project_id, items, [sample_timecode])
    start = client.post(f"/api/v1/projects/{project_id}/start").json()

    outcome = _process(start["task_ids"][0], PartialFrameExtractor())

    assert outcome.disposition == TaskDisposition.SUCCEEDED
    task = client.get(f"/api/v1/tasks/{start['task_ids'][0]}").json()
    assert task["frames_extracted"] == 1
    assert task["frames_skipped"] == 1


def test_all_skipped_frames_fail_the_task(
    client: TestClient,
    sample_video: str,
    sample_timecode: str,
) -> None:
    project_id = _create_frame_project(client)
    items = _add_videos(client, project_id, [sample_video])
    _attach_timecodes(client, project_id, items, [sample_timecode])
    start = client.post(f"/api/v1/projects/{project_id}/start").json()

    outcome = _process(start["task_ids"][0], AllSkippedFrameExtractor())

    assert outcome.disposition == TaskDisposition.FAILED
    task = client.get(f"/api/v1/tasks/{start['task_ids'][0]}").json()
    assert task["status"] == "failed"
    assert task["frames_extracted"] == 0
    assert task["frames_skipped"] == 2
    assert task["error"] == "no frames extracted"
