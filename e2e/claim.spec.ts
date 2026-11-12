import { expect, test } from "@playwright/test";
import { addStep, decide, pay, readSection, startClaim } from "./api";

test("a claim's page shows it in full", async ({ page }) => {
  await page.goto("/claims/CLM-1002");
  const claim = page.getByRole("region", { name: "The claim" });
  await expect(claim).toContainText("Milwaukee to Prague");
  await expect(claim.locator("tbody tr")).toHaveCount(6);
  await expect(claim.locator("tfoot")).toContainText("$1,150.00");
  await expect(claim.locator("article")).toHaveCount(3);
  await expect(claim).toContainText("Northwind Airlines settlement letter");
  const policy = page.getByRole("region", { name: "The policy" });
  await expect(policy).toContainText("Premium");
  await expect(policy).toContainText("Prague, Czech Republic");
  const customer = page.getByRole("region", { name: "The customer" });
  await expect(customer).toContainText("Tom Becker");
  await expect(customer.locator("tbody tr")).toHaveCount(2);
  await expect(customer).toContainText("CLM-0907");
});

test("the agent's steps appear as it works", async ({ page, request }) => {
  await page.goto("/claims/CLM-1005");
  await expect(page.getByText("No steps yet.")).toBeVisible();
  await startClaim(request, "CLM-1005");
  await expect(
    page.getByText("The agent is working on this claim."),
  ).toBeVisible();
  const steps = [
    {
      kind: "tool_call",
      name: "get_claim",
      content: '{"claim_id": "CLM-1005"}',
    },
    {
      kind: "tool_result",
      name: "get_claim",
      content: '{"claim_id": "CLM-1005"}',
    },
    {
      kind: "tool_call",
      name: "get_policy",
      content: '{"policy_id": "POL-2005"}',
    },
  ];
  for (const step of steps) {
    await addStep(request, "CLM-1005", step);
  }
  const items = page.getByRole("list", { name: "Steps" }).getByRole("listitem");
  await expect(items).toHaveCount(3);
  await expect(items.nth(0)).toContainText("Read the claim");
  await expect(items.nth(1)).toContainText("Result: Read the claim");
  await expect(items.nth(2)).toContainText("Read the policy");
  await decide(request, "CLM-1005", "refer", 0);
  const decision = page.getByRole("region", { name: "The agent's decision" });
  await expect(decision).toContainText("Refer");
  await expect(decision).toContainText("The receipts support the amount.");
});

test("the claim page shows what the agent read", async ({ page, request }) => {
  await page.goto("/claims/CLM-1006");
  const read = page.getByRole("region", { name: "What the agent read" });
  await expect(read).toContainText("Nothing yet.");
  for (const step of [
    {
      kind: "tool_call",
      name: "read_section",
      content: '{"document": "claims-manual", "number": 7}',
    },
    {
      kind: "tool_result",
      name: "read_section",
      content: await readSection(request, "claims-manual", 7),
    },
  ]) {
    await addStep(request, "CLM-1006", step);
  }
  await expect(read.getByRole("listitem")).toHaveText([
    "Claims manual, 7. Interpretation notes",
  ]);
  await expect(
    page.getByRole("list", { name: "Steps" }).getByRole("listitem").first(),
  ).toContainText("Read the claims manual, section 7");
});

test("a handler signs off a held payment", async ({ page, request }) => {
  await startClaim(request, "CLM-1012");
  await decide(request, "CLM-1012", "approve", 1500);
  const payment = await pay(request, "CLM-1012", 1500);
  expect(payment.status()).toBe(403);

  await page.goto("/claims/CLM-1012");
  const decision = page.getByRole("region", { name: "The agent's decision" });
  await expect(page.locator(".claim-header")).toContainText(
    "Waiting for sign-off",
  );
  await expect(decision).toContainText(
    "The payment is held until a handler signs off",
  );
  await page.getByLabel("Handler").selectOption({ label: "Dana Whitfield" });
  await page.getByRole("button", { name: "Sign off and pay" }).click();
  await expect(page.locator(".claim-header")).toContainText("Decided");
  await expect(decision).toContainText("Paid $1,500.00");
  await expect(decision).toContainText("Signed off by Dana Whitfield");
  await expect(
    page.getByRole("button", { name: "Sign off and pay" }),
  ).toHaveCount(0);

  await page.getByRole("link", { name: "Back to the queue" }).click();
  await expect(page.getByRole("row", { name: /CLM-1012/ })).toContainText(
    "Decided",
  );
});
