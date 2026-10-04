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
    TARGET_EXISTS,
    impact_query,
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
