import { expect, test } from "@playwright/test";
import { decide, finishRun, saveTodos, startClaim, startRun } from "./api";

// This test drives the API the way the queue agent's harness does; it never
// runs a model. It is the only test that starts a run.

test("the queue page shows the run's to-do list as it fills in", async ({
  page,
  request,
}) => {
  await page.goto("/");
  const panel = page.getByRole("region", { name: "This run" });
  await expect(panel).toBeVisible();

  const runId = await startRun(request, 2);
  await expect(panel).toContainText("Running");
  await expect(panel).toContainText("up to 2 claims");

  const items = [
    "CLM-1016: hospital admission",
    "CLM-1015: flew home",
    "Write the summary",
  ];
  const save = (...statuses: string[]) =>
    saveTodos(
      request,
      runId,
      items.map((content, i) => ({ content, status: statuses[i] })),
    );
  await save("in_progress", "pending", "pending");
  const todos = panel.getByRole("listitem");
  await expect(todos).toHaveText([
    /In progress.*CLM-1016/,
    /To do.*CLM-1015/,
    /To do.*Write the summary/,
  ]);

  await startClaim(request, "CLM-1016");
  await decide(request, "CLM-1016", "approve", 300);
  await startClaim(request, "CLM-1015");
  await decide(request, "CLM-1015", "refer", 0);
  await save("completed", "completed", "in_progress");
  await expect(todos).toHaveText([
    /Done.*CLM-1016/,
    /Done.*CLM-1015/,
    /In progress.*Write the summary/,
  ]);
  const referred = page.getByRole("row", { name: /CLM-1015/ });
  await expect(referred).toContainText("Decided");
  await expect(referred).toContainText("Refer");

  await finishRun(request, runId, "Worked 2 claims: 1 approved.");
  await expect(panel).toContainText("Finished");
  await expect(panel).toContainText("Worked 2 claims: 1 approved.");
});
