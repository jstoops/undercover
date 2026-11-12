# Code standards

1. Keep it simple, do not overcomplicate.
2. Comments only when necessary.
3. Be concise: a short README and no emojis.
4. IMPORTANT: avoid overly defensive code. Handle exceptions only when necessary.
5. Use uv: ALWAYS `uv run`, NEVER `python3`.
6. TypeScript: strict mode, never `any`.

## Structure

Code is written to be read and reviewed by a person, as a pull request. These rules hold for every change, however small:

7. **One home for each job.** Each module has one job, which its docstring names. A path, a URL, a constant or a rule is written once, in its home, and everything else uses it from there. If a change would mean editing the same string in two places, move it to its home first.
8. **One way to do each thing.** One way to call the backend, one way to answer 404, one way to change a claim's status. When you find a second way, fold it into the first in the same change.
9. **Organize by job, not by feature.** Split code by what it does, such as calling the API, the tools and the harness, not by which feature uses it, such as one module per agent. A module named `main` or `utils` that collects whatever is shared is a sign the split is wrong.
10. **No module reaches into another's internals.** A module uses another's public functions, never its client, its constants or its helpers.
11. **Use the framework's own way first.** Before writing plumbing, read the docs for the version in `uv.lock` or `package-lock.json`, and use what the framework already has.
12. **No test seams in the product.** No parameter that only tests use, and no `value or default()`. Choose dependencies, such as the model, once at the entry point and pass them in, and tests pass stubs the same way.

## The parts

- **The API is called from one module in each part that calls it:** `agent/api.py`, `dashboard/src/api.ts` and `e2e/api.ts`. Nothing else names a path or makes a request.
- **The agent:**
  - `api.py`: every call to the backend.
  - `tools.py`: every tool, for both agents.
  - `harness.py`: the model, the middleware, and building and running the agents.
  - `__main__.py`: the command.
- **LangChain 1.x:**
  - Tools read a run's state through `create_agent(..., context_schema=...)` and a `runtime: ToolRuntime[...]` argument, never through closures.
  - Errors and retries go to middleware (`ToolErrorMiddleware`, `ToolRetryMiddleware`, `ModelRetryMiddleware`).
  - Watching what an agent does is a middleware hook, not code that picks through its stream.
- **The backend:**
  - `main.py` only puts the app together, with one router for each part: `claims.py`, `runs.py` and `records.py`.
  - The rules for working a claim live in `claims.py`, and every change to a claim's status goes through `set_status`.
  - Every `INSERT` names its columns.
- **The dashboard:** `api.ts` holds the API's types, paths and calls, and `labels.ts` holds every word shown for a code the API returns.

## Agent instructions

- **Give the agent a goal, not a script.** Instructions say what the agent is for, what it has to work with and the rules it must keep, and leave the steps to the agent. No numbered steps: if the work is a fixed sequence, it belongs in code.
- **Point to the source, don't copy it.** When the claims manual or the wording sets out how something is done, the instructions send the agent there rather than restating it.
- **Enforce hard rules in code.** A rule that must never be broken, such as sign-off over $1,000, is enforced by the backend. The instructions say it so the agent understands, not to enforce it.
- **When a live run goes wrong, fix the cause.** Ask whether the agent's goal, tools or context are wrong before adding another rule to its instructions.

## Checked automatically

Some of these rules are checked on every commit. Add a check when a review finds a new kind of problem that a check could catch.

- `agent/tests/test_structure.py`: an HTTP client and the API's paths only in `api.py`, tools only in `tools.py`, agents and the model only in `harness.py`.
- `backend/tests/test_structure.py`: a claim's status changes in one place, and every `INSERT` names its columns.
- `test_instructions_give_a_goal_not_a_script` in `backend/tests/test_workflow.py`: each set of instructions has a goal and no numbered steps.
- The ESLint rule in `eslint.config.js`: no API path outside `dashboard/src/api.ts` and `e2e/api.ts`.
