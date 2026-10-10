from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.graph.dependencies import get_graph_repository
from app.graph.repository import GraphRepository
from app.schemas.impact import (
    ErrorResponse,
    ImpactedNodeResponse,
    ImpactPathResponse,
    ImpactResponse,
)

router = APIRouter()


@router.get(
    "/nodes/{node_id}/impact",
    response_model=ImpactResponse,
    responses={
        404: {"model": ErrorResponse, "description": "The target node does not exist."},
        503: {"model": ErrorResponse, "description": "The graph database is unavailable."},
        422: {"description": "The query parameter failed validation."},
    },
)
def node_impact(
    node_id: Annotated[str, Path(description="ID of the target graph node.")],
    repository: Annotated[GraphRepository, Depends(get_graph_repository)],
    max_depth: Annotated[int, Query(ge=1, le=10, description="Maximum traversal depth.")] = 10,
) -> ImpactResponse:
    impact = repository.get_impact(node_id, max_depth=max_depth)
    if not impact.found:
        raise HTTPException(status_code=404, detail=f"Node {node_id!r} was not found")
    details = (
        repository.get_node_details(tuple(node.id for node in impact.dependents))
        if impact.dependents
        else {}
    )
    dependents = [
        ImpactedNodeResponse(
            id=dependent.id,
            name=details[dependent.id].name,
            label=details[dependent.id].label,
            paths=[
                ImpactPathResponse(
                    node_ids=list(path.node_ids),
                    edge_types=list(path.edge_types),
                    criticalities=list(path.criticalities),
                )
                for path in dependent.paths
            ],
        )
        for dependent in impact.dependents
    ]
    return ImpactResponse(
        target_id=node_id,
        max_depth=max_depth,
        count=len(dependents),
        dependents=dependents,
    )
