import { paths } from "./api";
import { useApi } from "./useApi";

function InstructionSet({
  id,
  title,
  text,
}: Readonly<{ id: string; title: string; text: string }>) {
  return (
    <section aria-labelledby={id}>
      <h2 id={id}>{title}</h2>
      <pre className="panel instructions">{text}</pre>
    </section>
  );
}

export function InstructionsPage() {
  const { data, error } = useApi(paths.instructions, false);

  return (
    <section>
      <h1>The agent's instructions</h1>
      <p className="lead">
        What the UnderCover Agent is told, exactly as it reads it. The queue
        agent runs the queue and hands each claim to a claim agent, which looks
        up the sections of the policy wording and the claims manual it needs.
        The instructions are read only.
      </p>
      {error && (
        <p role="alert" className="alert">
          The instructions could not be loaded: {error}
        </p>
      )}
      {data && (
        <>
          <InstructionSet
            id="queue-heading"
            title="Running the queue"
            text={data.queue}
          />
          <InstructionSet
            id="claim-heading"
            title="Working a claim"
            text={data.claim}
          />
        </>
      )}
    </section>
  );
}
