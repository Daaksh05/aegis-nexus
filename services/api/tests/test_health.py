import pytest
from fastapi.testclient import TestClient

from app.healthchecks import check_neo4j, check_postgres
from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("postgres_ok", "neo4j_ok", "expected_status", "expected_ready"),
    [
        (True, True, 200, "ready"),
        (False, True, 503, "not_ready"),
        (True, False, 503, "not_ready"),
    ],
)
def test_ready(
    postgres_ok: bool,
    neo4j_ok: bool,
    expected_status: int,
    expected_ready: str,
) -> None:
    app.dependency_overrides[check_postgres] = lambda: postgres_ok
    app.dependency_overrides[check_neo4j] = lambda: neo4j_ok
    try:
        response = client.get("/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == expected_status
    body = response.json()
    payload = body.get("detail", body)
    assert payload["status"] == expected_ready
    assert payload["services"] == {
        "postgres": "ok" if postgres_ok else "unavailable",
        "neo4j": "ok" if neo4j_ok else "unavailable",
    }