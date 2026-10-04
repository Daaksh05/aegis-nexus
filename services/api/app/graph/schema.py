"""Explicit Neo4j schema bootstrap."""

from app.config import Settings
from app.graph.queries import NODE_LABELS, node_constraint_query
from app.graph.repository import create_driver


def bootstrap_schema(settings: Settings | None = None) -> None:
    """Create the graph's per-label id constraints; this is never run on import."""
    driver = create_driver(settings)
    try:
        with driver.session() as session:
            for label in NODE_LABELS:
                session.run(node_constraint_query(label)).consume()
    finally:
        driver.close()
