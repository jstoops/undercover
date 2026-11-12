import type { Step } from "./api";
import { time } from "./format";
import { TOOL_LABELS } from "./labels";
import { documentName, field, parse } from "./steps";

function refusal(value: unknown): string | null {
  const detail = field(value, "detail");
  return typeof detail === "string" ? detail : null;
}

/** A tool call in plain words, naming the document for a lookup. */
function callLabel(step: Step, value: unknown): string {
  const document = documentName(field(value, "document")).toLowerCase();
  if (step.name === "list_sections")
    return `Looked up the contents of the ${document}`;
  if (step.name === "read_section")
    return `Read the ${document}, section ${String(field(value, "number"))}`;
  return TOOL_LABELS[step.name] ?? step.name;
}

function StepItem({ step }: Readonly<{ step: Step }>) {
  const value = parse(step.content);
  const label =
    step.kind === "tool_call"
      ? callLabel(step, value)
      : (TOOL_LABELS[step.name] ?? step.name);
  const shown =
    typeof value === "string" ? value : JSON.stringify(value, null, 2);
  const refused = step.kind === "tool_result" ? refusal(value) : null;

  return (
    <li className={`step step-${step.kind}`}>
      <span className="step-time mono">{time(step.created_at)}</span>
      {step.kind === "reply" && (
        <div>
          <span className="step-label">The agent said</span>
          <p className="step-reply">{step.content}</p>
        </div>
      )}
      {step.kind === "error" && (
        <p className="step-error">Failed: {step.content}</p>
      )}
      {(step.kind === "tool_call" || step.kind === "tool_result") && (
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
