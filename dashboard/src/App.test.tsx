import { cleanup, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { renderAt, stubApi } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("has links to the queue and the instructions", () => {
  stubApi({});
  renderAt("/instructions");
  const nav = screen.getByRole("navigation", { name: "Main" });
  expect(nav.textContent).toContain("Queue");
  expect(nav.textContent).toContain("Instructions");
  expect(screen.getByRole("link", { name: "Instructions" }).className).toBe(
    "active",
  );
});

it("says when there is no page", () => {
  stubApi({});
  renderAt("/nowhere");
  expect(screen.getByText("There is no page here.")).toBeDefined();
});

it("shows a claim's id on its page", () => {
  stubApi({});
  renderAt("/claims/CLM-1001");
  expect(screen.getByRole("heading", { name: "CLM-1001" })).toBeDefined();
});
