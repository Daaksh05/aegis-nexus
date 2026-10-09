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

## Graph impact endpoint

`GET /nodes/{node_id}/impact` returns the target's distinct dependents and each
dependent's paths to the target, including ordered node IDs, edge types, and
edge criticality. The optional `max_depth` query parameter is an integer from
1 through 10 and defaults to 10. Unknown target IDs return `404`; invalid
`max_depth` values return FastAPI's `422` validation response.

For the full stack, copy the repository's `.env.example` to `.env` and run
`docker compose --env-file .env -f infra/docker-compose.yml up --build` from the
repository root.
