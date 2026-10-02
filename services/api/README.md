# API

Requires Python 3.12.

From this directory, install dependencies and run the API:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Set `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`,
`POSTGRES_DB`, `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD` in the environment
to configure readiness checks. The defaults target local services.

Run the tests without Docker:

```sh
pytest
```

For the full stack, copy the repository's `.env.example` to `.env` and run
`docker compose --env-file .env -f infra/docker-compose.yml up --build` from the
repository root.