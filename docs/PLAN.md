# Plan: the claims pilot

This plan builds the pilot in `docs/SPEC.md`: a backend that holds the claims queue and enforces the rules, the UnderCover Agent that works the queue through the backend's API, and a dashboard where the handlers watch the agent and sign off large payouts. It follows `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md`, `docs/PROCESS.md` and `docs/BRAND.md`.

There are six phases. The first two build the backend, the third the agent, the fourth and fifth the dashboard, and the sixth runs the whole pilot with the real model.

## How it fits together

```
 data/*.json ──seed──▶ SQLite (undercover.db)
                            ▲
                            │  every read and write
                   FastAPI backend (port 8000) ── enforces the $1,000 sign-off rule
                    ▲                    ▲
     HTTP (tools,   │                    │  HTTP via the Vite proxy, polled every 2 seconds
     instructions,  │                    │
     steps)         │                    │
  UnderCover Agent ─┘                    └─ Dashboard (React, port 5173)
  uv run -m agent                           queue, claim page, instructions, sign-off
```

A claim moves through four states, which the dashboard shows as Waiting, In progress, Waiting for sign-off and Decided:

```
waiting ──start_claim──▶ in_progress ──decide_claim──▶ decided
                                       (decline, refer, or approve up to $1,000)
                                    └──decide_claim──▶ awaiting_sign_off ──sign_off_claim (pays)──▶ decided
                                       (approve over $1,000)
```

## Key choices, and why

- **SQLite through Python's built-in `sqlite3`, with plain SQL.** It needs no new dependency and the queries are simple. Nested parts of a record, such as a claim's items and documents, are stored as JSON text. The database is `undercover.db` at the repo root (already ignored by git), or the path in `UNDERCOVER_DB`. The backend seeds it on startup if it's missing, and `uv run -m backend.seed` resets it.
- **The seed reads only what the pilot needs.** It reads `claims.json`, `policies.json`, `customers.json` and `handlers.json`, and the $1,000 limit comes from `company.json`. It never reads `data/evals/` or `data/security/`, and no API operation serves them, so the agent has no path to the answer key. For customers it keeps only the name, the customer-since date and the claim history. Contact details, dates of birth and addresses are personal data the pilot doesn't need.
- **The backend enforces the sign-off rule, not the agent.** The agent's instructions tell it about the rule, but the backend refuses the payment (HTTP 403) on any approval over $1,000 until a handler signs off, whatever the agent does. A payment must also match the approved payout to the cent and can be made only once, so it can't be split or changed to slip under the limit. A handler's sign-off records the payment. An approval of exactly $1,000.00 pays without sign-off, because the rule is "over $1,000".
- **Paying is its own operation that takes the amount,** as `TECH_STACK.md` asks. Deciding a claim and paying it are separate, so the block is a real check on a real payment attempt.
- **The agent's instructions live in the backend** (`backend/instructions.md`, served by `get_instructions`), because the agent may reach its instructions only through the API. The dashboard shows the same text, read only.
- **The policy wording goes in the system prompt.** The agent fetches the instructions and the wording through the API at the start of each claim and puts both in its system prompt. The wording is short enough to fit, and this way the agent always has it, which is more reliable than hoping it calls a tool for it. The pilot uses the full `data/policy_wording.md`.
- **The agent's harness records the steps.** `run()` streams the agent and posts each step (a tool call, a tool result, the final reply) to the backend as it happens. The model doesn't decide what gets logged. The dashboard polls every 2 seconds, which is simple and fast enough for a step that takes a few seconds.
- **Tools return the backend's response, refusals included.** When a payment is blocked, the model sees the backend's message, such as "This payout is over $1,000 and needs a handler's sign-off", and can say so instead of crashing.
- **The end-to-end tests get their own backend and database.** Playwright starts a backend on port 8001 with a freshly seeded database in the system temp folder, and a dashboard on port 5174 that proxies to it. The tests change claims (they decide and sign off), so they must not touch the queue you're using in `npm run dev`, and they need fresh data on every run.
- **React Router for the three pages** (`/`, `/claims/:claimId`, `/instructions`). It's the standard choice and one small dependency, so we don't hand-write routing.
- **Money is in dollars with cents.** The backend rounds amounts to cents and compares them in cents, and the dashboard shows them as `$1,250.00`.

