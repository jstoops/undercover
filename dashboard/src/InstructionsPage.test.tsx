import { cleanup, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { renderAt, stubApi } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows the instructions, read only", async () => {
  stubApi({
    "GET /api/instructions": {
      instructions: "# The UnderCover Agent\n\nDecide each claim.",
    },
  });
  renderAt("/instructions");
  expect(
    screen.getByRole("heading", { name: "The agent's instructions" }),
  ).toBeDefined();
  expect((await screen.findByText(/Decide each claim/)).textContent).toBe(
    "# The UnderCover Agent\n\nDecide each claim.",
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
