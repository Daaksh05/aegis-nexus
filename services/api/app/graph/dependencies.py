from fastapi import Request

from app.graph.repository import GraphRepository


def get_graph_repository(request: Request) -> GraphRepository:
    repository = request.app.state.graph_repository
    if not isinstance(repository, GraphRepository):
        raise RuntimeError("Graph repository is not available")
    return repository