## The API

Every operation has an `operation_id`, a one-line docstring and no optional inputs. A test checks this for the whole API.

| Operation | Route | What it does |
|---|---|---|
| `health` | `GET /api/health` | Already there |
| `list_claims` | `GET /api/claims` | The queue: each claim's id, customer name, type, summary, dates, amount claimed, status, decision and payout |
| `get_claim` | `GET /api/claims/{claim_id}` | The claim in full, with its decision, sign-off and payment |
| `get_policy` | `GET /api/policies/{policy_id}` | The policy: plan, add-ons, purchase date, trip and travelers |
| `get_customer` | `GET /api/customers/{customer_id}` | The customer's name, customer-since date and earlier claims |
| `get_policy_wording` | `GET /api/policy-wording` | The policy wording, as Markdown |
| `get_instructions` | `GET /api/instructions` | The agent's instructions |
| `list_handlers` | `GET /api/handlers` | The three handlers, for the sign-off |
| `start_claim` | `POST /api/claims/{claim_id}/start` | Marks the claim in progress |
| `add_step` | `POST /api/claims/{claim_id}/steps` | Records one of the agent's steps: thread id, kind, name and content |
| `list_steps` | `GET /api/claims/{claim_id}/steps` | The agent's steps on the claim, oldest first |
| `decide_claim` | `POST /api/claims/{claim_id}/decision` | Records the decision, payout, reason and policy section |
| `pay_claim` | `POST /api/claims/{claim_id}/payment` | Pays the approved payout; takes the amount |
| `sign_off_claim` | `POST /api/claims/{claim_id}/sign-off` | A handler signs off an approval over $1,000, which pays it; takes the handler id |

## Not in the pilot

Following the spec's "Not for now" and `AGENTS.md`'s rule against building ahead:

- The claims manual, sign-in, real payments and messages to customers.
- Scoring the agent against `data/evals/` (evaluations come in a later build). Nothing in this build opens that folder.
- The security claim CLM-1901, the held-out claims, `knowledge.json` and the short policy wording.
- Running the agent from the dashboard. You run it from the terminal with `uv run -m agent`.
- Editing the instructions, and handlers deciding referred claims themselves.

---

## Phase 1: The backend's records

**What it builds.** The database, the seed and the read operations, which give the agent and the dashboard something to work from.

- `backend/db.py`: the connection (a FastAPI dependency, so tests can point it at a temporary database) and the schema. The tables are `claims`, `policies`, `customers`, `handlers`, `decisions`, `sign_offs`, `payments` and `steps`. Decisions, sign-offs and payments are separate tables so each is its own record, with a timestamp.
- `backend/seed.py`: `uv run -m backend.seed` recreates the database from `data/`, with every claim `waiting`, and prints what it loaded. The backend calls the same seed on startup when the database file is missing, so `npm run dev` works on a fresh clone.
- The read operations: `list_claims`, `get_claim`, `get_policy`, `get_customer`, `get_policy_wording` and `list_handlers`, with Pydantic response models. An unknown id gives 404.
- A shared pytest fixture in a root `conftest.py` that seeds a temporary database and gives a `TestClient`. The agent's tests use it too.
- A test that walks `app.openapi()` and checks every operation has an `operation_id`, a one-line docstring and only required inputs.

**Success criteria**

- [x] `uv run -m backend.seed` creates `undercover.db` and reports 25 claims, 50 policies, 49 customers and 3 handlers
- [x] With the backend running, `GET /api/claims` returns 25 claims, CLM-1001 to CLM-1025, all with status `waiting` and no decision. No CLM-11xx or CLM-1901 appears
- [x] `GET /api/claims/CLM-1001` returns the story, 3 items, 4 documents, `amount_claimed` 420.0, status `waiting`, and null decision, sign-off and payment
- [x] `GET /api/policies/POL-2001` returns plan `premium`, no add-ons, the Rome trip from 2026-06-10 to 2026-06-18 with trip cost 3100.0, and traveler Maya Patel
- [x] `GET /api/customers/CUS-3001` returns Maya Patel, customer since 2023-04-11, with one earlier claim, CLM-0412. The response has no email, phone, date of birth or address
- [x] `GET /api/policy-wording` returns the text of `data/policy_wording.md`
- [x] `GET /api/handlers` returns Dana Whitfield, Marcus Oyelaran and Priya Raman
- [x] `GET /api/claims/CLM-9999`, `/api/policies/POL-9999` and `/api/customers/CUS-9999` each return 404
- [x] Deleting `undercover.db` and starting the backend creates and seeds it again
- [x] The OpenAPI test passes: every operation has an `operation_id`, a one-line docstring and no optional inputs
- [x] A search of `backend/` and `agent/` for `evals` finds nothing
- [x] `npm run check:python` passes, with coverage of at least 80%

