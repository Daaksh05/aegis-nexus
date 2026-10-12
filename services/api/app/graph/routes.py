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
from app.schemas.spof import SpofEvidenceItemResponse, SpofEvidenceResponse

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


@router.get(
    "/nodes/{node_id}/spof-evidence",
    response_model=SpofEvidenceResponse,
    responses={
        404: {"model": ErrorResponse, "description": "The target node does not exist."},
        503: {"model": ErrorResponse, "description": "The graph database is unavailable."},
        422: {"description": "The query parameter failed validation."},
    },
)
def node_spof_evidence(
    node_id: Annotated[str, Path(min_length=1, description="ID of the target graph node.")],
    repository: Annotated[GraphRepository, Depends(get_graph_repository)],
    max_depth: Annotated[int, Query(ge=1, le=10, description="Maximum traversal depth.")] = 10,
) -> SpofEvidenceResponse:
    result = repository.get_spof_evidence(max_depth=max_depth, target_id=node_id)
    if not result.found:
        raise HTTPException(status_code=404, detail=f"Node {node_id!r} was not found")
    evidence = [
        SpofEvidenceItemResponse(
            target_name=item.target_name,
            target_label=item.target_label,
            dependent_id=item.dependent_id,
            dependent_name=item.dependent_name,
            dependent_label=item.dependent_label,
            path_depth=item.path_depth,
            node_ids=list(item.node_ids),
            edge_redundancies=list(item.edge_redundancies),
            target_edge_redundancy=item.target_edge_redundancy,
            explicit_zero_on_target_edge=item.explicit_zero_on_target_edge,
            target_edge_redundancy_unspecified=item.target_edge_redundancy_unspecified,
        )
        for item in result.evidence
    ]
    return SpofEvidenceResponse(
        target_id=node_id,
        max_depth=max_depth,
        count=len(evidence),
        evidence=evidence,
    )
