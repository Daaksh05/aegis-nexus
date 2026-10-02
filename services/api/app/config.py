from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False)

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "aegis"
    postgres_password: str = ""
    postgres_db: str = "aegis"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""


def get_settings() -> Settings:
    return Settings()