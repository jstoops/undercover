# Status

The pilot is being built from `docs/PLAN.md`. Phases 1 to 5 of 6 are done.

## What's built

- `backend/`: FastAPI on SQLite (`undercover.db` at the repo root, or the path in `UNDERCOVER_DB`). The backend seeds the database on startup when it's missing. A test checks that every operation has an `operation_id`, a one-line docstring and no optional inputs.
  - Reading: `list_claims`, `get_claim`, `get_policy`, `get_customer`, `get_policy_wording`, `list_handlers`, `get_instructions` and `health`.
  - The workflow: `start_claim`, `add_step`, `list_steps`, `decide_claim`, `pay_claim` and `sign_off_claim`.
  - The agent's instructions are in `backend/instructions.md`.
- `agent/`: the UnderCover Agent, LangChain's `create_agent` on OpenRouter (`openai/gpt-6-luna` at low reasoning effort, or `MODEL_NAME`). Its tools are `get_claim`, `get_policy`, `get_customer`, `decide_claim` and `pay_claim`, and each calls the backend's API. `run(claim_id, thread_id)` starts the claim, builds the system prompt from the instructions and the policy wording (both fetched through the API), and posts each tool call, tool result and reply to the backend as a step while it works.
- `dashboard/`: React, Vite and React Router in UnderCover's brand (`dashboard/src/styles.css`), following the system's light or dark mode. The queue page (`/`) shows a count for each status, which you can click to filter, and a table of claims, refreshed every 2 seconds. The instructions page (`/instructions`) shows the agent's instructions, read only. The claim page (`/claims/:claimId`) shows the agent's decision (with the payment, or the held payment and a sign-off form), the agent's steps as they arrive, the claim in full, the policy and the customer's earlier claims; it refreshes the claim and its steps every 2 seconds. `api.ts` tags each API path with its response type.
- `e2e/`: Playwright tests of the queue, the instructions, a claim in full, the agent's steps arriving and a handler's sign-off. They drive the API the way the agent does and never run a model. `playwright.config.ts` starts its own backend on port 8001, with a freshly seeded database in the system temp folder, and its own dashboard on port 5174, so the tests never touch the queue you use in `npm run dev`.
- `.prettierrc.json` pins Prettier to its defaults, so a Prettier config in a parent folder can't change the repo's formatting.

The seed loads the 25 claims in the queue, the policies, the customers (name, customer-since date and earlier claims only) and the handlers. It never reads `data/evals/` or `data/security/`.

## The rules the backend enforces

- A claim goes from `waiting` to `in_progress` (`start_claim`), then to `decided`, or to `awaiting_sign_off` for an approval over $1,000. A decided claim is final.
- An approval needs a payout above zero. A decline or a referral has a payout of zero.
- `pay_claim` pays only an approved, unpaid claim, and only for the exact payout. Over $1,000 it refuses with a 403 until a handler signs off.
- `sign_off_claim` records a handler's sign-off and pays the claim.

## How to run it

- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173.
- `uv run -m agent` works every waiting claim in the queue, and `uv run -m agent CLM-1001` works one claim. The backend must be running. Each claim costs a few model calls on your OpenRouter key.
- `uv run -m backend.seed` resets the database: every claim goes back to waiting. A decided claim is final, so run this before working the queue again.
- `npm run check` runs every check.