## Phase 2: The backend's workflow

**What it builds.** The operations that change a claim, with the business rules in the backend where the agent can't get around them.

- `backend/instructions.md` and `get_instructions`. The instructions tell the agent:
  - its role
  - to read the claim, the policy and the customer's claim history, and to check the claim against the policy wording: the trip dates, plan, add-ons, waiting periods, limits, exclusions, required documents and the 90-day filing window
  - to approve when the wording covers the claim, decline when it doesn't, and refer when the claim needs judgment or more information, such as a missing document
  - to work out the payout as in section 10 of the wording, in US dollars and cents
  - to record the decision with a two-or-three-sentence reason in plain English and the policy section, such as "Section 5, Baggage and Personal Effects"
  - to pay an approved payout, and that a payout over $1,000 waits for a handler's sign-off, so a refused payment isn't retried
- `start_claim`: moves a claim from `waiting` (or `in_progress`, so a run that crashed can start again) to `in_progress`. Any other state gives 409, so a decided claim is final.
- `add_step` and `list_steps`. A step's kind is `tool_call`, `tool_result` or `reply`.
- `decide_claim`, with `decision` (`approve`, `decline` or `refer`), `payout`, `reason` and `policy_section`. This works only on a claim in progress (409 otherwise). An approval needs a payout above zero, and a decline or referral a payout of zero (422 otherwise). An approval over $1,000 goes to `awaiting_sign_off`, and everything else to `decided`.
- `pay_claim`, with `amount`. It pays only an approved claim that isn't paid yet, for the exact payout (409 otherwise). It refuses an approval over $1,000 that no handler has signed off, with a 403 and the reason. Nothing is recorded when a payment is refused.
- `sign_off_claim`, with `handler_id`. This works only on a claim awaiting sign-off (409 otherwise), by a known handler who can approve over the limit (404 for an unknown handler). It records the sign-off, pays the payout and marks the claim `decided`.

**Success criteria** (each checked with API calls against a freshly seeded backend, and covered by pytest)

- [x] `GET /api/instructions` returns the instructions, which mention the $1,000 sign-off rule
- [x] CLM-1001: `start` gives `in_progress`. `add_step` and then `list_steps` returns that step. Deciding `approve` with 420.00 gives `decided`. Paying 420.00 records a payment with a timestamp. Paying again gives 409
- [x] CLM-1003: deciding `approve` with 1500.00 gives `awaiting_sign_off`. Paying 1500.00 gives 403 with a message about sign-off. Paying 900.00 is also refused. `get_claim` shows no payment
- [x] CLM-1003: `sign_off_claim` with HND-01 gives `decided`, with a sign-off by HND-01 and a payment of 1500.00. Paying again afterwards gives 409
- [x] An approval of exactly 1000.00 goes straight to `decided` and pays without sign-off
- [x] A decline and a referral each give `decided` with payout 0, and paying either gives 409
- [x] State checks: deciding a `waiting` claim gives 409, starting a `decided` claim gives 409, signing off a claim that isn't awaiting sign-off gives 409, and signing off with HND-99 gives 404
- [x] Input checks: approving with payout 0, declining with a payout above 0, and the decision `maybe` each give 422
- [x] `GET /api/claims` shows each claim's new status, decision and payout
- [x] The OpenAPI test still passes for the new operations
- [x] `npm run check:python` passes, with coverage of at least 80%

## Phase 3: The UnderCover Agent

**What it builds.** The agent that works the queue, replacing the hello-world tool.

