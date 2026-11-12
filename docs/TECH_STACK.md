# Tech stack

- `backend/`: FastAPI and SQLite. Every API operation has an `operation_id`, a one-line docstring and no optional inputs. Paying a claim is a separate operation that takes the amount. The policy wording and the claims manual are served by numbered section, never whole.
- `agent/`: two agents, both built with LangChain's `create_agent` and its middleware on OpenRouter, and no other agent framework.
  - The queue agent, `run_queue(cap)`, plans a run as a to-do list with LangChain's `TodoListMiddleware` and hands each claim to the claim agent.
  - The claim agent, `try_claim(claim_id)`, works one claim on a fresh thread and reports back in one line.
  - The middleware retries model calls (`ModelRetryMiddleware`) and backend calls (`ToolRetryMiddleware`), and limits a claim agent's model calls (`ModelCallLimitMiddleware`). Our own `after_model` hook checks for missed claims before the queue agent finishes.
  - The agents reach claims, the documents and their instructions only through the backend's API.
  - They use `z-ai/glm-5.3-flash` with low reasoning effort by default, or the model in the environment variable `MODEL_NAME` if set, such as `openrouter/free`. They skip the OpenRouter providers listed in `OPENROUTER_IGNORE`, which is `wafer` when not set.
- `dashboard/`: React, Vite and TypeScript.
- `e2e/`: Playwright tests.
- `data/`: the business data the backend starts from. The agent never sees `data/evals/`, which holds the answer key.

Python 3.12 with uv, all in the root `pyproject.toml`. Node 26. The OpenRouter key is `OPENROUTER_API_KEY` in `.env`, where `MODEL_NAME` and `OPENROUTER_IGNORE` can also go.
