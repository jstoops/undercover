import { act, cleanup, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Run } from "./api";
import { queue } from "./fixtures";
import { renderAt, stubApi } from "./testing";
import { POLL_MS } from "./useApi";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const run: Run = {
  run_id: 1,
  cap: 5,
  status: "running",
  started_at: "2026-11-11T22:00:00+00:00",
  finished_at: null,
  summary: null,
  todos: [
    { position: 1, content: "CLM-1020: sunglasses", status: "completed" },
    { position: 2, content: "CLM-1015: flew home", status: "completed" },
    { position: 3, content: "CLM-1007: phone", status: "in_progress" },
    { position: 4, content: "Write the summary", status: "pending" },
  ],
};

function panel() {
  return within(screen.getByRole("region", { name: "This run" }));
}

it("says when the agent hasn't run yet", async () => {
  stubApi({ "GET /api/claims": queue, "GET /api/runs/current": null });
  renderAt("/");
  expect(await screen.findByText("The agent hasn't run yet.")).toBeDefined();
});

it("shows the run's to-do list as the agent works", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const routes: Record<string, unknown> = {
    "GET /api/claims": queue,
    "GET /api/runs/current": { ...run, todos: [] },
  };
  stubApi(routes);
  renderAt("/");
  expect(await screen.findByText("No to-do list yet.")).toBeDefined();
  expect(panel().getByText("Running")).toBeDefined();
  expect(panel().getByText(/up to 5 claims/)).toBeDefined();
  routes["GET /api/runs/current"] = run;
  await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
  const items = within(await screen.findByRole("list", { name: "To-do list" }))
    .getAllByRole("listitem")
    .map((item) => item.textContent);
  expect(items).toEqual([
    "DoneCLM-1020: sunglasses",
    "DoneCLM-1015: flew home",
    "In progressCLM-1007: phone",
    "To doWrite the summary",
  ]);
});

it("shows the summary when the run ends", async () => {
  stubApi({
    "GET /api/claims": queue,
    "GET /api/runs/current": {
      ...run,
      cap: 1,
      status: "finished",
      finished_at: "2026-11-11T22:10:00+00:00",
      summary: "Worked 1 claim: 1 approved.",
    },
  });
  renderAt("/");
  expect(await screen.findByText("Worked 1 claim: 1 approved.")).toBeDefined();
  expect(panel().getByText("Finished")).toBeDefined();
  expect(panel().getByText(/up to 1 claim$/)).toBeDefined();
});

it("shows a run that stopped", async () => {
  stubApi({
    "GET /api/claims": queue,
    "GET /api/runs/current": { ...run, status: "stopped" },
  });
  renderAt("/");
  expect(await screen.findByText("Stopped")).toBeDefined();
});
