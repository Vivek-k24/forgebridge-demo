from fastapi.testclient import TestClient

from partgraph.main import app


def test_liveness() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"service": "partgraph-api", "status": "ok"}


def test_readiness_reaches_postgres() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["database"] == "ready"
    assert payload["database_ms"] >= 0
