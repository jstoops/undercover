import { cleanup, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { renderAt, stubApi } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows both sets of instructions, read only", async () => {
  stubApi({
    "GET /api/instructions": {
      queue: "# Running the queue\n\nHand each claim to work_claim.",
      claim: "# Working a claim\n\nDecide the claim.",
    },
  });
  renderAt("/instructions");
  expect(
    screen.getByRole("heading", { name: "The agent's instructions" }),
  ).toBeDefined();
  const queue = within(
    await screen.findByRole("region", { name: "Running the queue" }),
  );
  expect(queue.getByText(/Hand each claim/).textContent).toBe(
    "# Running the queue\n\nHand each claim to work_claim.",
  );
  const claim = within(screen.getByRole("region", { name: "Working a claim" }));
  expect(claim.getByText(/Decide the claim/).textContent).toBe(
    "# Working a claim\n\nDecide the claim.",
  );
  expect(screen.queryByRole("textbox")).toBeNull();
});

it("says when the instructions can't be loaded", async () => {
  stubApi({});
  renderAt("/instructions");
  expect((await screen.findByRole("alert")).textContent).toContain(
    "The instructions could not be loaded",
  );
});
