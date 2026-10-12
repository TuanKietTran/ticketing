from fastapi.testclient import TestClient

from ticketing.app import create_app


def test_R11_readiness_flips_before_shutdown() -> None:
    app = create_app()
    with TestClient(app) as client:
        assert client.get("/readyz").status_code == 200
        app.state.accepting = False
        assert client.get("/readyz").status_code == 503
