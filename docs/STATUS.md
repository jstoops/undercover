# Status

The pilot is being built from `docs/PLAN.md`. Phase 1 of 6 is done.

## What's built

- `backend/`: FastAPI on SQLite (`undercover.db` at the repo root, or the path in `UNDERCOVER_DB`). The backend seeds the database on startup when it's missing. Its read operations are `list_claims`, `get_claim`, `get_policy`, `get_customer`, `get_policy_wording` and `list_handlers`, plus `health`. A test checks that every operation has an `operation_id`, a one-line docstring and no optional inputs.
- `agent/`: still the hello-world skeleton, with one tool that calls the health route.
- `dashboard/`: still the one page that shows whether the backend is up.
- `e2e/`: one test of that page.

The seed loads the 25 claims in the queue, the policies, the customers (name, customer-since date and earlier claims only) and the handlers. It never reads `data/evals/` or `data/security/`.

## How to run it

- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173.
- `uv run -m backend.seed` resets the database: every claim goes back to waiting.
- `npm run check` runs every check.
