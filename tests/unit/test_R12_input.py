from fastapi.testclient import TestClient

from ticketing.app import create_app


def test_R12_mutation_requires_idempotency_key() -> None:
    response = TestClient(create_app()).post(
        "/events/00000000-0000-0000-0000-000000000001/holds", json={}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "missing_idempotency_key"
