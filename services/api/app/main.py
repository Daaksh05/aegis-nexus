import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from neo4j.exceptions import GqlError, ServiceUnavailable, SessionExpired
from pydantic import BaseModel

from app.graph.repository import GraphRepository
from app.graph.routes import router as graph_router
from app.healthchecks import check_neo4j, check_postgres

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    repository = GraphRepository()
    application.state.graph_repository = repository
    try:
        yield
    finally:
        repository.close()


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.include_router(graph_router)


async def graph_unavailable_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if isinstance(exc, ServiceUnavailable | SessionExpired):
        status_code = 503
        detail = "Graph database is unavailable"
    else:
        status_code = 500
        detail = "Graph database error"
    logger.error(
        detail,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail},
    )


app.add_exception_handler(GqlError, graph_unavailable_handler)


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
