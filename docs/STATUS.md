# Status

The pilot from `docs/PLAN.md` and the harness from `docs/PLAN_HARNESS.md` are built: all six phases of the pilot and all five of the harness are done. The UnderCover Agent now works the whole queue in one run: a queue agent plans the run as a to-do list and hands each claim to a fresh claim agent, which looks up the sections of the policy wording and the claims manual it needs. Failures are put right without stopping the run.

## How to run it

- `uv sync` and `npm install` install everything.
- `npm run dev` starts the backend on port 8000 and the dashboard at http://localhost:5173. On first start the backend creates and seeds `undercover.db`.
- `uv run -m agent` starts a run of the queue agent on every waiting claim. `uv run -m agent --cap 5` works up to five and leaves the rest waiting, which keeps a trial cheap. Each prints a line per claim, such as "CLM-1001: approve $420.00, paid", then the run's summary. `uv run -m agent CLM-1001` works one claim with the claim agent alone. The backend must be running. Each claim makes several model calls on your OpenRouter key: `z-ai/glm-5.3-flash` at low reasoning effort, or the model in `MODEL_NAME`.
- `OPENROUTER_IGNORE` in `.env` lists the OpenRouter providers to skip, separated by commas. It defaults to `wafer`, which ignored GLM 5.3 Flash's low reasoning setting in the Week 1 Day 4 lab. Set it to nothing to skip none.
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
| `list_sections` | `GET /api/documents/{document}/sections` |
| `read_section` | `GET /api/documents/{document}/sections/{number}` |
| `get_instructions` | `GET /api/instructions` |
| `list_handlers` | `GET /api/handlers` |
| `start_claim` | `POST /api/claims/{claim_id}/start` |
| `add_step` | `POST /api/claims/{claim_id}/steps` |
| `list_steps` | `GET /api/claims/{claim_id}/steps` |
| `fail_claim` | `POST /api/claims/{claim_id}/failure` |
| `decide_claim` | `POST /api/claims/{claim_id}/decision` |
| `pay_claim` | `POST /api/claims/{claim_id}/payment` |
| `sign_off_claim` | `POST /api/claims/{claim_id}/sign-off` |
| `start_run` | `POST /api/runs` |
| `get_current_run` | `GET /api/runs/current` |
| `save_todos` | `PUT /api/runs/{run_id}/todos` |
| `finish_run` | `POST /api/runs/{run_id}/finish` |

The rules the backend enforces:

- A claim goes from `waiting` to `in_progress` (`start_claim`), then to `decided`, or to `awaiting_sign_off` for an approval over $1,000. A decided claim is final. Only a waiting claim can be started, so two agents never work the same claim.
- `fail_claim` records what went wrong on a claim in progress as an `error` step. The claim goes back to `waiting` the first time and to `left_for_handler` the second, and its `failures` count goes up. A claim with a decision can't fail, so no claim is decided or paid twice.
- An approval needs a payout above zero. A decline or a referral has a payout of zero.
- `pay_claim` pays only an approved, unpaid claim, and only for the exact payout. Over $1,000 it refuses with a 403 until a handler signs off, whatever the agent does.
- `sign_off_claim` records a handler's sign-off and pays the claim.
- A run has a cap, a status (`running`, `finished` or `stopped`), its times, its to-do list and a summary. `start_run` marks any earlier run that is still running as stopped, and fails every claim left in progress with "The run stopped before this claim was decided". `save_todos` and `finish_run` work only on a running run.
- `save_todos` takes the queue agent's to-do list with its statuses: `pending`, `in_progress` or `completed`. `get_current_run` shows each item as `to_do`, `in_progress`, `done` or `left_for_handler`. A completed item is left for a handler when the claim named in it (such as "CLM-1004: …") was referred or failed twice, and done otherwise, including for an approval waiting for sign-off.

The documents (`backend/documents.py`): `list_sections` and `read_section` serve the policy wording (`policy-wording`) and the claims manual (`claims-manual`) by their numbered `## N. Title` sections. A section's topics are the bold lead-ins of its paragraphs and list items, such as "Wild animals" in section 7 of the manual. The whole wording is no longer served.

### `agent/`

The UnderCover Agent: LangChain's `create_agent` on OpenRouter. `agent/main.py` holds what the agents share: the backend client, the model and the model retries.

The claim agent (`agent/claim_agent.py`) works one claim. Its tools are `get_claim`, `get_policy`, `get_customer`, `list_sections`, `read_section`, `decide_claim` and `pay_claim`, and each calls the backend's API and returns its reply, refusals included. Its system prompt is its instructions (`backend/instructions/claim.md`, fetched through the API), and it looks up the sections of the wording and the manual it needs.

- `try_claim(claim_id)` starts the claim and runs a new claim agent on a new thread, which posts each tool call, tool result and reply to the backend as a step. Then it returns one line built from the claim's record, not from the model's reply.
- Its middleware retries a model call that fails, such as a provider error or a 120-second timeout, up to 3 times. It retries a backend call that can't connect or times out up to 2 times, and stops a claim agent after 30 model calls.
- If the claim agent still raises an error, or finishes without recording a decision, `try_claim` calls `fail_claim` and says so in its line. One bad claim never stops the run.

The queue agent (`agent/queue_agent.py`) runs the queue. `run_queue(cap)` starts a run and gives the agent its instructions (`backend/instructions/queue.md`) and its cap.

