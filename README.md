# Aegis Nexus

AI resilience digital twin for critical infrastructure.

Aegis Nexus models a dependency graph (Government → Systems → Applications →
APIs → Cloud → Suppliers → Infrastructure → Services → Citizens), simulates
policy changes and adaptive cyber threats against it, and produces a
comparative resilience score, so officials can choose the safest option
before deploying a real change.

**Pilot domain:** public transport (synthetic data, ~80–120 nodes).

## Repo layout

| Path                  | Purpose                                                      |
| --------------------- | ------------------------------------------------------------ |
| `apps/web/`           | Next.js + TypeScript + D3 frontend                           |
| `services/api/`       | FastAPI (routers, schemas, services)                         |
| `services/engine/`    | Cascade, threat, scoring, Monte Carlo (pure Python, no HTTP) |
| `packages/contracts/` | OpenAPI spec and generated TypeScript client                 |
| `data/seed/`          | Synthetic transit twin                                       |
| `infra/`              | Docker Compose, CI                                           |
| `docs/adr/`           | Architecture decision records                                |

## Quick start

    make up      # start Postgres, Neo4j, API
    make test    # API and web tests
    make lint

## Working rules

- Trunk-based development, short-lived branches, PRs under ~400 lines
- Every PR reviewed by the other developer; no direct pushes to `main`
- OpenAPI is the contract: change the spec first, then generate the client
- `services/engine/` never imports FastAPI

## Status

Week 1: foundations and twin core.
