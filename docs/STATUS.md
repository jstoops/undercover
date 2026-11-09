# Status

The pilot is being built from `docs/PLAN.md`. Phases 1 and 2 of 6 are done.

## What's built

- `backend/`: FastAPI on SQLite (`undercover.db` at the repo root, or the path in `UNDERCOVER_DB`). The backend seeds the database on startup when it's missing. A test checks that every operation has an `operation_id`, a one-line docstring and no optional inputs.
  - Reading: `list_claims`, `get_claim`, `get_policy`, `get_customer`, `get_policy_wording`, `list_handlers`, `get_instructions` and `health`.
  - The workflow: `start_claim`, `add_step`, `list_steps`, `decide_claim`, `pay_claim` and `sign_off_claim`.
  - The agent's instructions are in `backend/instructions.md`.
- `agent/`: still the hello-world skeleton, with one tool that calls the health route.
- `dashboard/`: still the one page that shows whether the backend is up.
- `e2e/`: one test of that page.

The seed loads the 25 claims in the queue, the policies, the customers (name, customer-since date and earlier claims only) and the handlers. It never reads `data/evals/` or `data/security/`.

## The rules the backend enforces

- A claim goes from `waiting` to `in_progress` (`start_claim`), then to `decided`, or to `awaiting_sign_off` for an approval over $1,000. A decided claim is final.
- An approval needs a payout above zero. A decline or a referral has a payout of zero.
- `pay_claim` pays only an approved, unpaid claim, and only for the exact payout. Over $1,000 it refuses with a 403 until a handler signs off.
- `sign_off_claim` records a handler's sign-off and pays the claim.

## How to run it

- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173.
- `uv run -m backend.seed` resets the database: every claim goes back to waiting.
- `npm run check` runs every check.
