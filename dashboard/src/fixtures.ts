import type {
  Claim,
  ClaimSummary,
  Customer,
  Handler,
  Policy,
  Step,
} from "./api";

export const claim: Claim = {
  claim_id: "CLM-1001",
  policy_id: "POL-2001",
  customer_id: "CUS-3001",
  customer_name: "Maya Patel",
  claim_type: "trip_delay",
  submitted_on: "2026-06-24",
  incident_date: "2026-06-18",
  incident_location: "Rome, Italy",
  summary: "Flight home canceled by the airline",
  story: "My flight home from Rome was canceled by Meridian Air.",
  items: [
    {
      description: "Airport hotel, one night",
      category: "accommodation",
      amount: 245,
    },
    { description: "Dinner and breakfast", category: "meals", amount: 95 },
    { description: "Taxis", category: "transport", amount: 80 },
  ],
  amount_claimed: 420,
  documents: [
    {
      name: "Meridian Air cancellation notice",
      type: "carrier_report",
      content: "Flight MA 611 was canceled because of crew availability.",
    },
    { name: "Hotel receipt", type: "receipt", content: "Total paid: $245.00." },
  ],
  status: "waiting",
  decision: null,
  sign_off: null,
  payment: null,
};

export const approvedClaim: Claim = {
  ...claim,
  status: "decided",
  decision: {
    decision: "approve",
    payout: 420,
    reason:
      "The delay was over the waiting period. The receipts total $420.00.",
    policy_section: "Section 3, Trip Delay",
    decided_at: "2026-11-09T22:36:17+00:00",
  },
  payment: { amount: 420, paid_at: "2026-11-09T22:36:20+00:00" },
};

export const heldClaim: Claim = {
  ...claim,
  claim_id: "CLM-1003",
  status: "awaiting_sign_off",
  decision: {
    decision: "approve",
    payout: 1500,
    reason: "The hospital bill is covered.",
    policy_section: "Section 7, Emergency Medical",
    decided_at: "2026-11-09T22:36:17+00:00",
  },
};

export const signedOffClaim: Claim = {
  ...heldClaim,
  status: "decided",
  sign_off: {
    handler_id: "HND-01",
    handler_name: "Dana Whitfield",
    signed_off_at: "2026-11-09T23:00:00+00:00",
  },
  payment: { amount: 1500, paid_at: "2026-11-09T23:00:00+00:00" },
};

export const policy: Policy = {
  policy_id: "POL-2001",
  customer_id: "CUS-3001",
  plan: "premium",
  add_ons: ["electronics_plus"],
  purchased_on: "2026-04-22",
  sold_through: "Meridian Air checkout",
  trip: {
    destination: "Rome, Italy",
    departs_on: "2026-06-10",
    returns_on: "2026-06-18",
    trip_cost: 3100,
  },
  travelers: ["Maya Patel"],
  status: "active",
};

export const customer: Customer = {
  customer_id: "CUS-3001",
  name: "Maya Patel",
  customer_since: "2023-04-11",
  previous_claims: [
    {
      claim_id: "CLM-0412",
      filed_on: "2024-08-19",
      incident_date: "2024-08-09",
      claim_type: "baggage_delay",
      summary: "Checked bag arrived 30 hours late in Lisbon",
      outcome: "approved",
      amount_paid: 140,
    },
  ],
};

export const handlers: Handler[] = [
  {
    handler_id: "HND-01",
    name: "Dana Whitfield",
    role: "Senior Claims Handler",
    can_approve_over_limit: true,
  },
  {
    handler_id: "HND-02",
    name: "Marcus Oyelaran",
    role: "Claims Handler",
    can_approve_over_limit: true,
  },
];

function step(
  step_id: number,
  kind: Step["kind"],
  name: string,
  content: string,
): Step {
  return {
    step_id,
    claim_id: "CLM-1001",
    thread_id: "thread-1",
    kind,
    name,
    content,
    created_at: "2026-11-09T22:36:00+00:00",
  };
}

export const steps: Step[] = [
  step(1, "tool_call", "get_claim", '{"claim_id": "CLM-1001"}'),
  step(2, "tool_result", "get_claim", '{"claim_id":"CLM-1001"}'),
  step(3, "tool_call", "get_policy", '{"policy_id": "POL-2001"}'),
  step(4, "tool_call", "get_customer", '{"customer_id": "CUS-3001"}'),
  step(5, "tool_call", "decide_claim", '{"decision": "approve"}'),
  step(6, "tool_call", "pay_claim", '{"amount": 1500}'),
  step(
    7,
    "tool_result",
    "pay_claim",
    '{"detail":"The payment is held until a handler signs off"}',
  ),
  step(8, "tool_call", "search_web", "{}"),
  step(9, "tool_result", "search_web", "Not JSON at all"),
  step(10, "reply", "", "Approved $1,500.00; waiting for sign-off."),
];

export const queue: ClaimSummary[] = [
  {
    claim_id: "CLM-1001",
    customer_name: "Maya Patel",
    claim_type: "trip_delay",
    summary: "Flight home canceled by the airline",
    submitted_on: "2026-06-24",
    amount_claimed: 420,
    status: "waiting",
    decision: null,
    payout: null,
  },
  {
    claim_id: "CLM-1002",
    customer_name: "Tom Becker",
    claim_type: "baggage",
    summary: "Suitcase lost on a connecting flight",
    submitted_on: "2026-07-20",
    amount_claimed: 1150,
    status: "in_progress",
    decision: null,
    payout: null,
  },
  {
    claim_id: "CLM-1003",
    customer_name: "Ana Souza",
    claim_type: "emergency_medical",
    summary: "Broken wrist in Lisbon",
    submitted_on: "2026-07-08",
    amount_claimed: 3800,
    status: "awaiting_sign_off",
    decision: "approve",
    payout: 3750,
  },
];