- Tools that call the backend: `get_claim`, `get_policy`, `get_customer`, `decide_claim` and `pay_claim`. Each returns the backend's JSON response, including a refusal.
- `run(claim_id, thread_id)` stays the one entry point. It calls `start_claim`, fetches the instructions and the policy wording through the API and builds the system prompt from them. Then it streams the agent and posts each tool call, tool result and final reply to `add_step` as it happens, and returns the final reply.
- `agent/__main__.py`: `uv run -m agent` works every `waiting` claim in queue order, with a new thread id for each, and prints each claim's id and outcome. `uv run -m agent CLM-1001` works one claim.
- The backend URL becomes `http://127.0.0.1:8000`, to match the dashboard's proxy. On Windows, `localhost` can resolve to IPv6, where uvicorn isn't listening.
- The model stays as it is: `openai/gpt-6-luna` at low reasoning effort, or `MODEL_NAME` when set.

**Success criteria**

- [x] The pytest tests with a stub model (none call a real model) show that:
  - for an approval up to $1,000, the claim ends `decided` and paid, and the steps are recorded in order: tool calls, tool results and the reply
  - for an approval over $1,000, the payment is refused, the refusal reaches the model as a tool result, the claim ends `awaiting_sign_off` and no payment is recorded
  - for a decline, the claim ends `decided` with no payment
  - the system prompt holds the instructions and the policy wording, both fetched through the API
  - `uv run -m agent` with no argument picks only the `waiting` claims, and with a claim id runs just that one
- [x] The agent's code reaches the backend only over HTTP. It imports nothing from `backend/` and reads no files from `data/`
- [x] With `npm run dev` running, `uv run -m agent CLM-1001` (one real model call chain, about a cent) ends with CLM-1001 `decided`. `GET /api/claims/CLM-1001/steps` lists calls to `get_claim`, `get_policy`, `get_customer` and `decide_claim` with their results, and the decision has a two-or-three-sentence reason and a policy section. By the wording, this claim should be an approval of $420.00 under Section 3, Trip Delay
- [x] `uv run -m backend.seed` resets CLM-1001 to `waiting`
- [x] `npm run check:python` passes, with coverage of at least 80%

## Phase 4: The dashboard's look, the queue and the instructions

**What it builds.** The dashboard's frame in UnderCover's brand, and the two simpler pages.

- The look, from `docs/BRAND.md` and the layout of its reference stylesheet:
  - Saira Extra Condensed, Roboto and Courier Prime from Google Fonts. Headings are uppercase Saira Extra Condensed, as in the reference. Claim ids, amounts and dates are in Courier Prime, and the tagline is in Roboto
  - a fixed Smoke Tree side nav with the UnderCover name, the tagline and links to Queue and Instructions, which becomes a top bar on narrow screens
  - color tokens in CSS custom properties, with light and dark mode following the system setting: page `#f8f9fa` with white panels, or `#343a40` with black panels
  - rounded panels with no outline, no one-edge borders and no gradients. Smoke Tree and the grays are darkened for text on light backgrounds and lightened on dark ones
  - status colors: Waiting in Dark grayish blue, In progress in Pelorous, Waiting for sign-off in Smoke Tree and Decided in Very dark grayish blue
  - our own small stylesheet, not Bootstrap
- React Router with `/`, `/claims/:claimId` (a placeholder until Phase 5) and `/instructions`.
- `api.ts` with typed functions and types for each operation the dashboard uses, and `format.ts` for money (`$1,250.00`) and dates.
- The queue page: a count for each status, which you can click to show only those claims, and a table with claim id, customer, type, summary, submitted date, amount claimed, status, decision and payout. Each row links to its claim. The page refreshes every 2 seconds, so statuses change as the agent works.
- The instructions page: the instructions text, read only.
- End-to-end isolation: `playwright.config.ts` starts its own backend on port 8001, seeded fresh into a temp-folder database through `UNDERCOVER_DB`, and its own dashboard on port 5174. `vite.config.ts` reads the proxy target from `UNDERCOVER_API`, with port 8000 as the default. The health page and its test give way to the queue.

**Success criteria**

