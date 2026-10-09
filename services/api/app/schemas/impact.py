from pydantic import BaseModel, ConfigDict, Field


class ImpactPathResponse(BaseModel):
    node_ids: list[str] = Field(description="Node IDs in traversal order, dependent to target.")
    edge_types: list[str] = Field(description="Relationship type for each adjacent node pair.")
    criticalities: list[str | None] = Field(
        description="Edge criticality for each adjacent node pair, or null when unset."
    )


class ImpactedNodeResponse(BaseModel):
    id: str = Field(description="ID of the node that depends on the target.")
    name: str = Field(description="Display name of the dependent node.")
    label: str = Field(description="Graph label of the dependent node.")
    paths: list[ImpactPathResponse] = Field(
        description="All discovered paths from this dependent to the target."
    )


class ImpactResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "target_id": "api_payment",
                    "max_depth": 10,
                    "count": 1,
                    "dependents": [
                        {
                            "id": "app_ticketing",
                            "name": "Ticketing",
                            "label": "Application",
                            "paths": [
                                {
                                    "node_ids": ["app_ticketing", "api_payment"],
                                    "edge_types": ["DEPENDS_ON"],
                                    "criticalities": ["high"],
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    )

    target_id: str = Field(description="ID of the node whose impact was requested.")
    max_depth: int = Field(description="Maximum relationship traversal depth used.")
    count: int = Field(description="Number of distinct dependent nodes returned.")
    dependents: list[ImpactedNodeResponse] = Field(
        description="Nodes that depend on the target and their complete discovered paths."
    )


class ErrorResponse(BaseModel):
    detail: str = Field(description="Explanation of the request error.")
