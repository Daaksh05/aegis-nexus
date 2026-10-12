"""Typed repository operations for the Neo4j graph."""

from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from neo4j import Driver, GraphDatabase, Session

from app.config import Settings, get_settings
from app.graph.queries import (
    EDGE_PROPERTIES,
    GET_NODE,
    GET_NODE_DETAILS,
    NODE_LABELS,
    TARGET_EXISTS,
    impact_query,
    spof_query,
    upsert_edge_query,
    upsert_node_query,
    validate_edge_type,
    validate_max_depth,
    validate_node_label,
)


@dataclass(frozen=True)
class ImpactPath:
    node_ids: tuple[str, ...]
    edge_types: tuple[str, ...]
    criticalities: tuple[str | None, ...]


@dataclass(frozen=True)
class ImpactedNode:
    id: str
    paths: tuple[ImpactPath, ...]


@dataclass(frozen=True)
class ImpactResult:
    found: bool
    dependents: tuple[ImpactedNode, ...]


@dataclass(frozen=True)
class NodeDetails:
    id: str
    name: str
    label: str


@dataclass(frozen=True)
class SpofEvidence:
    target_id: str
    target_name: str
    target_label: str
    dependent_id: str
    dependent_name: str
    dependent_label: str
    path_depth: int
    node_ids: tuple[str, ...]
    edge_redundancies: tuple[int | None, ...]
    target_edge_redundancy: int | None
    explicit_zero_on_target_edge: bool
    target_edge_redundancy_unspecified: bool


@dataclass(frozen=True)
class SpofEvidenceResult:
    found: bool
    evidence: tuple[SpofEvidence, ...]


def create_driver(settings: Settings | None = None) -> Driver:
    graph_settings = settings or get_settings()
    return GraphDatabase.driver(
        graph_settings.neo4j_uri,
        auth=(graph_settings.neo4j_user, graph_settings.neo4j_password),
    )


