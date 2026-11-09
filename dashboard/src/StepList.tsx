import type { Step } from "./api";
import { time } from "./format";

const TOOL_LABELS: Partial<Record<string, string>> = {
  get_claim: "Read the claim",
  get_policy: "Read the policy",
  get_customer: "Read the customer's claim history",
  decide_claim: "Recorded the decision",
  pay_claim: "Asked to pay",
};

function parse(content: string): unknown {
  try {
    return JSON.parse(content);
  } catch {
    return content;
  }
}

function refusal(value: unknown): string | null {
  return typeof value === "object" &&
    value !== null &&
    "detail" in value &&
    typeof value.detail === "string"
    ? value.detail
    : null;
}

function StepItem({ step }: Readonly<{ step: Step }>) {
  const label = TOOL_LABELS[step.name] ?? step.name;
  const value = parse(step.content);
  const shown =
    typeof value === "string" ? value : JSON.stringify(value, null, 2);
  const refused = step.kind === "tool_result" ? refusal(value) : null;

  return (
    <li className={`step step-${step.kind}`}>
      <span className="step-time mono">{time(step.created_at)}</span>
      {step.kind === "reply" ? (
        <div>
          <span className="step-label">The agent said</span>
          <p className="step-reply">{step.content}</p>
        </div>
      ) : (
        <details>
          <summary className={refused ? "step-refused" : undefined}>
            {step.kind === "tool_call" && label}
            {step.kind === "tool_result" &&
              (refused ? `Refused: ${refused}` : `Result: ${label}`)}
          </summary>
          <pre>{shown}</pre>
        </details>
      )}
    </li>
  );
}

export function StepList({ steps }: Readonly<{ steps: Step[] }>) {
  return (
    <section className="panel" aria-labelledby="steps-heading">
      <h2 id="steps-heading">The agent's steps</h2>
      {steps.length === 0 ? (
        <p>No steps yet.</p>
      ) : (
        <ol className="steps" aria-label="Steps">
          {steps.map((step) => (
            <StepItem key={step.step_id} step={step} />
          ))}
        </ol>
      )}
    </section>
  );
}
