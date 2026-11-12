import { expect, test } from "@playwright/test";

// Other tests change some claims at the same time, so these check the queue's
// shape rather than how many claims are in each state.

test("the queue shows every claim", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Claims queue" }),
  ).toBeVisible();
  await expect(page.getByRole("row")).toHaveCount(26);
  const counts = page
    .getByRole("group", { name: "Claims by status" })
    .locator(".count-number");
  await expect(counts).toHaveCount(4);
  const total = (await counts.allTextContents()).reduce(
    (sum, count) => sum + Number(count),
    0,
  );
  expect(total).toBe(25);
  await expect(page.getByRole("row", { name: /CLM-1001/ })).toContainText(
    "Waiting",
  );
});

test("a claim opens from the queue", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "CLM-1001" }).click();
  await expect(page).toHaveURL(/\/claims\/CLM-1001$/);
  await expect(page.getByRole("heading", { name: "CLM-1001" })).toBeVisible();
});

test("the queue shows a claim in progress without a reload", async ({
  page,
  request,
}) => {
  await page.goto("/");
  const row = page.getByRole("row", { name: /CLM-1004/ });
  await expect(row).toContainText("Waiting");
  const started = await request.post("/api/claims/CLM-1004/start");
  expect(started.ok()).toBe(true);
  await expect(row).toContainText("In progress");
});
