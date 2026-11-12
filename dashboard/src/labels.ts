/** The words the dashboard shows for the codes the API returns. */
import type { DecisionKind, RunStatus, Status, TodoStatus } from "./api";

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

export const RUN_LABELS: Record<RunStatus, string> = {
  running: "Running",
  finished: "Finished",
  stopped: "Stopped",
};

export const TODO_LABELS: Record<TodoStatus, string> = {
  pending: "To do",
  in_progress: "In progress",
  completed: "Done",
};

/** The documents the agent looks up, by the name a step gives them. */
export const DOCUMENT_NAMES: Partial<Record<string, string>> = {
  "policy-wording": "Policy wording",
  "claims-manual": "Claims manual",
};

/** The agent's tools, by the name a step gives them. */
export const TOOL_LABELS: Partial<Record<string, string>> = {
  get_claim: "Read the claim",
  get_policy: "Read the policy",
  get_customer: "Read the customer's claim history",
  list_sections: "Looked up the contents",
  read_section: "Read a section",
  decide_claim: "Recorded the decision",
  pay_claim: "Asked to pay",
};
