# Aegis Nexus: agent instructions

AI resilience digital twin for critical infrastructure. It models a dependency graph
(Government -> Systems -> Applications -> APIs -> Cloud -> Suppliers -> Infrastructure ->
Services -> Citizens), simulates policy changes and cyber threats against it, and produces
a comparative resilience score so officials can pick the safest option before deploying.

Pilot domain: **public transport only**, on a synthetic dataset (~80-120 nodes).
Do not generalize to energy, healthcare, etc. This is a deliberate scope decision.

## Current phase: Week 1, foundations and twin core

Do only what the current prompt asks. If a task seems to need something outside its
scope, stop and ask.

Not yet: simulation engines, Monte Carlo, threat simulation, scoring, copilot, auth,
live telemetry, cloud deployment, non-transit domains.

## Stack

- Python 3.12, FastAPI (services/api)
- Engine in services/engine: pure Python, never imports FastAPI
- Neo4j Community (pinned image tag, never `latest`) via the official `neo4j` driver
- Postgres (pinned tag) for relational data; Docker Compose only, no Kubernetes
- Next.js + TypeScript (apps/web); D3 only when a graph view is requested
- OpenAPI spec in packages/contracts is the contract: change the spec first, then
  generate the TS client
- pytest for API and engine tests

Do NOT introduce: Redpanda, TimescaleDB, Mesa, SimPy, PyTorch, Kubernetes.
NetworkX and NumPy are allowed only inside services/engine, and not before Week 3.

## Repo layout

apps/web, services/api, services/engine, packages/contracts, data/seed, infra, docs/adr

## Domain model (draft; ADR-002 is the source of truth once merged)

Node labels: TransitAuthority, System, Application, API, CloudProvider, Supplier,
PhysicalInfrastructure, Service, CitizenGroup.
Every node has a unique string `id` and a `name`.

Relationship: `DEPENDS_ON`, directed **dependent -> depended-on**, optional
`criticality`: `low` | `medium` | `high`.
Do not add HOSTED_ON, SUPPLIES, or SERVES until ADR-002 is merged.

Example: `(app_ticketing)-[:DEPENDS_ON]->(api_payment)` means ticketing needs the payment
API. If the payment API fails, ticketing is affected.

## Core query: reverse impact traversal

Given a node, return everything that depends on it, directly or transitively, as **full
paths**, not just neighbors. Traverse _toward_ the target:

    MATCH p = (dependent)-[:DEPENDS_ON*1..N]->(target {id: $id})
    RETURN p

Neo4j does not allow a parameter in the range. Validate `max_depth` as an int
(1 to 10) and build N from the validated int only, never from raw user input.

- Always cap depth (default 10).
- Never reverse the arrow direction. Re-check this in every graph query.
- Return distinct dependents with their paths and the criticality along each path.
- Get this query right and tested before anything built on top of it.

## Conventions

- All Cypher lives in `services/api/app/graph/queries.py`. Never inline Cypher in routes.
- Route handlers stay thin: validate, call a query function, shape the response.
- Parameterized Cypher only. No f-strings with user input (except the validated depth).
- Every endpoint needs a pytest test using the seed data (`data/seed/transit.cypher`).
- Query tests must run without the API layer.
- Unknown node id -> 404. Invalid depth -> 422.
- Type hints and Pydantic response models everywhere.
- Trunk-based, PRs under 400 lines, conventional commits, no direct pushes to `main`.
- No secrets in code. Config via env vars; commit `.env.example` only.
- One task per change. Flag any drift into live telemetry, cloud deployment, or a
  non-transit domain.
