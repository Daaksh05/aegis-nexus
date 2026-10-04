from collections.abc import Iterator
from uuid import uuid4

import pytest
from neo4j.exceptions import ServiceUnavailable

from app.config import get_settings
from app.graph.queries import DELETE_TEST_NODES
from app.graph.repository import GraphRepository, ImpactPath, create_driver


@pytest.fixture
def graph() -> Iterator[tuple[GraphRepository, str]]:
    settings = get_settings()
    driver = create_driver(settings)
    repository = GraphRepository(driver)
    try:
        repository.verify_connectivity()
    except (ServiceUnavailable, ConnectionError) as exc:
        repository.close()
        pytest.skip(f"Neo4j is unreachable at {settings.neo4j_uri}: {exc}")
    test_run = str(uuid4())
    try:
        nodes = (
            ("API", "api_payment", "Payment API"),
            ("Application", "app_ticketing", "Ticketing"),
            ("Service", "svc_fares", "Fares"),
            ("CitizenGroup", "group_commuters", "Commuters"),
            ("CloudProvider", "cloud_x", "Cloud X"),
        )
        for label, node_id, name in nodes:
            repository.upsert_node(label, node_id, name, test_run=test_run)
        repository.upsert_edge("app_ticketing", "DEPENDS_ON", "api_payment", criticality="high")
        repository.upsert_edge("svc_fares", "DEPENDS_ON", "app_ticketing", criticality="medium")
        repository.upsert_edge("group_commuters", "SERVED_BY", "svc_fares", criticality="low")
        repository.upsert_edge("app_ticketing", "HOSTED_ON", "cloud_x")
        yield repository, test_run
    finally:
        with driver.session() as session:
            session.run(DELETE_TEST_NODES, test_run=test_run).consume()
        repository.close()


@pytest.mark.neo4j
def test_payment_impact_returns_full_paths(graph: tuple[GraphRepository, str]) -> None:
    repository, _ = graph
    payment_impact = repository.get_impact("api_payment")
    assert payment_impact.found
    payment_paths = {node.id: node.paths[0] for node in payment_impact.dependents}
    assert set(payment_paths) == {"app_ticketing", "svc_fares", "group_commuters"}
    assert payment_paths["app_ticketing"] == ImpactPath(
        ("app_ticketing", "api_payment"), ("DEPENDS_ON",), ("high",)
    )
    assert payment_paths["svc_fares"] == ImpactPath(
        ("svc_fares", "app_ticketing", "api_payment"),
        ("DEPENDS_ON", "DEPENDS_ON"),
        ("medium", "high"),
    )
    assert payment_paths["group_commuters"] == ImpactPath(
        ("group_commuters", "svc_fares", "app_ticketing", "api_payment"),
        ("SERVED_BY", "DEPENDS_ON", "DEPENDS_ON"),
        ("low", "medium", "high"),
    )


@pytest.mark.neo4j
def test_leaf_node_has_no_dependents(graph: tuple[GraphRepository, str]) -> None:
    repository, _ = graph
    assert repository.get_impact("group_commuters").dependents == ()


@pytest.mark.neo4j
def test_cloud_impact_traverses_hosted_on(graph: tuple[GraphRepository, str]) -> None:
    repository, _ = graph
    cloud_impact = repository.get_impact("cloud_x")
    assert {node.id for node in cloud_impact.dependents} == {
        "app_ticketing",
        "svc_fares",
        "group_commuters",
    }
    cloud_paths = {node.id: node.paths[0] for node in cloud_impact.dependents}
    assert cloud_paths["app_ticketing"] == ImpactPath(
        ("app_ticketing", "cloud_x"), ("HOSTED_ON",), (None,)
    )
    assert cloud_paths["svc_fares"] == ImpactPath(
        ("svc_fares", "app_ticketing", "cloud_x"),
        ("DEPENDS_ON", "HOSTED_ON"),
        ("medium", None),
    )
    assert cloud_paths["group_commuters"] == ImpactPath(
        ("group_commuters", "svc_fares", "app_ticketing", "cloud_x"),
        ("SERVED_BY", "DEPENDS_ON", "HOSTED_ON"),
        ("low", "medium", None),
    )


@pytest.mark.neo4j
def test_max_depth_one_returns_only_direct_dependent(
    graph: tuple[GraphRepository, str],
) -> None:
    repository, _ = graph
    shallow = repository.get_impact("api_payment", max_depth=1)
    assert {node.id for node in shallow.dependents} == {"app_ticketing"}


@pytest.mark.neo4j
def test_unknown_target_returns_not_found(graph: tuple[GraphRepository, str]) -> None:
    repository, _ = graph
    assert not repository.get_impact("unknown_node").found


@pytest.mark.neo4j
def test_cycle_terminates_without_duplicate_or_target_dependents(
    graph: tuple[GraphRepository, str],
) -> None:
    repository, _ = graph
    repository.upsert_edge("app_ticketing", "DEPENDS_ON", "svc_fares")
    cycle_impact = repository.get_impact("api_payment")
    dependent_ids = [node.id for node in cycle_impact.dependents]
    assert len(dependent_ids) == len(set(dependent_ids))
    assert "api_payment" not in dependent_ids
