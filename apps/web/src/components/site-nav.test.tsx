import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SiteNav } from "./site-nav";

vi.mock("next/navigation", () => ({
  usePathname: () => "/twin",
}));

describe("SiteNav", () => {
  it("renders all routes and marks the active link", () => {
    render(<SiteNav />);

    expect(screen.getByRole("link", { name: "Twin" })).toHaveAttribute(
      "href",
      "/twin",
    );
    expect(screen.getByRole("link", { name: "Scenarios" })).toHaveAttribute(
      "href",
      "/scenarios",
    );
    expect(screen.getByRole("link", { name: "Results" })).toHaveAttribute(
      "href",
      "/results",
    );
    expect(screen.getByRole("link", { name: "Copilot" })).toHaveAttribute(
      "href",
      "/copilot",
    );
    expect(screen.getByRole("link", { name: "Twin" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });
});