class GraphRepository:
    def __init__(self, driver: Driver | None = None) -> None:
        self._driver = driver if driver is not None else create_driver()

    def close(self) -> None:
        self._driver.close()

    def verify_connectivity(self) -> None:
        self._driver.verify_connectivity()

    def __enter__(self) -> "GraphRepository":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @contextmanager
    def _session(self) -> Iterator[Session]:
        with self._driver.session() as session:
            yield session

    def upsert_node(self, label: str, id: str, name: str, **props: object) -> dict[str, object]:
        query = upsert_node_query(validate_node_label(label))
        if not isinstance(id, str) or not isinstance(name, str):
            raise ValueError("Node id and name must be strings")
        if "id" in props or "name" in props:
            raise ValueError("Node properties cannot override id or name")
        with self._session() as session:
            record = session.run(query, id=id, name=name, props=props).single()
        if record is None:
            raise RuntimeError("Neo4j did not return the upserted node")
        return dict(record["node"])

    def upsert_edge(
        self, source_id: str, edge_type: str, target_id: str, **props: object
    ) -> dict[str, object]:
        query = upsert_edge_query(validate_edge_type(edge_type))
        unknown = props.keys() - EDGE_PROPERTIES
        if unknown:
            raise ValueError(f"Unsupported edge properties: {sorted(unknown)}")
        criticality = props.get("criticality")
        if criticality is not None and (
            not isinstance(criticality, str) or criticality not in {"low", "medium", "high"}
        ):
            raise ValueError("criticality must be low, medium, or high")
        for key in ("redundancy", "recovery_time_minutes"):
            value = props.get(key)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{key} must be a non-negative integer")
        with self._session() as session:
            record = session.run(
                query,
                source_id=source_id,
                target_id=target_id,
                props=props,
            ).single()
        if record is None:
            raise LookupError("Cannot upsert edge: source or target node was not found")
        return {"type": record["type"], "properties": dict(record["properties"])}

    def get_node(self, id: str) -> dict[str, object] | None:
        with self._session() as session:
            record = session.run(GET_NODE, id=id).single()
        return None if record is None else dict(record["node"])

    def get_node_details(self, node_ids: tuple[str, ...]) -> dict[str, NodeDetails]:
        if not node_ids:
            return {}
        with self._session() as session:
            records = session.run(GET_NODE_DETAILS, ids=list(node_ids))
            details: dict[str, NodeDetails] = {}
            for record in records:
                node_id = record["id"]
                name = record["name"]
                label = record["label"]
                if (
                    not isinstance(node_id, str)
                    or not isinstance(name, str)
                    or not isinstance(label, str)
                    or label not in NODE_LABELS
                ):
                    raise TypeError("Neo4j returned invalid node details")
                details[node_id] = NodeDetails(id=node_id, name=name, label=label)
        missing = set(node_ids) - details.keys()
        if missing:
            raise RuntimeError(f"Neo4j did not return node details for: {sorted(missing)}")
        return details

    def get_impact(self, node_id: str, max_depth: int = 10) -> ImpactResult:
        depth = validate_max_depth(max_depth)
        with self._session() as session:
            target = session.run(TARGET_EXISTS, id=node_id).single()
            if target is None:
                return ImpactResult(found=False, dependents=())
            records = session.run(impact_query(depth), id=node_id)
            grouped: dict[str, list[ImpactPath]] = defaultdict(list)
            for record in records:
                node_ids = tuple(record["node_ids"])
                edge_types = tuple(record["edge_types"])
                criticalities = tuple(record["criticalities"])
                if not all(isinstance(node_id, str) for node_id in node_ids):
                    raise TypeError("Neo4j returned a path with a non-string node id")
                if not all(isinstance(edge_type, str) for edge_type in edge_types):
                    raise TypeError("Neo4j returned an invalid edge type")
                if not all(value is None or isinstance(value, str) for value in criticalities):
                    raise TypeError("Neo4j returned an invalid edge criticality")
                grouped[record["dependent_id"]].append(
                    ImpactPath(
                        node_ids=node_ids,
                        edge_types=edge_types,
                        criticalities=criticalities,
                    )
                )
        return ImpactResult(
            found=True,
            dependents=tuple(
                ImpactedNode(id=dependent_id, paths=tuple(paths))
                for dependent_id, paths in grouped.items()
            ),
        )

    def get_spof_evidence(
        self, max_depth: int = 10, target_id: str | None = None
    ) -> SpofEvidenceResult:
        depth = validate_max_depth(max_depth)
        query = spof_query(depth)
        if target_id is not None and (not isinstance(target_id, str) or not target_id):
            raise ValueError("target_id must be a non-empty string")
        with self._session() as session:
            if target_id is not None:
                target = session.run(TARGET_EXISTS, id=target_id).single()
                if target is None:
                    return SpofEvidenceResult(found=False, evidence=())
                if "id" not in target.keys():
                    raise TypeError("Neo4j returned an invalid SPOF evidence target")
                found_id = target["id"]
                if not isinstance(found_id, str) or found_id != target_id:
                    raise TypeError("Neo4j returned an invalid SPOF evidence target")
            records = session.run(query, target_id=target_id)
            evidence: list[SpofEvidence] = []
            required_fields = {
                "target_id",
                "target_name",
                "target_label",
                "dependent_id",
                "dependent_name",
                "dependent_label",
                "path_depth",
                "node_ids",
                "edge_redundancies",
                "target_edge_redundancy",
                "explicit_zero_on_target_edge",
                "target_edge_redundancy_unspecified",
            }
            for record in records:
                missing_fields = required_fields - set(record.keys())
                if missing_fields:
                    raise TypeError(
                        "Neo4j returned SPOF evidence without fields: " f"{sorted(missing_fields)}"
                    )
                record_target_id = record["target_id"]
                if target_id is not None and record_target_id != target_id:
                    raise TypeError("Neo4j returned SPOF evidence for a different target")
                target_name = record["target_name"]
                target_label = record["target_label"]
                dependent_id = record["dependent_id"]
                dependent_name = record["dependent_name"]
                dependent_label = record["dependent_label"]
                path_depth = record["path_depth"]
                node_ids_value = record["node_ids"]
                edge_redundancies_value = record["edge_redundancies"]
                target_edge_redundancy = record["target_edge_redundancy"]
                explicit_zero = record["explicit_zero_on_target_edge"]
                redundancy_unspecified = record["target_edge_redundancy_unspecified"]

                if not all(
                    isinstance(value, str)
                    for value in (
                        record_target_id,
                        target_name,
                        target_label,
                        dependent_id,
                        dependent_name,
                        dependent_label,
                    )
                ):
                    raise TypeError("Neo4j returned invalid SPOF evidence node details")
                if target_label not in NODE_LABELS or dependent_label not in NODE_LABELS:
                    raise TypeError("Neo4j returned an unsupported SPOF evidence node label")
                if type(path_depth) is not int or not 1 <= path_depth <= depth:
                    raise TypeError("Neo4j returned an invalid SPOF evidence path depth")
                if not isinstance(node_ids_value, list | tuple) or not all(
                    isinstance(node_id, str) for node_id in node_ids_value
                ):
                    raise TypeError("Neo4j returned invalid SPOF evidence path node IDs")
                if len(node_ids_value) != path_depth + 1:
                    raise TypeError("Neo4j returned inconsistent SPOF evidence path length")
                if node_ids_value[0] != dependent_id or node_ids_value[-1] != record_target_id:
                    raise TypeError("Neo4j returned inconsistent SPOF evidence path endpoints")
                if not isinstance(edge_redundancies_value, list | tuple) or not all(
                    value is None or (type(value) is int and value >= 0)
                    for value in edge_redundancies_value
                ):
                    raise TypeError("Neo4j returned invalid SPOF evidence redundancy values")
                if len(edge_redundancies_value) != path_depth:
                    raise TypeError("Neo4j returned inconsistent SPOF evidence redundancy length")
                if target_edge_redundancy is not None and (
                    type(target_edge_redundancy) is not int or target_edge_redundancy < 0
                ):
                    raise TypeError("Neo4j returned an invalid target-edge redundancy value")
                if type(explicit_zero) is not bool or type(redundancy_unspecified) is not bool:
                    raise TypeError("Neo4j returned invalid SPOF evidence redundancy flags")
                if target_edge_redundancy != edge_redundancies_value[-1]:
                    raise TypeError("Neo4j returned inconsistent target-edge redundancy")
                if explicit_zero != (target_edge_redundancy == 0):
                    raise TypeError("Neo4j returned an inconsistent explicit-zero flag")
                if redundancy_unspecified != (target_edge_redundancy is None):
                    raise TypeError("Neo4j returned an inconsistent unspecified-redundancy flag")

                evidence.append(
                    SpofEvidence(
                        target_id=record_target_id,
                        target_name=target_name,
                        target_label=target_label,
                        dependent_id=dependent_id,
                        dependent_name=dependent_name,
                        dependent_label=dependent_label,
                        path_depth=path_depth,
                        node_ids=tuple(node_ids_value),
                        edge_redundancies=tuple(edge_redundancies_value),
                        target_edge_redundancy=target_edge_redundancy,
                        explicit_zero_on_target_edge=explicit_zero,
                        target_edge_redundancy_unspecified=redundancy_unspecified,
                    )
                )
        return SpofEvidenceResult(found=True, evidence=tuple(evidence))
