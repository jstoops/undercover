# Tech stack

- `backend/`: FastAPI and SQLite, with a router for each part of the API. Every API operation has an `operation_id`, a one-line docstring and no optional inputs. Paying a claim is a separate operation that takes the amount. The policy wording and the claims manual are served by numbered section, never whole.
- `agent/`: two agents, both built with LangChain's `create_agent` and its middleware on OpenRouter, and no other agent framework.
  - The modules: `api.py` (the backend's API), `tools.py` (every tool), `harness.py` (the model, the middleware and the two agents) and `__main__.py` (the command).
  - The queue agent, `harness.run_queue(cap, model)`, plans a run as a to-do list with LangChain's `TodoListMiddleware` and hands each claim to the claim agent. Its tools read the run's state through `context_schema=RunContext` and `ToolRuntime`.
  - The claim agent, `harness.work_claim(claim_id, model)`, works one claim from a clean start and reports back in one line.
  - The middleware:
    - retries model calls (`ModelRetryMiddleware`) and backend calls (`ToolRetryMiddleware`)
    - turns a backend refusal into a message for the model (`ToolErrorMiddleware`)
    - limits a claim agent's model calls (`ModelCallLimitMiddleware`)
    - records each step and saves each to-do list, with hooks of our own (`RecordSteps`, `ShowProgress`)
    - checks for missed claims before the queue agent finishes, with our own `after_model` hook (`MissedClaimsCheck`)
  - The agents reach claims, the documents and their instructions only through the backend's API.
  - They use `z-ai/glm-5.3-flash` with low reasoning effort by default, or the model in the environment variable `MODEL_NAME` if set, such as `openrouter/free`. They skip the OpenRouter providers listed in `OPENROUTER_IGNORE`, which is `wafer` when not set.
- `dashboard/`: React, Vite and TypeScript.
- `e2e/`: Playwright tests.
- `data/`: the business data the backend starts from. The agent never sees `data/evals/`, which holds the answer key.

Python 3.12 with uv, all in the root `pyproject.toml`. Node 26. The OpenRouter key is `OPENROUTER_API_KEY` in `.env`, where `MODEL_NAME` and `OPENROUTER_IGNORE` can also go.
