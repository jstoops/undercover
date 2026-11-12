import { paths } from "./api";
import { useApi } from "./useApi";

export function InstructionsPage() {
  const { data, error } = useApi(paths.instructions, false);

  return (
    <section>
      <h1>The agent's instructions</h1>
      <p className="lead">
        What the UnderCover Agent is told before it works a claim, exactly as it
        reads them. The policy wording follows them in its prompt. They are read
        only.
      </p>
      {error && (
        <p role="alert" className="alert">
          The instructions could not be loaded: {error}
        </p>
      )}
      {data && <pre className="panel instructions">{data.instructions}</pre>}
    </section>
  );
}
