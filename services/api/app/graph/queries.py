"""Cypher query definitions and graph schema allow-lists."""

from typing import Final

NODE_LABELS: Final[tuple[str, ...]] = (
    "TransitAuthority",
    "System",
    "Application",
    "API",
    "CloudProvider",
    "Supplier",
    "PhysicalInfrastructure",
    "Service",
    "CitizenGroup",
)
EDGE_TYPES: Final[tuple[str, ...]] = (
    "DEPENDS_ON",
    "HOSTED_ON",
    "SUPPLIED_BY",
    "SERVED_BY",
)
EDGE_PROPERTIES: Final[frozenset[str]] = frozenset(
    {"criticality", "redundancy", "recovery_time_minutes"}
)
GET_NODE = "MATCH (node {id: $id}) RETURN properties(node) AS node LIMIT 1"
GET_NODE_DETAILS = (
    "MATCH (node) WHERE node.id IN $ids "
    "RETURN node.id AS id, node.name AS name, labels(node)[0] AS label"
)
TARGET_EXISTS = "MATCH (target {id: $id}) RETURN target.id AS id LIMIT 1"
DELETE_TEST_NODES = "MATCH (node {test_run: $test_run}) DETACH DELETE node"


def validate_node_label(label: str) -> str:
    if label not in NODE_LABELS:
        raise ValueError(f"Unsupported graph node label: {label!r}")
    return label


def validate_edge_type(edge_type: str) -> str:
    if edge_type not in EDGE_TYPES:
        raise ValueError(f"Unsupported graph edge type: {edge_type!r}")
    return edge_type


def node_constraint_query(label: str) -> str:
    validated_label = validate_node_label(label)
    constraint_name = f"node_id_{validated_label.lower()}"
    return (
        f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS "
        f"FOR (node:{validated_label}) REQUIRE node.id IS UNIQUE"
    )


def upsert_node_query(label: str) -> str:
    validated_label = validate_node_label(label)
    return (
        f"MERGE (node:{validated_label} {{id: $id}}) "
        "SET node.name = $name SET node += $props RETURN properties(node) AS node"
    )


def upsert_edge_query(edge_type: str) -> str:
    validated_type = validate_edge_type(edge_type)
    return (
        f"MATCH (source {{id: $source_id}}), (target {{id: $target_id}}) "
        f"MERGE (source)-[edge:{validated_type}]->(target) "
        "SET edge += $props "
        "RETURN type(edge) AS type, properties(edge) AS properties"
    )


def validate_max_depth(max_depth: object) -> int:
    if type(max_depth) is not int or not 1 <= max_depth <= 10:
        raise ValueError("max_depth must be an integer in the range 1..10")
    return max_depth


def impact_query(max_depth: object) -> str:
    depth = validate_max_depth(max_depth)
    # Every edge points dependent -> depended-on; traverse toward the target.
    return (
        "MATCH p = (dependent)-[rels:DEPENDS_ON|HOSTED_ON|SUPPLIED_BY|SERVED_BY*1.."
        f"{depth}]->(target {{id: $id}}) "
        "RETURN DISTINCT dependent.id AS dependent_id, "
        "[node IN nodes(p) | node.id] AS node_ids, "
        "[rel IN rels | type(rel)] AS edge_types, "
        "[rel IN rels | rel.criticality] AS criticalities "
        "ORDER BY dependent_id, node_ids, edge_types"
    )


def spof_query(max_depth: object = 10) -> str:
    depth = validate_max_depth(max_depth)
    # Return evidence only; redundancy metadata does not guarantee failover.
    return (
        "MATCH p = (dependent)-[rels:DEPENDS_ON*1.."
        f"{depth}]->(target) "
        "WHERE $target_id IS NULL OR target.id = $target_id "
        "RETURN DISTINCT "
        "target.id AS target_id, target.name AS target_name, "
        "labels(target)[0] AS target_label, "
        "dependent.id AS dependent_id, dependent.name AS dependent_name, "
        "labels(dependent)[0] AS dependent_label, "
        "length(p) AS path_depth, "
        "[node IN nodes(p) | node.id] AS node_ids, "
        "[rel IN rels | rel.redundancy] AS edge_redundancies, "
        "last(rels).redundancy AS target_edge_redundancy, "
        "coalesce(last(rels).redundancy = 0, false) "
        "AS explicit_zero_on_target_edge, "
        "last(rels).redundancy IS NULL AS target_edge_redundancy_unspecified "
        "ORDER BY target_id, dependent_id, node_ids"
    )
