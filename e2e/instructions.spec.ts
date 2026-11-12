import { expect, test } from "@playwright/test";

test("the instructions page shows both sets of instructions, read only", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Instructions" }).click();
  await expect(
    page.getByRole("heading", { name: "The agent's instructions" }),
  ).toBeVisible();
  const queue = page.getByRole("region", { name: "Running the queue" });
  await expect(queue).toContainText(
    "# The UnderCover Agent: running the queue",
  );
  await expect(queue).toContainText("work_claim");
  const claim = page.getByRole("region", { name: "Working a claim" });
  await expect(claim).toContainText("# The UnderCover Agent: working a claim");
  await expect(claim).toContainText("Payouts over $1,000");
  await expect(page.getByRole("textbox")).toHaveCount(0);
});
