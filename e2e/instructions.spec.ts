import { expect, test } from "@playwright/test";

test("the instructions page shows the agent's instructions, read only", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Instructions" }).click();
  await expect(
    page.getByRole("heading", { name: "The agent's instructions" }),
  ).toBeVisible();
  await expect(page.locator("pre")).toContainText("# The UnderCover Agent");
  await expect(page.locator("pre")).toContainText("Payouts over $1,000");
  await expect(page.getByRole("textbox")).toHaveCount(0);
});
