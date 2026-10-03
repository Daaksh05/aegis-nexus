import { act, cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { mockGet } = vi.hoisted(() => ({ mockGet: vi.fn() }));

vi.mock("../../lib/api/client", () => ({
  apiClient: { GET: mockGet },
}));

import StatusPage from "./page";

function expectCard(name: string, state: string) {
  const card = screen.getByRole("article", { name: `${name} status` });
  expect(within(card).getByText(state)).toBeInTheDocument();
  return card;
}

describe("StatusPage", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockGet.mockReset();
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("shows the loading state while the first check is pending", () => {
    mockGet.mockReturnValue(new Promise(() => {}));

    render(<StatusPage />);

    expect(screen.getByRole("status")).toHaveTextContent("Checking service health");
    expectCard("API", "checking");
    expectCard("Postgres", "checking");
    expectCard("Neo4j", "checking");
  });

  it("shows all services healthy and refreshes every ten seconds", async () => {
    mockGet.mockResolvedValue({
      data: { status: "ready", services: { postgres: "ok", neo4j: "ok" } },
      response: new Response(null, { status: 200 }),
    });

    render(<StatusPage />);

    await act(async () => {});
    expect(screen.getByRole("status")).toHaveTextContent("All services are healthy");
    expectCard("API", "ok");
    expectCard("Postgres", "ok");
    expectCard("Neo4j", "ok");

    await act(async () => {
      vi.advanceTimersByTime(10_000);
    });
    expect(mockGet).toHaveBeenCalledTimes(2);
  });

  it("shows per-service detail for a degraded response", async () => {
    mockGet.mockResolvedValue({
      error: {
        detail: {
          status: "not_ready",
          services: { postgres: "ok", neo4j: "unavailable" },
        },
      },
      response: new Response(null, { status: 503 }),
    });

    render(<StatusPage />);

    await act(async () => {});
    expect(screen.getByRole("status")).toHaveTextContent("one or more services are unavailable");
    expectCard("API", "ok");
    expectCard("Postgres", "ok");
    const neo4jCard = expectCard("Neo4j", "down");
    expect(within(neo4jCard).getByText("unavailable")).toBeInTheDocument();
  });

  it("shows the API unreachable state after a network error", async () => {
    mockGet.mockRejectedValue(new Error("connection refused"));

    render(<StatusPage />);

    await act(async () => {});
    expect(screen.getByRole("status")).toHaveTextContent("API unreachable");
    expectCard("API", "down");
    expectCard("Postgres", "down");
    expectCard("Neo4j", "down");
    expect(screen.getAllByText("The API could not be reached.")).toHaveLength(1);
  });
});