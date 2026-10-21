from fastapi.testclient import TestClient

from transcributed import __version__


def test_version_endpoint_reports_the_api_version(client: TestClient) -> None:
    response = client.get("/api/v1/version")

    assert response.status_code == 200
    assert response.json() == {"version": __version__}