- Its tools are `list_waiting_claims` and `work_claim`, which calls `try_claim` and reports back in one line.
- LangChain's `TodoListMiddleware` gives it `write_todos` with our own tool description, and the harness saves each new list to the backend for the dashboard.
- `work_claim` enforces the cap: it counts the different claims the run has started, under a lock in case of parallel calls. A second try of the same claim counts once.
- The missed-claims check (`MissedClaimsCheck`, an `after_model` hook) runs when the agent replies without calling a tool. If a claim the run tried is back in the queue, or claims are waiting and the run is under its cap, it sends the agent back with a message naming them. It does this at most 3 times a run.
- The agent's final reply is the run's summary. If the queue agent fails after its retries, the run is marked stopped with the error.

`agent/__main__.py` is the `uv run -m agent` command.

Both sets of instructions are written from the policy wording and the claims manual alone, never from the handlers' decisions. The claim instructions follow the manual's order of work, name the sections every claim needs, and tell the agent to work its decision out in full, including the payout, before it calls `decide_claim`. The queue instructions tell the agent how to keep its to-do list (each item starts with its claim id), to try a claim again when it comes back to the queue, to check the queue before it finishes, and what the summary holds.

### `dashboard/`

React, Vite and React Router in UnderCover's brand (`dashboard/src/styles.css`), following the system's light or dark mode.

- The queue (`/`): the current run, with its status, cap, to-do list (To do, In progress, Done or Left for a handler) and summary; a count for each status (Waiting, In progress, Waiting for sign-off, Decided and Left for a handler, in Bright red), which you can click to filter, and the claims with their status, decision and payout. It refreshes every 2 seconds.
- A claim (`/claims/:claimId`): the agent's decision with its reason and policy section; the payment, or the held payment and a sign-off form; what the agent read, such as "Claims manual, 7. Interpretation notes"; the agent's steps as they arrive, in plain words, such as "Read the claims manual, section 7", and any failure as "Failed: …"; the claim in full; the policy; and the customer's earlier claims. It refreshes every 2 seconds.
- The instructions (`/instructions`): the queue agent's ("Running the queue") and the claim agent's ("Working a claim"), read only, exactly as the agents read them.

`api.ts` tags each API path with its response type.

### `e2e/`

Playwright tests of the queue, the instructions, a claim in full, the agent's steps arriving, what the agent read, a claim left for a handler, a handler's sign-off and a run's to-do list filling in. `e2e/run.spec.ts` is the only test that starts a run. They drive the API the way the agent does and never run a model.

### Other

- `.prettierrc.json` pins Prettier to its defaults, so a Prettier config in a parent folder can't change the repo's formatting.
- Tests never call a model: the agent's tests use a stub model.

## What we've seen from the agent

### In the pilot, on GPT-6 Luna with the whole wording in its prompt

- On CLM-1001 the agent approved $420.00 under Section 3, Trip Delay, as the wording gives.
- On CLM-1003 it once approved the full $3,800.00 hospital bill, saying no deductible applies to Emergency Medical. On another run it took off the $50 Premium deductible and approved $3,750.00, as section 1 of the wording says. The same claim can come out differently from one run to the next.
- A run of the whole queue gave 16 approvals (3 of them held for sign-off), 5 declines and 4 referrals, so 21 of 25 went straight through.
- On CLM-1013 the agent recorded an approval of $64.00 whose own reason said the 7-hour delay fell short of the Economy plan's 12-hour waiting period. It then tried to record a decline, which the backend refused because a decision is final, and its final reply said the claim was declined. The record (approve $64.00, unpaid) is what counts. The outcome printed from the record, not from the reply, is how this was caught. The claim instructions now tell the agent to work its decision out in full before it calls `decide_claim`.

### With the harness, on GLM 5.3 Flash looking sections up

- CLM-1020 (sunglasses taken by a monkey) was approved for $240.00 and paid. The agent read the contents of both documents, then sections 1 and 5 of the wording and sections 5, 6 and 7 of the manual. Its reason treats the loss as caused by a wild animal, not as theft, as the manual's note says. It skipped some of the sections the instructions say every claim needs (sections 9 to 11 of the wording and sections 2 and 9 of the manual).
- A run capped at 2 chose the two claims submitted earliest and approved CLM-1001 ($420.00, paid) and CLM-1008 ($2,240.00, waiting for sign-off). It ticked off its to-do list, wrote a summary and left 23 claims waiting.
- The acceptance run, `uv run -m agent --cap 5` after a reseed, worked five claims on its own in 166 seconds and 60 model calls, with no failures:
  - CLM-1001 approve $420.00, paid; CLM-1008 approve $2,240.00 and CLM-1011 approve $1,150.00, both waiting for sign-off; CLM-1010 and CLM-1015 declined.
  - The to-do list appeared on the queue page with the five claims and "Write the summary", and was ticked off one item at a time. The run finished with its summary, and 20 claims stayed waiting, none in progress.
  - Each claim's page showed what the agent read, from 3 sections (CLM-1015) to 9 (CLM-1008), and its steps.
  - It mostly chose the claims submitted earliest, but took CLM-1010 (July 2) and CLM-1015 ahead of CLM-1018 (July 1).
  - Its summary came out in Markdown, which the dashboard shows as written, with `**` marks, so the queue instructions now ask for plain text.
- A second acceptance run, after a reseed, with the plain-text instruction: the same five claims came out the same way, in 115 seconds and 54 model calls, and the summary was plain text. All 54 calls ran on GLM 5.3 Flash, served by InferenceNet (19), Crusoe (16), Together (9), OpenInference (7), Venice, Parasail and Reka (1 each), and none by Wafer. Reasoning came to at most 270 tokens a call, 21 on average. OpenRouter's generation API reports the provider for each call by its id.
- The agent's accuracy against the handlers' decisions isn't measured yet.
