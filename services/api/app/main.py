from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

from app.healthchecks import check_neo4j, check_postgres

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
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