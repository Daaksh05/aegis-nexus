from typing import Annotated

import psycopg
from fastapi import Depends

from app.config import Settings, get_settings
from app.graph.dependencies import get_graph_repository
from app.graph.repository import GraphRepository


def check_postgres(settings: Annotated[Settings, Depends(get_settings)]) -> bool:
    try:
        connection = psycopg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=settings.postgres_user,
            password=settings.postgres_password,
            dbname=settings.postgres_db,
            connect_timeout=2,
        )
        connection.close()
        return True
    except Exception:
        return False


def check_neo4j(
    repository: Annotated[GraphRepository, Depends(get_graph_repository)],
) -> bool:
    try:
        repository.verify_connectivity()
        return True
    except Exception:
        return False
