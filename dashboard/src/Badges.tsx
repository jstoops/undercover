import {
  DECISION_LABELS,
  STATUS_LABELS,
  type DecisionKind,
  type Status,
} from "./api";

export function StatusBadge({ status }: Readonly<{ status: Status }>) {
  return (
    <span className={`badge status-${status}`}>{STATUS_LABELS[status]}</span>
  );
}

export function DecisionBadge({
  decision,
}: Readonly<{ decision: DecisionKind }>) {
  return (
    <span className={`badge decision-${decision}`}>
      {DECISION_LABELS[decision]}
    </span>
  );
}
