import os
import shutil
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


def _root() -> Path:
    return Path(os.environ["NAS_INPUT_ROOT"])


def _case_dir(name: str) -> Path:
    path = _root() / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def test_list_nas_root_and_nested_directory(client: TestClient) -> None:
    case = _case_dir("nas-api-test")
    (case / "spring").mkdir()
    (case / "lecture-01.mp4").write_bytes(b"video")
    (case / "notes.txt").write_text("not media")
    (case / "spring" / "lecture-02.mkv").write_bytes(b"video-2")

    response = client.get("/api/v1/nas/files", params={"path": "nas-api-test"})
    assert response.status_code == 200
    body = response.json()
    assert body["path"] == "nas-api-test"
    assert body["parent"] == ""
    assert body["directories"] == [
        {"name": "spring", "path": "nas-api-test/spring"}
    ]
    assert [file["name"] for file in body["files"]] == ["lecture-01.mp4"]
    assert body["files"][0]["size_bytes"] == 5
    assert body["truncated"] is False

    response = client.get(
        "/api/v1/nas/files",
        params={"path": "nas-api-test/spring"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["path"] == "nas-api-test/spring"
    assert body["parent"] == "nas-api-test"
    assert [file["path"] for file in body["files"]] == [
        "nas-api-test/spring/lecture-02.mkv"
    ]


def test_nas_root_listing_has_no_parent(client: TestClient) -> None:
    _case_dir("nas-root-listing")

    response = client.get("/api/v1/nas/files")
    assert response.status_code == 200
    body = response.json()
    assert body["path"] == ""
    assert body["parent"] is None
    assert "nas-root-listing" in [
        directory["name"] for directory in body["directories"]
    ]


def test_nas_listing_limit_sets_truncated(client: TestClient) -> None:
    case = _case_dir("nas-api-limit")
    for index in range(3):
        (case / f"lecture-{index}.mp4").write_bytes(b"x")

    response = client.get(
        "/api/v1/nas/files",
        params={"path": "nas-api-limit", "limit": 2},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["files"]) == 2
    assert body["truncated"] is True


def test_nas_rejects_unsafe_paths(client: TestClient) -> None:
    for path in ["../escape", "/etc", "a\\b", "a/../b", ".", "a//b"]:
        response = client.get("/api/v1/nas/files", params={"path": path})
        assert response.status_code == 422, path

    response = client.get("/api/v1/nas/files", params={"path": "a\x00b"})
    assert response.status_code == 422


def test_nas_missing_directory_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/nas/files", params={"path": "does-not-exist"})
    assert response.status_code == 404


def test_nas_file_path_returns_422(client: TestClient) -> None:
    case = _case_dir("nas-api-file")
    (case / "lecture.mp4").write_bytes(b"video")

    response = client.get(
        "/api/v1/nas/files",
        params={"path": "nas-api-file/lecture.mp4"},
    )
    assert response.status_code == 422


def test_nas_skips_symlinks_that_escape_the_root(client: TestClient) -> None:
    case = _case_dir("nas-api-symlink")
    outside = Path(tempfile.mkdtemp(prefix="transcributed-outside-"))
    try:
        (case / "escape").symlink_to(outside, target_is_directory=True)

        response = client.get(
            "/api/v1/nas/files",
            params={"path": "nas-api-symlink"},
        )
        assert response.status_code == 200
        assert "escape" not in [
            directory["name"] for directory in response.json()["directories"]
        ]
    finally:
        shutil.rmtree(outside)
