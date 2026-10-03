"use client";

import { useEffect, useState } from "react";
import { apiClient } from "../../lib/api/client";
import type { components } from "../../lib/api/schema";

type ServiceStatuses = components["schemas"]["ServiceStatuses"];

type StatusState =
  | { kind: "loading" }
  | { kind: "healthy" }
  | { kind: "degraded"; services: ServiceStatuses }
  | { kind: "unreachable"; detail: string };

const pollingInterval = 10_000;

export default function StatusPage() {
  const [status, setStatus] = useState<StatusState>({ kind: "loading" });

  useEffect(() => {
    let mounted = true;

    async function loadStatus() {
      try {
        const { data, error, response } = await apiClient.GET("/ready");
        if (!mounted) {
          return;
        }

        if (response.status === 503 && error && "detail" in error) {
          setStatus({ kind: "degraded", services: error.detail.services });
        } else if (data) {
          setStatus({ kind: "healthy" });
        } else {
          setStatus({
            kind: "unreachable",
            detail: "The API returned an unexpected response.",
          });
        }
      } catch {
        if (mounted) {
          setStatus({
            kind: "unreachable",
            detail: "The API could not be reached.",
          });
        }
      }
    }

    void loadStatus();
    const intervalId = window.setInterval(() => void loadStatus(), pollingInterval);

    return () => {
      mounted = false;
      window.clearInterval(intervalId);
    };
  }, []);

  const apiIsReachable = status.kind === "healthy" || status.kind === "degraded";
  const services = status.kind === "degraded" ? status.services : undefined;
  const apiState =
    status.kind === "loading" ? "checking" : apiIsReachable ? "ok" : "down";
  const postgresState = serviceState(status, services?.postgres);
  const neo4jState = serviceState(status, services?.neo4j);

  return (
    <section className="status-page" aria-labelledby="status-title">
      <header className="status-overview">
        <p className="eyebrow">Live system checks</p>
        <h1 id="status-title">Service status</h1>
        <p>Current availability of the API and its data services.</p>
      </header>

      <p className="status-summary" role="status" aria-live="polite">
        {summaryFor(status)}
      </p>

      <div className="status-grid">
        <StatusCard name="API" state={apiState} detail={apiDetail(status)} />
        <StatusCard
          name="Postgres"
          state={postgresState.state}
          detail={postgresState.detail}
        />
        <StatusCard
          name="Neo4j"
          state={neo4jState.state}
          detail={neo4jState.detail}
        />
      </div>
    </section>
  );
}

function serviceState(
  status: StatusState,
  serviceStatus: ServiceStatuses[keyof ServiceStatuses] | undefined,
): { state: string; detail?: string } {
  if (status.kind === "loading") {
    return { state: "checking" };
  }
  if (status.kind === "unreachable") {
    return { state: "down", detail: "Cannot verify while the API is unreachable." };
  }
  if (serviceStatus === "unavailable") {
    return { state: "down", detail: "unavailable" };
  }
  return { state: "ok" };
}

function summaryFor(status: StatusState): string {
  switch (status.kind) {
    case "loading":
      return "Checking service health...";
    case "healthy":
      return "All services are healthy.";
    case "degraded":
      return "The API is reachable, but one or more services are unavailable.";
    case "unreachable":
      return `API unreachable. ${status.detail}`;
  }
}

function apiDetail(status: StatusState): string | undefined {
  if (status.kind === "degraded") {
    return "API is responding.";
  }
  if (status.kind === "unreachable") {
    return status.detail;
  }
  return undefined;
}

function StatusCard({
  name,
  state,
  detail,
}: {
  name: string;
  state: string;
  detail?: string;
}) {
  const cardState = state === "ok" ? "ok" : state === "down" ? "down" : "checking";

  return (
    <article className="status-card" data-state={cardState} aria-label={`${name} status`}>
      <h2>{name}</h2>
      <p className="status-indicator">{state}</p>
      {detail && <p className="status-detail">{detail}</p>}
    </article>
  );
}