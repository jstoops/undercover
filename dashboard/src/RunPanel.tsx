import { paths, type Run, type RunStatus, type TodoStatus } from "./api";
import { dateTime } from "./format";
import { useApi } from "./useApi";

const RUN_LABELS: Record<RunStatus, string> = {
  running: "Running",
  finished: "Finished",
  stopped: "Stopped",
};

const TODO_LABELS: Record<TodoStatus, string> = {
  to_do: "To do",
  in_progress: "In progress",
  done: "Done",
  left_for_handler: "Left for a handler",
};

function RunDetails({ run }: Readonly<{ run: Run }>) {
  return (
    <>
      <p className="run-meta">
        Started <span className="mono">{dateTime(run.started_at)}</span>, up to{" "}
        {run.cap} {run.cap === 1 ? "claim" : "claims"}
      </p>
      {run.todos.length === 0 ? (
        <p>No to-do list yet.</p>
      ) : (
        <ol className="todos" aria-label="To-do list">
          {run.todos.map((todo) => (
            <li key={todo.position} className="todo">
              <span className={`badge todo-${todo.status}`}>
                {TODO_LABELS[todo.status]}
              </span>
              <span>{todo.content}</span>
            </li>
          ))}
        </ol>
      )}
      {run.summary && (
        <div className="run-summary">
          <h3>Summary</h3>
          <p>{run.summary}</p>
        </div>
      )}
    </>
  );
}

export function RunPanel() {
  const { data: run } = useApi(paths.currentRun);
  return (
    <section className="panel run" aria-labelledby="run-heading">
      <div className="run-header">
        <h2 id="run-heading">This run</h2>
        {run && (
          <span className={`badge run-${run.status}`}>
            {RUN_LABELS[run.status]}
          </span>
        )}
      </div>
      {run === null && <p>The agent hasn't run yet.</p>}
      {run && <RunDetails run={run} />}
    </section>
  );
}
