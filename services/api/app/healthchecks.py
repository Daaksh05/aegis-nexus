from typing import Annotated

import psycopg
from fastapi import Depends
from neo4j import GraphDatabase

from app.config import Settings, get_settings


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


def check_neo4j(settings: Annotated[Settings, Depends(get_settings)]) -> bool:
    driver = None
    try:
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        driver.verify_connectivity()
        return True
    except Exception:
        return False
    finally:
        if driver is not None:
            driver.close()