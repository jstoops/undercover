import type { ClaimSummary } from "./api";

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
