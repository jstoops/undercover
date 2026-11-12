# Status

The pilot from `docs/PLAN.md` is built: all six phases are done.

## How to run it

- `uv sync` and `npm install` install everything.
- `npm run dev` starts the backend on port 8000 and the dashboard at http://localhost:5173. On first start the backend creates and seeds `undercover.db`.
- `uv run -m agent` works every waiting claim in the queue, one after another. `uv run -m agent CLM-1001` works one claim. The backend must be running. Each claim makes a few model calls on your OpenRouter key: `openai/gpt-6-luna` at low reasoning effort, or the model in `MODEL_NAME`.
- `uv run -m backend.seed` resets the queue: every claim goes back to waiting, with no decisions, payments or steps. A decided claim is final, so run this before working the queue again.
- `npm run check` runs every check, including the Playwright tests, which start their own backend (port 8001) and dashboard (port 5174) on a fresh database, so they never touch the queue in `npm run dev`.

## What's built

### `backend/`

FastAPI on SQLite (`undercover.db` at the repo root, or the path in `UNDERCOVER_DB`). The seed (`backend/seed.py`) loads the 25 claims in the queue, the policies, the customers (name, customer-since date and earlier claims only) and the handlers from `data/`. It never reads `data/evals/` or `data/security/`, and no operation serves them. The $1,000 limit comes from `data/company.json`.

Every operation has an `operation_id`, a one-line docstring and no optional inputs, and a test checks this.

| Operation | Route |
|---|---|
| `health` | `GET /api/health` |
| `list_claims` | `GET /api/claims` |
| `get_claim` | `GET /api/claims/{claim_id}` |
| `get_policy` | `GET /api/policies/{policy_id}` |
| `get_customer` | `GET /api/customers/{customer_id}` |
| `get_policy_wording` | `GET /api/policy-wording` |
| `get_instructions` | `GET /api/instructions` |
| `list_handlers` | `GET /api/handlers` |
| `start_claim` | `POST /api/claims/{claim_id}/start` |
| `add_step` | `POST /api/claims/{claim_id}/steps` |
| `list_steps` | `GET /api/claims/{claim_id}/steps` |
| `decide_claim` | `POST /api/claims/{claim_id}/decision` |
| `pay_claim` | `POST /api/claims/{claim_id}/payment` |
| `sign_off_claim` | `POST /api/claims/{claim_id}/sign-off` |

The rules the backend enforces:

- A claim goes from `waiting` to `in_progress` (`start_claim`), then to `decided`, or to `awaiting_sign_off` for an approval over $1,000. A decided claim is final.
- An approval needs a payout above zero. A decline or a referral has a payout of zero.
- `pay_claim` pays only an approved, unpaid claim, and only for the exact payout. Over $1,000 it refuses with a 403 until a handler signs off, whatever the agent does.
- `sign_off_claim` records a handler's sign-off and pays the claim.

### `agent/`

The UnderCover Agent: LangChain's `create_agent` on OpenRouter. Its tools are `get_claim`, `get_policy`, `get_customer`, `decide_claim` and `pay_claim`, and each calls the backend's API and returns its reply, refusals included. `run(claim_id, thread_id)` starts the claim, builds the system prompt from the instructions (`backend/instructions.md`) and the policy wording, both fetched through the API, and posts each tool call, tool result and reply to the backend as a step while it works. `agent/__main__.py` is the `uv run -m agent` command.

### `dashboard/`

React, Vite and React Router in UnderCover's brand (`dashboard/src/styles.css`), following the system's light or dark mode.

- The queue (`/`): a count for each status, which you can click to filter, and the claims with their status, decision and payout. It refreshes every 2 seconds.
- A claim (`/claims/:claimId`): the agent's decision with its reason and policy section; the payment, or the held payment and a sign-off form; the agent's steps as they arrive, in plain words; the claim in full; the policy; and the customer's earlier claims. It refreshes every 2 seconds.
- The instructions (`/instructions`): the agent's instructions, read only, exactly as the agent reads them.

`api.ts` tags each API path with its response type.

### `e2e/`

Playwright tests of the queue, the instructions, a claim in full, the agent's steps arriving and a handler's sign-off. They drive the API the way the agent does and never run a model.

### Other

- `.prettierrc.json` pins Prettier to its defaults, so a Prettier config in a parent folder can't change the repo's formatting.
- Tests never call a model: the agent's tests use a stub model.

## What we've seen from the agent

- On CLM-1001 the agent approves $420.00 under Section 3, Trip Delay, as the wording gives.
- On CLM-1003 it once approved the full $3,800.00 hospital bill, saying no deductible applies to Emergency Medical. On another run it took off the $50 Premium deductible and approved $3,750.00, as section 1 of the wording says. The same claim can come out differently from one run to the next.
- A run of the whole queue gave 16 approvals (3 of them held for sign-off), 5 declines and 4 referrals, so 21 of 25 went straight through.
- On CLM-1013 the agent recorded an approval of $64.00 whose own reason said the 7-hour delay fell short of the Economy plan's 12-hour waiting period. It then tried to record a decline, which the backend refused because a decision is final, and its final reply said the claim was declined. The record (approve $64.00, unpaid) is what counts. `uv run -m agent` prints the outcome from the record, not from the reply, and that is how this was caught.
- The pilot doesn't yet measure the agent's accuracy against the handlers' decisions.

## To do

- Change the agent's instructions (`backend/instructions.md`) to tell it to work the decision out fully, including the payout, before it calls `decide_claim`, because a recorded decision can't be changed. This is the fix for what happened on CLM-1013.
