from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from app.healthchecks import check_neo4j, check_postgres

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ServiceStatuses(BaseModel):
    postgres: Literal["ok", "unavailable"]
    neo4j: Literal["ok", "unavailable"]


class ReadyResponse(BaseModel):
    status: Literal["ready"]
    services: ServiceStatuses


class NotReadyDetail(BaseModel):
    status: Literal["not_ready"]
    services: ServiceStatuses


class NotReadyResponse(BaseModel):
    detail: NotReadyDetail


@app.get("/health", response_model=HealthResponse)
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/ready",
    response_model=ReadyResponse,
    responses={503: {"model": NotReadyResponse}},
)
def ready(
    postgres_ok: Annotated[bool, Depends(check_postgres)],
    neo4j_ok: Annotated[bool, Depends(check_neo4j)],
) -> dict[str, object]:
    services = {
        "postgres": "ok" if postgres_ok else "unavailable",
        "neo4j": "ok" if neo4j_ok else "unavailable",
    }
    if not postgres_ok or not neo4j_ok:
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "services": services},
        )
    return {"status": "ready", "services": services}