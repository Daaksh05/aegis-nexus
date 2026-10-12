from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from neo4j.exceptions import AuthError, ServiceUnavailable, SessionExpired

from app.graph.dependencies import get_graph_repository
from app.graph.repository import SpofEvidence, SpofEvidenceResult
from app.main import app


def _evidence(
    dependent_id: str,
    dependent_name: str,
    dependent_label: str,
    node_ids: tuple[str, ...],
    redundancies: tuple[int | None, ...],
) -> SpofEvidence:
    target_redundancy = redundancies[-1]
    return SpofEvidence(
        target_id="api_payment",
        target_name="Payment API",
        target_label="API",
        dependent_id=dependent_id,
        dependent_name=dependent_name,
        dependent_label=dependent_label,
        path_depth=len(node_ids) - 1,
        node_ids=node_ids,
        edge_redundancies=redundancies,
        target_edge_redundancy=target_redundancy,
        explicit_zero_on_target_edge=target_redundancy == 0,
        target_edge_redundancy_unspecified=target_redundancy is None,
    )


class FakeGraphRepository:
    def __init__(self) -> None:
        self.last_target_id: str | None = None
        self.last_max_depth: int | None = None
        self.failure: Exception | None = None
        self.result = SpofEvidenceResult(
            found=True,
            evidence=(
                _evidence(
                    "app_ticketing",
                    "Ticketing",
                    "Application",
                    ("app_ticketing", "api_payment"),
                    (0,),
                ),
                _evidence(
                    "svc_fares",
                    "Fares",
                    "Service",
                    ("svc_fares", "app_ticketing", "api_payment"),
                    (3, 0),
                ),
                _evidence(
                    "sys_network",
                    "Transit Network",
                    "System",
                    ("sys_network", "api_payment"),
                    (None,),
                ),
            ),
        )

    def get_spof_evidence(
        self, max_depth: int = 10, target_id: str | None = None
    ) -> SpofEvidenceResult:
        if self.failure is not None:
            raise self.failure
        self.last_target_id = target_id
        self.last_max_depth = max_depth
        return self.result


@pytest.fixture
def api_client() -> Iterator[tuple[TestClient, FakeGraphRepository]]:
    repository = FakeGraphRepository()
    app.dependency_overrides[get_graph_repository] = lambda: repository
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, repository
    finally:
        app.dependency_overrides.pop(get_graph_repository, None)


def test_spof_endpoint_returns_paths_and_redundancy_evidence(
    api_client: tuple[TestClient, FakeGraphRepository],
) -> None:
    client, repository = api_client

    response = client.get("/nodes/api_payment/spof-evidence?max_depth=3")

    assert response.status_code == 200
    body = response.json()
    assert body["target_id"] == "api_payment"
    assert body["max_depth"] == 3
    assert body["count"] == len(body["evidence"]) == 3
    assert [
        (
            item["dependent_id"],
            item["dependent_name"],
            item["dependent_label"],
            item["path_depth"],
            item["node_ids"],
            item["edge_redundancies"],
            item["target_edge_redundancy"],
            item["explicit_zero_on_target_edge"],
            item["target_edge_redundancy_unspecified"],
        )
        for item in body["evidence"]
    ] == [
        (
            "app_ticketing",
            "Ticketing",
            "Application",
            1,
            ["app_ticketing", "api_payment"],
            [0],
            0,
            True,
            False,
        ),
        (
            "svc_fares",
            "Fares",
            "Service",
            2,
            ["svc_fares", "app_ticketing", "api_payment"],
            [3, 0],
            0,
            True,
            False,
        ),
        (
            "sys_network",
            "Transit Network",
            "System",
            1,
            ["sys_network", "api_payment"],
            [None],
            None,
            False,
            True,
        ),
    ]
    assert all(
        (item["target_name"], item["target_label"]) == ("Payment API", "API")
        for item in body["evidence"]
    )
    assert repository.last_target_id == "api_payment"
    assert repository.last_max_depth == 3


def test_spof_endpoint_returns_empty_evidence_for_existing_leaf(
    api_client: tuple[TestClient, FakeGraphRepository],
) -> None:
    client, repository = api_client
    repository.result = SpofEvidenceResult(found=True, evidence=())

    response = client.get("/nodes/api_payment/spof-evidence")

    assert response.status_code == 200
    assert response.json() == {
        "target_id": "api_payment",
        "max_depth": 10,
        "count": 0,
        "evidence": [],
    }


def test_spof_endpoint_returns_404_for_unknown_target(
    api_client: tuple[TestClient, FakeGraphRepository],
) -> None:
    client, repository = api_client
    repository.result = SpofEvidenceResult(found=False, evidence=())

    response = client.get("/nodes/unknown/spof-evidence")

    assert response.status_code == 404
    assert response.json() == {"detail": "Node 'unknown' was not found"}


@pytest.mark.parametrize("max_depth", [0, 11, "abc"])
def test_spof_endpoint_rejects_invalid_max_depth(
    api_client: tuple[TestClient, FakeGraphRepository],
    max_depth: int | str,
) -> None:
    client, _ = api_client

    response = client.get("/nodes/api_payment/spof-evidence", params={"max_depth": max_depth})

    assert response.status_code == 422


@pytest.mark.parametrize("exception_type", [ServiceUnavailable, SessionExpired])
def test_spof_endpoint_returns_503_when_graph_is_unavailable(
    api_client: tuple[TestClient, FakeGraphRepository],
    exception_type: type[ServiceUnavailable] | type[SessionExpired],
) -> None:
    client, repository = api_client
    repository.failure = exception_type("bolt://private-host:7687 with private credentials")

    response = client.get("/nodes/api_payment/spof-evidence")

    assert response.status_code == 503
    assert response.json() == {"detail": "Graph database is unavailable"}


def test_spof_endpoint_does_not_expose_authentication_error(
    api_client: tuple[TestClient, FakeGraphRepository],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, repository = api_client
    repository.failure = AuthError("bad credentials for private-host")

    response = client.get("/nodes/api_payment/spof-evidence")

    assert response.status_code == 500
    assert "Graph database error" in caplog.text
    assert "bad credentials for private-host" in caplog.text
    assert "bad credentials for private-host" not in response.text
