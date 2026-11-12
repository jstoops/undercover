import {
  act,
  cleanup,
  fireEvent,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { queue } from "./fixtures";
import { renderAt, stubApi } from "./testing";
import { POLL_MS } from "./useApi";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function rows() {
  return screen.getAllByRole("row").slice(1);
}

it("lists the claims with their status and decision", async () => {
  stubApi({ "GET /api/claims": queue });
  renderAt("/");
  expect(await screen.findByRole("link", { name: "CLM-1001" })).toBeDefined();
  expect(rows()).toHaveLength(3);
  const first = within(rows()[0]);
  expect(first.getByText("Maya Patel")).toBeDefined();
  expect(first.getByText("Trip delay")).toBeDefined();
  expect(first.getByText("Jun 24, 2026")).toBeDefined();
  expect(first.getByText("$420.00")).toBeDefined();
  expect(first.getByText("Waiting")).toBeDefined();
  expect(first.queryByText("Approve")).toBeNull();
  const third = within(rows()[2]);
  expect(third.getByText("Waiting for sign-off")).toBeDefined();
  expect(third.getByText("Approve")).toBeDefined();
  expect(third.getByText("$3,750.00")).toBeDefined();
  expect(
    screen.getByRole("link", { name: "CLM-1003" }).getAttribute("href"),
  ).toBe("/claims/CLM-1003");
});

it("counts the claims in each state", async () => {
  stubApi({ "GET /api/claims": queue });
  renderAt("/");
  expect(
    await screen.findByRole("button", { name: "Waiting 1" }),
  ).toBeDefined();
  expect(screen.getByRole("button", { name: "In progress 1" })).toBeDefined();
  expect(
    screen.getByRole("button", { name: "Waiting for sign-off 1" }),
  ).toBeDefined();
  expect(screen.getByRole("button", { name: "Decided 0" })).toBeDefined();
  expect(
    screen.getByRole("button", { name: "Left for a handler 0" }),
  ).toBeDefined();
});

it("shows the claims left for a handler", async () => {
  const left = {
    ...queue[0],
    claim_id: "CLM-1008",
    status: "left_for_handler",
    failures: 2,
  };
  stubApi({ "GET /api/claims": [...queue, left] });
  renderAt("/");
  const count = await screen.findByRole("button", {
    name: "Left for a handler 1",
  });
  expect(within(rows()[3]).getByText("Left for a handler")).toBeDefined();
  fireEvent.click(count);
  expect(rows()).toHaveLength(1);
  expect(screen.getByRole("link", { name: "CLM-1008" })).toBeDefined();
});

it("shows only the claims in a state when you click its count", async () => {
  stubApi({ "GET /api/claims": queue });
  renderAt("/");
  const signOff = await screen.findByRole("button", {
    name: "Waiting for sign-off 1",
  });
  fireEvent.click(signOff);
  expect(signOff.getAttribute("aria-pressed")).toBe("true");
  expect(rows()).toHaveLength(1);
  expect(screen.getByRole("link", { name: "CLM-1003" })).toBeDefined();
  fireEvent.click(signOff);
  expect(rows()).toHaveLength(3);
});

it("refreshes the queue every two seconds", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const routes: Record<string, unknown> = { "GET /api/claims": queue };
  stubApi(routes);
  renderAt("/");
  expect(
    await screen.findByRole("button", { name: "Decided 0" }),
  ).toBeDefined();
  routes["GET /api/claims"] = queue.map((claim) => ({
    ...claim,
    status: "decided",
  }));
  await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
  expect(
    await screen.findByRole("button", { name: "Decided 3" }),
  ).toBeDefined();
});

it("says when the queue can't be loaded", async () => {
  stubApi({});
  renderAt("/");
  expect((await screen.findByRole("alert")).textContent).toBe(
    "The queue could not be loaded: No route for GET /api/claims",
  );
});

it("says when the backend can't be reached", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response("Bad gateway", { status: 502 })),
  );
  renderAt("/");
  expect((await screen.findByRole("alert")).textContent).toContain(
    "The backend answered 502",
  );
});
