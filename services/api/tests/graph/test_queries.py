import pytest

from app.graph.queries import (
    EDGE_TYPES,
    NODE_LABELS,
    impact_query,
    validate_edge_type,
    validate_max_depth,
    validate_node_label,
)


def test_allow_lists_accept_schema_values() -> None:
    assert tuple(validate_node_label(label) for label in NODE_LABELS) == NODE_LABELS
    assert tuple(validate_edge_type(edge_type) for edge_type in EDGE_TYPES) == EDGE_TYPES


def test_allow_lists_reject_values_outside_schema() -> None:
    with pytest.raises(ValueError, match="Unsupported graph node label"):
        validate_node_label("Unknown")
    with pytest.raises(ValueError, match="Unsupported graph edge type"):
        validate_edge_type("SUPPLIES")


def test_impact_query_traverses_dependent_toward_target() -> None:
    query = impact_query(10)
    assert "(dependent)-[rels:" in query
    assert "]->(target {id: $id})" in query
    assert "<-[rels:" not in query
    assert "(target {id: $id})<-" not in query


@pytest.mark.parametrize("depth", [0, 11, "3", None])
def test_depth_validation_rejects_invalid_values(depth: object) -> None:
    with pytest.raises(ValueError, match="1..10"):
        validate_max_depth(depth)
