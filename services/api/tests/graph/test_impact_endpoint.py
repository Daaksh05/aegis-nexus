from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from neo4j.exceptions import AuthError, ServiceUnavailable, SessionExpired

from app.graph.dependencies import get_graph_repository
from app.graph.repository import ImpactedNode, ImpactPath, ImpactResult, NodeDetails
from app.main import app


class FakeGraphRepository:
    def __init__(self) -> None:
        self.last_max_depth: int | None = None
        self.details_requested = False
        self.failure: Exception | None = None

    def get_impact(self, node_id: str, max_depth: int = 10) -> ImpactResult:
        if self.failure is not None:
            raise self.failure
        self.last_max_depth = max_depth
        if node_id == "unknown":
            return ImpactResult(found=False, dependents=())
        if node_id == "leaf":
            return ImpactResult(found=True, dependents=())
        return ImpactResult(
            found=True,
            dependents=(
                ImpactedNode(
                    id="app_ticketing",
                    paths=(
                        ImpactPath(
                            node_ids=("app_ticketing", "api_payment"),
                            edge_types=("DEPENDS_ON",),
                            criticalities=("high",),
                        ),
                    ),
                ),
            ),
        )

    def get_node_details(self, node_ids: tuple[str, ...]) -> dict[str, NodeDetails]:
        self.details_requested = True
        return {
            node_id: NodeDetails(id=node_id, name="Ticketing", label="Application")
            for node_id in node_ids
        }


@pytest.fixture
def api_client() -> Iterator[tuple[TestClient, FakeGraphRepository]]:
    repository = FakeGraphRepository()
    app.dependency_overrides[get_graph_repository] = lambda: repository
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, repository
    finally:
        app.dependency_overrides.pop(get_graph_repository, None)


def test_impact_returns_dependents_and_full_paths(
    api_client: tuple[TestClient, FakeGraphRepository],
) -> None:
    client, repository = api_client
    response = client.get("/nodes/api_payment/impact?max_depth=2")

    assert response.status_code == 200
    assert response.json() == {
        "target_id": "api_payment",
        "max_depth": 2,
        "count": 1,
        "dependents": [
            {
                "id": "app_ticketing",
                "name": "Ticketing",
                "label": "Application",
                "paths": [
                    {
                        "node_ids": ["app_ticketing", "api_payment"],
                        "edge_types": ["DEPENDS_ON"],
                        "criticalities": ["high"],
                    }
                ],
            }
        ],
    }
    assert repository.details_requested


def test_impact_returns_404_for_unknown_node(
    api_client: tuple[TestClient, FakeGraphRepository],
) -> None:
    client, _ = api_client
    response = client.get("/nodes/unknown/impact")

    assert response.status_code == 404
    assert response.json() == {"detail": "Node 'unknown' was not found"}


@pytest.mark.parametrize("max_depth", [0, 11, "abc"])
def test_impact_rejects_invalid_max_depth(
    api_client: tuple[TestClient, FakeGraphRepository],
    max_depth: int | str,
) -> None:
    client, _ = api_client
    response = client.get("/nodes/api_payment/impact", params={"max_depth": max_depth})

    assert response.status_code == 422


def test_impact_defaults_to_depth_ten(
    api_client: tuple[TestClient, FakeGraphRepository],
) -> None:
    client, repository = api_client
    response = client.get("/nodes/api_payment/impact")

    assert response.status_code == 200
    assert response.json()["max_depth"] == 10
    assert repository.last_max_depth == 10


def test_leaf_node_returns_empty_dependents(
    api_client: tuple[TestClient, FakeGraphRepository],
) -> None:
    client, repository = api_client
    response = client.get("/nodes/leaf/impact")

    assert response.status_code == 200
    assert response.json() == {
        "target_id": "leaf",
        "max_depth": 10,
        "count": 0,
        "dependents": [],
    }
    assert not repository.details_requested


@pytest.mark.parametrize(
    "exception_type",
    [ServiceUnavailable, SessionExpired],
)
def test_impact_returns_redacted_503_when_graph_is_unavailable(
    api_client: tuple[TestClient, FakeGraphRepository],
    exception_type: type[ServiceUnavailable] | type[SessionExpired],
) -> None:
    client, repository = api_client
    repository.failure = exception_type("bolt://private-host:7687 with private credentials")

    response = client.get("/nodes/api_payment/impact")

    assert response.status_code == 503
    assert response.json() == {"detail": "Graph database is unavailable"}


def test_impact_does_not_hide_authentication_errors(
    api_client: tuple[TestClient, FakeGraphRepository],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, repository = api_client
    repository.failure = AuthError("bad credentials for private-host")

    response = client.get("/nodes/api_payment/impact")

    assert response.status_code == 500
    assert "Graph database error" in caplog.text
    assert "bad credentials for private-host" in caplog.text
    assert "bad credentials for private-host" not in response.text