- [x] vitest tests cover the queue's rows, counts and filter, the status labels, money and date formatting and the instructions page, all against a stubbed `fetch`
- [x] Playwright: the queue shows 25 claims and "Waiting 25". Clicking CLM-1001 opens `/claims/CLM-1001`. The instructions page shows the instructions with no editable field
- [x] Playwright: after a claim is started through the API, the queue shows it as In progress without a reload
- [x] With `npm run dev` running, `npm run e2e` passes and leaves the dev queue untouched (still 25 waiting)
- [x] Checked in the browser with the Playwright MCP server at `localhost:5173`, light and dark mode: the fonts are Saira Extra Condensed, Courier Prime and Roboto (by computed style), the side nav is Smoke Tree, the panels are rounded with no outline, the status colors match the brand, and there are no console errors
- [x] At 390 pixels wide the side nav becomes a top bar and the table scrolls inside its panel, not the whole page
- [x] `npm run check:ts` passes, with coverage of at least 80%

## Phase 5: The claim page, the agent's steps and sign-off

**What it builds.** The page where a handler sees a claim in full, watches the agent work and signs off a large payout.

- The header: claim id, status, summary and type.
- The claim: the story, incident date and place, submitted date, a table of items with amounts, the amount claimed, and each document's name, type and text.
- The policy: plan, add-ons, purchase date, destination, trip dates, trip cost and travelers. The customer: name, customer since, and earlier claims with date, type, summary, outcome and amount paid.
- The agent's decision: approve, decline or refer, the payout, the reason, the policy section and when it was decided. Then the payment: paid (amount and date), held until a handler signs off, or none.
- Sign-off, shown only while the claim waits for it: a choice of handler and a "Sign off and pay" button. After sign-off it shows who signed off and when.
- The agent's steps, oldest first and updating live: each tool call has a plain label, such as "Read the claim", "Read the policy", "Read the customer's claim history", "Recorded the decision" or "Asked to pay", with the raw input and the result in a collapsible detail. The final reply is shown in full.
- The page polls the claim and its steps every 2 seconds.

**Success criteria**

- [x] vitest tests cover each section, the empty states (no decision yet, no steps yet), the step labels and the sign-off request, against a stubbed `fetch`
- [x] Playwright: the CLM-1002 page shows the story, 6 items, the amount claimed of $1,150.00, 3 documents, the policy and the customer's history
- [x] Playwright: with the CLM-1005 page open, the test starts the claim and adds steps through the API, the way the agent does. The steps appear in order without a reload, and after the test records a decision, the decision and its reason appear
- [x] Playwright: a claim approved at $1,500.00 through the API, whose payment is then refused with a 403, shows "Waiting for sign-off" and that the payment is held. Choosing Dana Whitfield and pressing "Sign off and pay" changes it to Decided, paid $1,500.00 and signed off by Dana Whitfield, and the queue shows it as Decided
- [x] Checked in the browser with the Playwright MCP server, light and dark mode: a decided claim, a claim waiting for sign-off and a claim with steps all read clearly, with no console errors
- [x] `npm run check:ts` passes, with coverage of at least 80%

## Phase 6: The pilot, end to end

**What it builds.** Nothing new. It runs the real agent through the real dashboard, then hands the pilot over.

- Run the agent with the real model on two claims while watching the dashboard with the Playwright MCP server, then reseed.
- Bring `docs/STATUS.md` up to date: what's built, how to run it (`npm run dev`, `uv run -m agent`, `uv run -m backend.seed`, `npm run check`) and the API in brief.

**Success criteria**

- [ ] With `npm run dev` running and the CLM-1001 page open in the Playwright MCP browser, `uv run -m agent CLM-1001` shows the status go from In progress to Decided. The steps appear while the agent works, and the decision, reason and policy section appear at the end
- [ ] `uv run -m agent CLM-1003` (a $3,800.00 hospital bill on a Premium policy) runs. If the agent approves it, as the wording suggests, its payment is refused, the claim shows Waiting for sign-off in the queue and on its page, and signing off in the browser pays it. If the agent decides otherwise, the decision and reason are shown, and the block was already proven in Phases 2, 3 and 5
- [ ] `uv run -m backend.seed` resets the queue to 25 waiting claims
- [ ] `docs/STATUS.md` describes the pilot and how to run it
- [ ] `npm run check` passes in full: ruff, pyright, pytest with at least 80% coverage, ESLint, Prettier, tsc, vitest with at least 80% coverage, and Playwright

Running the whole queue with `uv run -m agent` is left to you, since it makes 25 claims' worth of model calls on your key. Reseed afterwards to start again.
