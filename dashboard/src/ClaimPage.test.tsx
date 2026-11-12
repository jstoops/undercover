import {
  cleanup,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import {
  approvedClaim,
  claim,
  customer,
  handlers,
  heldClaim,
  policy,
  signedOffClaim,
  steps,
} from "./fixtures";
import { renderAt, stubApi } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const records = {
  "GET /api/policies/POL-2001": policy,
  "GET /api/customers/CUS-3001": customer,
  "GET /api/handlers": handlers,
};

function region(name: string) {
  return within(screen.getByRole("region", { name }));
}

it("shows the claim in full, with its policy and customer", async () => {
  stubApi({
    ...records,
    "GET /api/claims/CLM-1001": claim,
    "GET /api/claims/CLM-1001/steps": [],
  });
  renderAt("/claims/CLM-1001");
  expect(await screen.findByText(/canceled by Meridian Air/)).toBeDefined();
  const details = region("The claim");
  expect(details.getByText(/, Rome, Italy$/)).toBeDefined();
  expect(details.getByText("Jun 18, 2026")).toBeDefined();
  expect(details.getAllByRole("row")).toHaveLength(5);
  expect(details.getByText("Airport hotel, one night")).toBeDefined();
  expect(details.getByText("Accommodation")).toBeDefined();
  expect(details.getByText("$420.00")).toBeDefined();
  expect(details.getByText("Meridian Air cancellation notice")).toBeDefined();
  expect(details.getByText("Carrier report")).toBeDefined();
  expect(await screen.findByText("Premium")).toBeDefined();
  const policyPanel = region("The policy");
  expect(policyPanel.getByText("Electronics plus")).toBeDefined();
  expect(policyPanel.getByText("$3,100.00")).toBeDefined();
  expect(policyPanel.getByText("Jun 10, 2026 to Jun 18, 2026")).toBeDefined();
  const customerPanel = region("The customer");
  expect(customerPanel.getByText("Apr 11, 2023")).toBeDefined();
  expect(customerPanel.getByText("CLM-0412")).toBeDefined();
  expect(customerPanel.getByText("$140.00")).toBeDefined();
});

it("says when nothing has happened yet", async () => {
  stubApi({
    ...records,
    "GET /api/claims/CLM-1001": claim,
    "GET /api/claims/CLM-1001/steps": [],
  });
  renderAt("/claims/CLM-1001");
  expect(
    await screen.findByText("The agent hasn't decided this claim yet."),
  ).toBeDefined();
  expect(screen.getByText("No steps yet.")).toBeDefined();
  expect(screen.getByText("Waiting")).toBeDefined();
});

it("says when the agent is working", async () => {
  stubApi({
    ...records,
    "GET /api/claims/CLM-1001": { ...claim, status: "in_progress" },
    "GET /api/claims/CLM-1001/steps": [],
  });
  renderAt("/claims/CLM-1001");
  expect(
    await screen.findByText("The agent is working on this claim."),
  ).toBeDefined();
});

it("shows the decision and the payment", async () => {
  stubApi({
    ...records,
    "GET /api/claims/CLM-1001": approvedClaim,
    "GET /api/claims/CLM-1001/steps": [],
  });
  renderAt("/claims/CLM-1001");
  const decision = within(
    await screen.findByRole("region", { name: "The agent's decision" }),
  );
  expect(decision.getByText("Approve")).toBeDefined();
  expect(
    decision.getByText("$420.00", { selector: ".payout-large" }),
  ).toBeDefined();
  expect(decision.getByText(/The receipts total \$420\.00/)).toBeDefined();
  expect(decision.getByText("Section 3, Trip Delay")).toBeDefined();
  expect(decision.getByText(/^Paid/)).toBeDefined();
  expect(decision.queryByRole("button")).toBeNull();
});

it("says when an approval hasn't been paid", async () => {
  stubApi({
    ...records,
    "GET /api/claims/CLM-1001": { ...approvedClaim, payment: null },
    "GET /api/claims/CLM-1001/steps": [],
  });
  renderAt("/claims/CLM-1001");
  expect(await screen.findByText("Not paid yet.")).toBeDefined();
});

it("shows a decline without a payout or a payment", async () => {
  const decision = {
    decision: "decline",
    payout: 0,
    reason: "Not covered.",
    policy_section: "Section 9, General exclusions",
    decided_at: "2026-11-09T22:36:17+00:00",
  };
  stubApi({
    ...records,
    "GET /api/claims/CLM-1001": { ...claim, status: "decided", decision },
    "GET /api/claims/CLM-1001/steps": [],
  });
  renderAt("/claims/CLM-1001");
  expect(await screen.findByText("Decline")).toBeDefined();
  expect(region("The agent's decision").queryByText(/^Paid/)).toBeNull();
  expect(screen.queryByText("Not paid yet.")).toBeNull();
});

it("shows the agent's steps in plain words", async () => {
  stubApi({
    ...records,
    "GET /api/claims/CLM-1001": claim,
    "GET /api/claims/CLM-1001/steps": steps,
  });
  renderAt("/claims/CLM-1001");
  const list = within(await screen.findByRole("list", { name: "Steps" }));
  const labels = list.getAllByRole("listitem").map((item) => item.textContent);
  expect(labels).toHaveLength(10);
  expect(list.getByText("Read the claim")).toBeDefined();
  expect(list.getByText("Result: Read the claim")).toBeDefined();
  expect(list.getByText("Read the policy")).toBeDefined();
  expect(list.getByText("Read the customer's claim history")).toBeDefined();
  expect(list.getByText("Recorded the decision")).toBeDefined();
  expect(list.getByText("Asked to pay")).toBeDefined();
  expect(
    list.getByText("Refused: The payment is held until a handler signs off"),
  ).toBeDefined();
  expect(list.getByText("search_web")).toBeDefined();
  expect(list.getByText("Result: search_web")).toBeDefined();
  expect(list.getByText("Not JSON at all")).toBeDefined();
  expect(list.getByText("The agent said")).toBeDefined();
  expect(
    list.getByText("Approved $1,500.00; waiting for sign-off."),
  ).toBeDefined();
  expect(list.getAllByText(/"claim_id": "CLM-1001"/)).toHaveLength(2);
});

it("lets a handler sign off a held payment", async () => {
  const routes: Record<string, unknown> = {
    ...records,
    "GET /api/claims/CLM-1003": heldClaim,
    "GET /api/claims/CLM-1003/steps": [],
    "POST /api/claims/CLM-1003/sign-off": signedOffClaim,
  };
  const fetchMock = stubApi(routes, (key) => {
    if (key === "POST /api/claims/CLM-1003/sign-off")
      routes["GET /api/claims/CLM-1003"] = signedOffClaim;
  });
  renderAt("/claims/CLM-1003");
  expect(
    await screen.findByText(/The payment is held until a handler signs off/),
  ).toBeDefined();
  const button = screen.getByRole("button", { name: "Sign off and pay" });
  expect(button.hasAttribute("disabled")).toBe(true);
  await screen.findByRole("option", { name: "Dana Whitfield" });
  fireEvent.change(screen.getByLabelText("Handler"), {
    target: { value: "HND-01" },
  });
  expect(button.hasAttribute("disabled")).toBe(false);
  fireEvent.click(button);
  expect(await screen.findByText(/Signed off by Dana Whitfield/)).toBeDefined();
  expect(
    region("The agent's decision").getByText(/^Paid/).textContent,
  ).toContain("$1,500.00");
  expect(screen.queryByRole("button", { name: "Sign off and pay" })).toBeNull();
  const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
  expect(post?.[1]?.body).toBe(JSON.stringify({ handler_id: "HND-01" }));
});

it("says when a sign-off is refused", async () => {
  stubApi({
    ...records,
    "GET /api/claims/CLM-1003": heldClaim,
    "GET /api/claims/CLM-1003/steps": [],
  });
  renderAt("/claims/CLM-1003");
  await screen.findByRole("option", { name: "Dana Whitfield" });
  fireEvent.change(screen.getByLabelText("Handler"), {
    target: { value: "HND-01" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Sign off and pay" }));
  await waitFor(() => {
    expect(screen.getByRole("alert").textContent).toBe(
      "No route for POST /api/claims/CLM-1003/sign-off",
    );
  });
});

it("says when the claim can't be loaded", async () => {
  stubApi({});
  renderAt("/claims/CLM-9999");
  expect((await screen.findByRole("alert")).textContent).toBe(
    "This claim could not be loaded: No route for GET /api/claims/CLM-9999",
  );
});
