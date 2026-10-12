from fastapi.testclient import TestClient

from ticketing.app import create_app


def test_health_and_request_id() -> None:
    response = TestClient(create_app()).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"]
