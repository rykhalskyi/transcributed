from fastapi.testclient import TestClient


def test_cors_allows_the_ui_origin_and_exposes_download_filename(
    client: TestClient,
) -> None:
    origin = "http://localhost:5173"
    response = client.get("/healthz", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "Content-Disposition" in response.headers["access-control-expose-headers"]
