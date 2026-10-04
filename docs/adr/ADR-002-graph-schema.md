# ADR-002: Graph schema

- Status: Proposed

## Decisions

Nodes use the labels `TransitAuthority`, `System`, `Application`, `API`,
`CloudProvider`, `Supplier`, `PhysicalInfrastructure`, `Service`, and
`CitizenGroup`. Every node has a unique string `id` and a `name`.

Edges are directed dependent -> depended-on and use `DEPENDS_ON`, `HOSTED_ON`,
`SUPPLIED_BY`, or `SERVED_BY`. This renames the plan's `SUPPLIES` and `SERVES`.
One consistent direction lets reverse impact traversal use a single pattern.
Optional edge properties are `criticality` (`low`, `medium`, or `high`),
`redundancy` (integer >= 0), and `recovery_time_minutes` (integer >= 0).

Example: `(app_ticketing)-[:DEPENDS_ON]->(api_payment)` means ticketing depends
on the payment API. The **impact of X = everything with a path to X along these
edges**.
