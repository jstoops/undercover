import { expect, test, type APIRequestContext } from "@playwright/test";

// This test drives the API the way the queue agent's harness does; it never
// runs a model. It is the only test that starts a run.

async function decide(
  request: APIRequestContext,
  claimId: string,
  decision: string,
  payout: number,
) {
  await request.post(`/api/claims/${claimId}/start`);
  await request.post(`/api/claims/${claimId}/decision`, {
    data: {
      decision,
      payout,
      reason: "The wording covers the claim.",
      policy_section: "Section 3, Trip Delay",
    },
  });
}

test("the queue page shows the run's to-do list as it fills in", async ({
  page,
  request,
}) => {
  await page.goto("/");
  const panel = page.getByRole("region", { name: "This run" });
  await expect(panel).toBeVisible();

  const started = await request.post("/api/runs", { data: { cap: 2 } });
  const runId = ((await started.json()) as { run_id: number }).run_id;
  await expect(panel).toContainText("Running");
  await expect(panel).toContainText("up to 2 claims");

  const items = [
    "CLM-1016: hospital admission",
    "CLM-1015: flew home",
    "Write the summary",
  ];
  const save = (...statuses: string[]) =>
    request.put(`/api/runs/${String(runId)}/todos`, {
      data: {
        todos: items.map((content, i) => ({ content, status: statuses[i] })),
      },
    });
  await save("in_progress", "pending", "pending");
  const todos = panel.getByRole("listitem");
  await expect(todos).toHaveText([
    /In progress.*CLM-1016/,
    /To do.*CLM-1015/,
    /To do.*Write the summary/,
  ]);

  await decide(request, "CLM-1016", "approve", 300);
  await decide(request, "CLM-1015", "refer", 0);
  await save("completed", "completed", "in_progress");
  await expect(todos).toHaveText([
    /Done.*CLM-1016/,
    /Left for a handler.*CLM-1015/,
    /In progress.*Write the summary/,
  ]);

  await request.post(`/api/runs/${String(runId)}/finish`, {
    data: { outcome: "finished", summary: "Worked 2 claims: 1 approved." },
  });
  await expect(panel).toContainText("Finished");
  await expect(panel).toContainText("Worked 2 claims: 1 approved.");
});
