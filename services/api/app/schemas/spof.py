from pydantic import BaseModel, Field


class SpofEvidenceItemResponse(BaseModel):
    target_name: str = Field(description="Display name of the dependency target.")
    target_label: str = Field(description="Graph label of the dependency target.")
    dependent_id: str = Field(description="ID of the node depending on the target.")
    dependent_name: str = Field(description="Display name of the dependent node.")
    dependent_label: str = Field(description="Graph label of the dependent node.")
    path_depth: int = Field(description="Number of DEPENDS_ON relationships in this path.")
    node_ids: list[str] = Field(description="Node IDs in traversal order, dependent to target.")
    edge_redundancies: list[int | None] = Field(
        description="Redundancy metadata for each edge, in node_ids order; null means unspecified."
    )
    target_edge_redundancy: int | None = Field(
        description="Redundancy metadata on the final edge into the target, or null if unspecified."
    )
    explicit_zero_on_target_edge: bool = Field(
        description="Whether redundancy is explicitly zero on the final edge into the target."
    )
    target_edge_redundancy_unspecified: bool = Field(
        description="Whether redundancy is unspecified on the final edge into the target."
    )


class SpofEvidenceResponse(BaseModel):
    target_id: str = Field(description="ID of the node whose dependency evidence was requested.")
    max_depth: int = Field(description="Maximum DEPENDS_ON traversal depth used.")
    count: int = Field(description="Number of distinct dependent paths returned.")
    evidence: list[SpofEvidenceItemResponse] = Field(
        description=(
            "Potential single-point-of-failure evidence only; redundancy metadata does not "
            "prove that failover is available."
        )
    )
