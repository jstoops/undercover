export type Status =
  | "waiting"
  | "in_progress"
  | "awaiting_sign_off"
  | "decided"
  | "left_for_handler";
export type DecisionKind = "approve" | "decline" | "refer";
export type StepKind = "tool_call" | "tool_result" | "reply" | "error";

export const STATUSES: Status[] = [
  "waiting",
  "in_progress",
  "awaiting_sign_off",
  "decided",
  "left_for_handler",
];

export const STATUS_LABELS: Record<Status, string> = {
  waiting: "Waiting",
  in_progress: "In progress",
  awaiting_sign_off: "Waiting for sign-off",
  decided: "Decided",
  left_for_handler: "Left for a handler",
};

export const DECISION_LABELS: Record<DecisionKind, string> = {
  approve: "Approve",
  decline: "Decline",
  refer: "Refer",
};

export interface ClaimSummary {
  claim_id: string;
  customer_name: string;
  claim_type: string;
  summary: string;
  submitted_on: string;
  amount_claimed: number;
  status: Status;
  failures: number;
  decision: DecisionKind | null;
  payout: number | null;
}

export interface Item {
  description: string;
  category: string;
  amount: number;
}

export interface ClaimDocument {
  name: string;
  type: string;
  content: string;
}

export interface Decision {
  decision: DecisionKind;
  payout: number;
  reason: string;
  policy_section: string;
  decided_at: string;
}

export interface SignOff {
  handler_id: string;
  handler_name: string;
  signed_off_at: string;
}

export interface Payment {
  amount: number;
  paid_at: string;
}

export interface Claim {
  claim_id: string;
  policy_id: string;
  customer_id: string;
  customer_name: string;
  claim_type: string;
  submitted_on: string;
  incident_date: string;
  incident_location: string;
  summary: string;
  story: string;
  items: Item[];
  amount_claimed: number;
  documents: ClaimDocument[];
  status: Status;
  failures: number;
  decision: Decision | null;
  sign_off: SignOff | null;
  payment: Payment | null;
}

export interface Policy {
  policy_id: string;
  customer_id: string;
  plan: string;
  add_ons: string[];
  purchased_on: string;
  sold_through: string;
  trip: {
    destination: string;
    departs_on: string;
    returns_on: string;
    trip_cost: number;
  };
  travelers: string[];
  status: string;
}

export interface PreviousClaim {
  claim_id: string;
  filed_on: string;
  incident_date: string;
  claim_type: string;
  summary: string;
  outcome: string;
  amount_paid: number;
}

export interface Customer {
  customer_id: string;
  name: string;
  customer_since: string;
  previous_claims: PreviousClaim[];
}

export interface Handler {
  handler_id: string;
  name: string;
  role: string;
  can_approve_over_limit: boolean;
}

export interface Step {
  step_id: number;
  claim_id: string;
  thread_id: string;
  kind: StepKind;
  name: string;
  content: string;
  created_at: string;
}

export interface Instructions {
  instructions: string;
}

/** A path in the API, tagged with the type of its response. */
export type ApiPath<T> = string & { readonly response?: T };

export const paths = {
  claims: "/api/claims" as ApiPath<ClaimSummary[]>,
  claim: (id: string) => `/api/claims/${id}` as ApiPath<Claim>,
  steps: (id: string) => `/api/claims/${id}/steps` as ApiPath<Step[]>,
  signOff: (id: string) => `/api/claims/${id}/sign-off` as ApiPath<Claim>,
  policy: (id: string) => `/api/policies/${id}` as ApiPath<Policy>,
  customer: (id: string) => `/api/customers/${id}` as ApiPath<Customer>,
  handlers: "/api/handlers" as ApiPath<Handler[]>,
  instructions: "/api/instructions" as ApiPath<Instructions>,
};

async function request<T>(apiPath: ApiPath<T>, init?: RequestInit): Promise<T> {
  const response = await fetch(apiPath, init);
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      detail?: unknown;
    };
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `The backend answered ${String(response.status)}`,
    );
  }
  return (await response.json()) as T;
}

export function getJson<T>(apiPath: ApiPath<T>): Promise<T> {
  return request(apiPath);
}

export function postJson<T>(apiPath: ApiPath<T>, body: unknown): Promise<T> {
  return request(apiPath, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
