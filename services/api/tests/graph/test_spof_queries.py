from typing import cast

import pytest
from neo4j import Driver

from app.graph import queries
from app.graph.queries import TARGET_EXISTS
from app.graph.repository import GraphRepository


def test_spof_query_traverses_dependents_toward_target() -> None:
    query = queries.spof_query(max_depth=10)

    assert "(dependent)-[rels:DEPENDS_ON*1..10]->(target" in query
    assert "<-[rels:" not in query
    assert "(target)<-" not in query


def test_spof_query_uses_only_depends_on_relationships() -> None:
    query = queries.spof_query(max_depth=10)

    assert "[rels:DEPENDS_ON*" in query
    assert "HOSTED_ON" not in query
    assert "SUPPLIED_BY" not in query
    assert "SERVED_BY" not in query


def test_spof_query_can_scope_evidence_to_a_target_id() -> None:
    query = queries.spof_query(max_depth=10)

    assert "WHERE $target_id IS NULL OR target.id = $target_id" in query


def test_spof_query_validates_max_depth(monkeypatch: pytest.MonkeyPatch) -> None:
    validated_depths: list[object] = []

    def validate_depth(max_depth: object) -> int:
        validated_depths.append(max_depth)
        return 4

    monkeypatch.setattr(queries, "validate_max_depth", validate_depth)

    query = queries.spof_query(max_depth=3)

    assert validated_depths == [3]
    assert "DEPENDS_ON*1..4" in query


@pytest.mark.parametrize("depth", [0, 11, "3", None])
def test_spof_query_rejects_invalid_depths(depth: object) -> None:
    with pytest.raises(ValueError, match="1..10"):
        queries.spof_query(max_depth=depth)


def test_spof_query_returns_path_ids_and_redundancy_metadata() -> None:
    query = queries.spof_query(max_depth=10)

    assert "RETURN DISTINCT" in query
    assert "[node IN nodes(p) | node.id] AS node_ids" in query
    assert "[rel IN rels | rel.redundancy] AS edge_redundancies" in query
    assert "last(rels).redundancy AS target_edge_redundancy" in query
    assert "ORDER BY target_id, dependent_id, node_ids" in query


def test_spof_query_distinguishes_zero_from_unspecified_redundancy() -> None:
    query = queries.spof_query(max_depth=10)

    assert "coalesce(last(rels).redundancy = 0, false)" in query
    assert "AS explicit_zero_on_target_edge" in query
    assert "last(rels).redundancy IS NULL" in query
    assert "AS target_edge_redundancy_unspecified" in query


def test_spof_query_does_not_claim_positive_redundancy_guarantees_failover() -> None:
    query = queries.spof_query(max_depth=10).lower()

    assert "redundancy" in query
    assert "failover" not in query
    assert "guaranteed" not in query


class FakeSession:
    def __init__(self, records: list[dict[str, object]], target_found: bool = True) -> None:
        self.records = records
        self.target_found = target_found
        self.query: str | None = None
        self.parameters: dict[str, object] = {}

    def __enter__(self) -> "FakeSession":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def run(self, query: str, **parameters: object) -> object:
        self.query = query
        self.parameters = parameters
        if query == TARGET_EXISTS:
            return FakeResult({"id": parameters["id"]} if self.target_found else None)
        return self.records


class FakeResult:
    def __init__(self, record: dict[str, object] | None) -> None:
        self.record = record

    def single(self) -> dict[str, object] | None:
        return self.record


class FakeDriver:
    def __init__(self, session: FakeSession) -> None:
        self.fake_session = session

    def session(self) -> FakeSession:
        return self.fake_session


def _spof_record(node_ids: list[str], redundancies: list[int | None]) -> dict[str, object]:
    target_redundancy = redundancies[-1]
    names_and_labels = {
        "api_payment": ("Payment API", "API"),
        "app_ticketing": ("Ticketing", "Application"),
        "svc_fares": ("Fares", "Service"),
        "sys_network": ("Transit Network", "System"),
    }
    dependent_name, dependent_label = names_and_labels[node_ids[0]]
    return {
        "target_id": "api_payment",
        "target_name": "Payment API",
        "target_label": "API",
        "dependent_id": node_ids[0],
        "dependent_name": dependent_name,
        "dependent_label": dependent_label,
        "path_depth": len(node_ids) - 1,
        "node_ids": node_ids,
        "edge_redundancies": redundancies,
        "target_edge_redundancy": target_redundancy,
        "explicit_zero_on_target_edge": target_redundancy == 0,
        "target_edge_redundancy_unspecified": target_redundancy is None,
    }


def test_repository_preserves_each_path_and_redundancy_value() -> None:
    records = [
        _spof_record(["app_ticketing", "api_payment"], [0]),
        _spof_record(["svc_fares", "app_ticketing", "api_payment"], [3, 0]),
        _spof_record(["sys_network", "api_payment"], [None]),
    ]
    session = FakeSession(records)
    repository = GraphRepository(driver=cast(Driver, FakeDriver(session)))

    result = repository.get_spof_evidence()

    assert session.query == queries.spof_query()
    assert session.parameters == {"target_id": None}
    assert [
        (
            item.node_ids,
            item.edge_redundancies,
            item.target_edge_redundancy,
            item.explicit_zero_on_target_edge,
            item.target_edge_redundancy_unspecified,
        )
        for item in result.evidence
    ] == [
        (("app_ticketing", "api_payment"), (0,), 0, True, False),
        (("svc_fares", "app_ticketing", "api_payment"), (3, 0), 0, True, False),
        (("sys_network", "api_payment"), (None,), None, False, True),
    ]
    assert all(item.target_id == "api_payment" for item in result.evidence)
    assert [item.dependent_id for item in result.evidence] == [
        "app_ticketing",
        "svc_fares",
        "sys_network",
    ]


def test_repository_reports_unknown_target() -> None:
    session = FakeSession([], target_found=False)
    repository = GraphRepository(driver=cast(Driver, FakeDriver(session)))

    result = repository.get_spof_evidence(target_id="unknown")

    assert not result.found
    assert result.evidence == ()
    assert session.query == TARGET_EXISTS


def test_repository_rejects_inconsistent_spof_evidence_record() -> None:
    invalid_record = _spof_record(["app_ticketing", "api_payment"], [0])
    invalid_record["path_depth"] = 2
    repository = GraphRepository(driver=cast(Driver, FakeDriver(FakeSession([invalid_record]))))

    with pytest.raises(TypeError, match="inconsistent SPOF evidence path length"):
        repository.get_spof_evidence()


def test_repository_rejects_records_missing_evidence_fields() -> None:
    invalid_record = _spof_record(["app_ticketing", "api_payment"], [0])
    del invalid_record["target_edge_redundancy"]
    repository = GraphRepository(driver=cast(Driver, FakeDriver(FakeSession([invalid_record]))))

    with pytest.raises(TypeError, match="without fields"):
        repository.get_spof_evidence()
