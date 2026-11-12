# Plan: the agent's harness

This plan builds `docs/HARNESS.md`: the UnderCover Agent grows from one claim at a time into a run that works the whole queue on its own. A queue agent plans the run as a to-do list and hands each claim to a fresh claim agent. The claim agent looks up the sections of the policy wording and the claims manual it needs, and failures are put right without stopping the run. It follows `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md`, `docs/PROCESS.md` and `docs/BRAND.md`. `docs/PLAN.md` is the pilot's finished plan and stays as it is.

There are five phases. Each one delivers a feature end to end, across the backend, the agent and the dashboard, so it can be checked in the browser:

1. The claim agent looks things up by section
2. A fresh claim agent for each claim, with failures put right
3. Runs and the to-do list
4. The queue agent
5. A five-claim run on the default model, and the handover

## How it fits together

```
 uv run -m agent --cap 5                                 uv run -m agent CLM-1020
          │                                                        │
 run_queue(cap): the queue agent, on one thread                    │
   tools:      list_waiting_claims, work_claim                     │
   middleware: TodoListMiddleware (write_todos), model retry,      │
               the missed-claims check                             │
   each new to-do list is saved to the backend                     │
          │ work_claim("CLM-1007")                                 │
          ▼                                                        ▼
 try_claim(claim_id): a new claim agent on a new thread for every attempt
   tools:      get_claim, get_policy, get_customer, list_sections, read_section,
               decide_claim, pay_claim
   middleware: model retry, tool retry, a limit of 30 model calls
   returns one line built from the claim's record, such as "CLM-1007: approve $180.00, paid"
          │ every step is posted to the claim
          ▼
 FastAPI backend: runs and their to-do lists, failures, the documents by section,
          ▲        both sets of instructions, and the $1,000 rule as before
          │ polled every 2 seconds
 Dashboard: the queue with the run's to-do list, and the claim page with what the agent read
```

A claim gains one state, Left for a handler:

```
waiting ──start_claim──▶ in_progress ──decide_claim──▶ decided or awaiting_sign_off (as in the pilot)
   ▲                         │
   └── fail_claim (first) ───┤
                             └── fail_claim (second) ──▶ left_for_handler
```

## Key choices, and why

- **Two agents, both built with LangChain's `create_agent` and its middleware.** The brief asks for these pieces in our own agent rather than another framework. Deep Agents is installed for the Day 5 lab, but the product never imports it.
- **The claim agent is called through a tool.** `work_claim` runs `try_claim`, which starts the claim and runs a new claim agent on a new thread. When the claim agent finishes, `try_claim` returns one line, and the code builds that line from the claim's record, not from the model's reply. CLM-1013 showed the reply can disagree with the record. The queue agent never sees a claim's details. Its context grows by about one line per claim, and every claim agent starts empty, so the twentieth claim costs no more than the first.
- **The to-do list comes from LangChain's `TodoListMiddleware`.** It gives the queue agent a `write_todos` tool and keeps the list in the agent's state, with three statuses: pending, in progress and completed. It also refuses two `write_todos` calls in the same turn. The harness already reads the agent's updates as they stream in, so whenever the list changes it saves the new list to the backend for the dashboard. The middleware's own prompt tells the agent to keep a task in progress when it hits an error, which would leave a claim that failed twice in progress forever. So the to-do guidance goes in the queue instructions, where the instructions page shows it. The middleware gets a short tool description of ours in place of its generic one, and an empty prompt of its own.
- **The fourth status, Left for a handler, comes from the claim's record.** Each to-do item starts with its claim id, such as "CLM-1007: phone dropped in the shower". The agent marks an item completed when `work_claim` reports back, whatever the outcome. When the backend serves the run, it shows a completed item as Left for a handler if its claim was referred or failed twice. Otherwise it shows Done, including for an approval waiting for sign-off. An item with no claim id, such as the summary, shows its own status. This way the status always matches the record, which is the lesson of CLM-1013, and the model has one less judgment to make.
  - **Changed after the build:** the to-do list has no fourth status. Showing a referred claim as Left for a handler in the to-do list while the queue counted it as Decided read as a contradiction. So the to-do list shows only the agent's progress (To do, In progress or Done), and the queue alone shows where each claim stands, including waiting for sign-off and left for a handler. This departs from item 2 of `docs/HARNESS.md`, which lists "left for a handler" as a to-do status; our forward deployed engineer decided it. The criteria below about Left for a handler in the to-do list describe the build as it was first done.
- **The code enforces the cap.** `work_claim` counts the different claims this run has started and refuses a new one once the count reaches the cap. A second try of the same claim doesn't count again. The model can call tools in parallel, so the count is taken under a lock. The agent is told its cap, but the code is what holds it.
- **Failures are handled at two levels.**
  - *Within a step:* `ModelRetryMiddleware` retries model provider errors and timeouts, with backoff, up to 3 times. Each model call has a 120-second timeout, so a call that hangs becomes a timeout and is retried. `ToolRetryMiddleware` retries a call to the backend that can't connect or times out. `ModelCallLimitMiddleware` stops a claim agent that goes round in circles after 30 model calls.
  - *A whole claim:* `try_claim` catches any error from the claim agent, and also catches a claim agent that finishes without recording a decision. In either case it calls `fail_claim`. This is the one place the code catches exceptions, and it's what stops one bad claim from stopping the run.
- **The backend owns the retry rule.** `fail_claim` records what went wrong as an `error` step. It sends the claim back to `waiting` the first time and to `left_for_handler` the second. It works only on a claim in progress. Once a decision is recorded, the claim is out of the retry loop, and the backend already refuses a second decision or a second payment, so no claim is decided or paid twice. `start_claim` now accepts only a waiting claim, so two agents can never work the same claim. The pilot let `start_claim` take a claim in progress so that a crashed run could start it again. `start_run` now does that recovery instead: when a run starts, any claim still in progress from a run that died (closed with Ctrl-C, or a crash) counts as a failed attempt, and that run is marked stopped.
- **The missed-claims check is middleware.** When the queue agent replies without calling a tool, it's about to finish. An `after_model` hook then compares the queue with the run's cap. If a waiting claim is still within reach, it adds a message naming those claims and sends the agent back to the model. A claim is within reach if this run already tried it and it's back in the queue, or if it hasn't been touched and the run is under its cap. The instructions tell the agent to check before it finishes, and the middleware makes sure it does. It nudges at most 3 times a run, so a stubborn model can't loop forever.
- **The documents are looked up by section.** Two operations, `list_sections` and `read_section`, work on the policy wording and the claims manual, split at their `## N. Title` headings. The contents list each section's topics, which are the bold lead-ins such as "Wild animals" in section 7 of the manual. That lets the agent find a note inside a long section without reading every section. The whole wording no longer goes into the system prompt, and `get_policy_wording` is removed. There's no search index, because the documents are short and numbered, and a handler uses them the same way: contents first, then the section.
- **Two sets of instructions, written from the wording and the manual alone** (`backend/instructions/claim.md` and `backend/instructions/queue.md`). The claim instructions follow the manual's order of work (section 4). They also take in the CLM-1013 to-do from `docs/STATUS.md`: work the decision out in full, including the payout, before calling `decide_claim`. Nothing in this build opens `data/evals/`.
- **A single named claim skips the queue agent.** `uv run -m agent CLM-1020` calls `try_claim` directly, so it gets the same retries and failure handling with no extra model calls.
- **The model is `z-ai/glm-5.3-flash` at low reasoning effort**, or the model in `MODEL_NAME`, which runs with no reasoning setting, as now. Phase 1 checks that OpenRouter applies the reasoning effort to GLM. If `reasoning_effort` isn't passed through, we send OpenRouter's own `reasoning` setting instead.
- **OpenRouter can be told to skip providers.** In the Week 1 Day 4 lab, Wafer, one of GLM 5.3 Flash's providers, ignored the low reasoning setting and thought for up to 3,000 tokens on a single claim. The lab skipped Wafer with OpenRouter's `provider.ignore` setting, and `model()` does the same for both agents.
  - The providers to skip come from `OPENROUTER_IGNORE` in `.env`, a comma-separated list such as `wafer,another-provider`.
  - When it isn't set, the default is `wafer`, so the default model never reaches Wafer, even on a fresh clone. Setting it to nothing skips no provider.
  - It's a setting like `MODEL_NAME`, so skipping another provider later needs no code change.
- **A run has its own record**: its cap, its status (running, finished or stopped), its times, its to-do list and its summary. The queue agent's final reply becomes the summary. If the queue agent itself fails after its retries, the run is marked stopped, with the error as its summary.
- **The tests use stub models**: a scripted queue agent, a scripted claim agent for each claim, and a stub that raises an error the way a provider does. In tests the retries don't wait.

## Changes to the API

Every operation still has an `operation_id`, a one-line docstring and no optional inputs.

| Operation | Route | What it does |
|---|---|---|
| `list_sections` | `GET /api/documents/{document}/sections` | The contents of `policy-wording` or `claims-manual`: each section's number, title and topics |
| `read_section` | `GET /api/documents/{document}/sections/{number}` | One section's title and text, or 404 if there's no such section |
| `fail_claim` | `POST /api/claims/{claim_id}/failure` | Records what went wrong (thread id and reason) as an `error` step. The claim goes back to waiting the first time and to left for a handler the second. 409 unless the claim is in progress |
| `start_run` | `POST /api/runs` | Starts a run with a cap. Marks any earlier run still running as stopped, and fails the claims it left in progress |
| `get_current_run` | `GET /api/runs/current` | The latest run with its to-do list, or null before the first run. Each item has the status the dashboard shows: to do, in progress, done or left for a handler |
| `save_todos` | `PUT /api/runs/{run_id}/todos` | Saves the queue agent's to-do list as it now stands: each item's text and status (pending, in_progress or completed) |
| `finish_run` | `POST /api/runs/{run_id}/finish` | Records the outcome (finished or stopped) and the summary |

The operations that change a run answer 409 once the run is no longer running.

Changed: `start_claim` accepts only a waiting claim. A claim carries its `failures`. The statuses gain `left_for_handler` and the step kinds gain `error`. `get_instructions` returns the queue agent's and the claim agent's instructions (from Phase 4).

Removed: `get_policy_wording`.

## Not in this build

Following `AGENTS.md`'s rule against building ahead:

- Scoring the agent against `data/evals/`. Evaluations come in a later build, and nothing here opens that folder.
- Durable state, a checkpointer or a LangGraph graph of our own. The run's record is a plain table in the backend.
- Starting or stopping a run from the dashboard. Runs start in the terminal.
- Handlers deciding a claim left for them, or putting it back in the queue. `uv run -m backend.seed` resets the queue.
- A search index or embeddings over the documents, and summarizing the queue agent's conversation. Neither is needed at this size.
- The manual's rules on what a decision record holds (sections 13 and 14: the manual's version and the calculation), letters to customers, the security claim CLM-1901 and the held-out claims.

---

## Phase 1: The claim agent looks things up by section

**What it builds.** The claims manual becomes part of how claims are decided. The agent finds and reads the sections it needs instead of being handed the whole wording, and the claim page shows what it read.

- `backend/documents.py` splits `data/policy_wording.md` and `data/claims_manual.md` at their `## N. Title` headings. A section's topics are the bold lead-ins at the start of its paragraphs and list items.
- `list_sections` and `read_section`, with `document` limited to `policy-wording` or `claims-manual`. `get_policy_wording` is removed.
- The claim agent's tools gain `list_sections` and `read_section`. Its system prompt becomes the instructions alone.
- `backend/instructions.md` moves to `backend/instructions/claim.md` and is rewritten from the wording and the manual. The rewrite covers:
  - the manual's order of work
  - the sections every claim needs: the plan table, the benefit's section, the general exclusions, how the payout is worked out, the documents required and repeat claims
  - using the topics to find the rest
  - when to refer (manual section 2)
  - working the decision out in full before `decide_claim`, because it's final
  - the $1,000 rule
- The default model becomes `z-ai/glm-5.3-flash` at low reasoning effort. `model()` also tells OpenRouter which providers to skip: those in `OPENROUTER_IGNORE`, or Wafer when it isn't set.
- The claim page has a "What the agent read" list, in the order the sections were read, such as "Claims manual, 7. Interpretation notes". The steps gain plain labels, such as "Looked up the contents of the claims manual" and "Read the policy wording, section 5".
- `docs/SPEC.md`: decisions follow the policy wording and the claims manual, with the wording first, and the manual leaves "Not for now". The CLM-1013 to-do leaves `docs/STATUS.md`, since the instructions now cover it.

**Success criteria**

- [x] `GET /api/documents/policy-wording/sections` returns 12 sections, from "1. Your plan" to "12. Definitions", and section 8's topics are Adventure Sports, Pre-Existing Condition Waiver and Electronics Plus
- [x] `GET /api/documents/claims-manual/sections` returns 14 sections, and section 7's topics include Unattended belongings, Wild animals and Pre-existing conditions
- [x] `GET /api/documents/claims-manual/sections/10` returns "Meals without receipts" with the $35 rule and nothing from section 11. Section 15 gives 404, and the document `evals` gives 422
- [x] `GET /api/policy-wording` gives 404
- [x] `GET /api/instructions` returns the new claim instructions, which name `list_sections` and `read_section`, say to work the decision out in full before `decide_claim`, and keep the $1,000 rule
- [x] pytest with a stub model: the claim agent's system prompt is the instructions alone, with no policy wording, and a `read_section` call and its result are recorded as steps on the claim
- [x] `main.model()` names `z-ai/glm-5.3-flash` by default and the model in `MODEL_NAME` when set. The request it would send for the default model carries low reasoning effort in a form OpenRouter accepts, and with `MODEL_NAME` set it carries none
- [x] The request `main.model()` would send skips Wafer by default (`provider.ignore` is `["wafer"]`). With `OPENROUTER_IGNORE=wafer,deepinfra` it skips both. With `OPENROUTER_IGNORE` set to nothing it has no provider setting. This holds with or without `MODEL_NAME`
- [x] vitest: the "What the agent read" list and the new step labels, from stubbed steps
- [x] Playwright: with the CLM-1006 page open, the test posts a `read_section` call and its result through the API. "Claims manual, 7. Interpretation notes" appears under "What the agent read" without a reload
- [x] After `uv run -m backend.seed`, `uv run -m agent CLM-1020` (sunglasses taken by a monkey) runs on the default model. Its steps show it read the contents and section 7 of the manual. Its reason treats the loss as caused by a wild animal, not as theft, as the manual's note says. OpenRouter's activity page shows the calls on GLM 5.3 Flash, and none of them served by Wafer (checked with two calls on the same settings through OpenRouter's generation API, which reported InferenceNet and Reka; the CLM-1020 calls themselves weren't recorded with their ids)
- [x] A search of `backend/` and `agent/` for `evals` finds only the test that the document `evals` is refused
- [x] `docs/SPEC.md` has the manual in its rules and no longer lists it under "Not for now"
- [x] `npm run check:python` and `npm run check:ts` pass, with coverage of at least 80%

## Phase 2: A fresh claim agent for each claim, with failures put right

**What it builds.** The claim agent becomes the subagent that the queue agent will call. It starts clean every time, reports back in a line, and never leaves a claim stuck.

- `fail_claim`, the `failures` count on a claim, the status `left_for_handler` and the step kind `error`. `start_claim` accepts only a waiting claim.
- `agent/claim_agent.py`:
  - the claim agent's tools, and `run_claim(claim_id, thread_id)`, which streams the agent and posts each step as before
  - `ModelRetryMiddleware`, `ToolRetryMiddleware` and a `ModelCallLimitMiddleware` of 30 calls, and a 120-second timeout on each model call
  - `try_claim(claim_id)`, which starts the claim and runs the claim agent on a new thread. If the agent raises an error, or finishes with the claim still in progress, it calls `fail_claim` with the reason. Then it returns one line from the claim's record.
- `agent/main.py` keeps `model()` and the backend client, which both agents share.
- The one-line reports:
  - "CLM-1001: approve $420.00, paid"
  - "CLM-1003: approve $3,750.00, waiting for sign-off"
  - "CLM-1004: decline"
  - "CLM-1006: failed (the model provider timed out), back in the queue for another try"
  - "CLM-1006: failed again (…), left for a handler"
  - "CLM-1004 is decided, so there is nothing to do"
- `uv run -m agent CLM-1001` uses `try_claim` and prints its line.
- Dashboard: the status Left for a handler in Bright red (the brand's fifth color) in the queue's counts and badges. Error steps show as "Failed: …" on the claim page.

**Success criteria**

- [x] API: `fail_claim` on CLM-1001 in progress gives `waiting` with failures 1 and an `error` step holding the reason. Starting and failing it again gives `left_for_handler` with failures 2. Starting it now gives 409
- [x] API: `fail_claim` on a waiting claim or a decided claim gives 409 and changes nothing. `start_claim` on a claim in progress gives 409
- [x] pytest with stub models:
  - a claim agent that approves $420.00 gives "CLM-1001: approve $420.00, paid", with its steps recorded as before
  - a model that raises a provider error once and then works is retried, and the claim is decided
  - a model that always raises leaves the claim waiting with failures 1 and an error step. Doing it a second time leaves the claim left for a handler
  - a claim agent that finishes without deciding counts as a failure
  - a backend call that times out once is retried
  - `try_claim` on a decided claim says so and records nothing
- [x] pytest: a claim agent that fails after recording its decision leaves the decision as it is, with no second decision and no payment
- [x] vitest: the Left for a handler count, badge and filter, and an error step on the claim page
- [x] Playwright: a claim started and failed twice through the API shows Left for a handler in the queue, and both failures appear in its steps
- [x] After `uv run -m backend.seed`, `uv run -m agent CLM-1001` on the default model prints a one-line report that matches the claim's record
- [x] `npm run check:python` and `npm run check:ts` pass, with coverage of at least 80%

## Phase 3: Runs and the to-do list

**What it builds.** The record of a run and its to-do list, and the panel on the queue page that shows them, ready for the queue agent in Phase 4.

- The `runs` and `todos` tables, cleared by the seed. `start_run`, `get_current_run`, `save_todos` and `finish_run`.
- `get_current_run` gives each item the status to show. Pending is To do and in progress is In progress. Completed is Left for a handler when the item's claim was referred or left for a handler, and Done otherwise.
- `start_run` marks any earlier run still running as stopped. It fails each claim left in progress, with the reason "The run stopped before this claim was decided".
- The queue page has a "This run" panel above the counts. It shows the run's status (Running, Finished or Stopped), when it started, its cap ("Up to 5 claims"), and the to-do list in order with each item's status (To do, In progress, Done or Left for a handler). The summary appears when the run ends. Before the first run it says "The agent hasn't run yet". It refreshes every 2 seconds with the rest of the page.

**Success criteria**

- [x] API: before any run, `GET /api/runs/current` returns null. `POST /api/runs` with cap 5 returns a running run with cap 5 and an empty to-do list, and `GET /api/runs/current` returns it
- [x] API: saving three items, and then the same three with item 2 `completed`, gives the three items in order with item 2 done. The status `maybe` gives 422, and so does a cap of 0
- [x] API: completed items for an approved claim, a claim waiting for sign-off, a referred claim and a claim left for a handler show done, done, left for a handler and left for a handler. A completed item with no claim id shows done
- [x] API: `finish_run` with `finished` and a summary records both and the finish time. Saving to-dos or finishing again gives 409
- [x] API: starting a run while an earlier run is running and CLM-1002 is in progress marks the earlier run stopped, and puts CLM-1002 back to waiting with failures 1 and an error step
- [x] `uv run -m backend.seed` clears the runs, to-do lists and failures
- [x] The OpenAPI test passes for the new operations
- [x] vitest: the panel with no run, a running run with its to-do list in each of the four statuses, and a finished run with its summary
- [x] Playwright: with the queue page open, the test starts a run, saves a to-do list and ticks items off through the API, the way the harness will. Each change appears without a reload, an item for a claim the test referred shows Left for a handler, and finishing the run shows the summary
- [x] Checked in the browser with the Playwright MCP server, light and dark mode: the panel reads clearly beside the counts and the table, the four to-do statuses are easy to tell apart, there are no console errors, and at 390 pixels wide it fits without the page scrolling sideways
- [x] `npm run check:python` and `npm run check:ts` pass, with coverage of at least 80%

## Phase 4: The queue agent

**What it builds.** One command that works the whole queue, or a capped part of it: planning, handing claims out, retrying, checking and summing up.

- `agent/queue_agent.py`:
  - `run_queue(cap)` starts a run and runs the queue agent. The first message tells it its cap. It prints each claim's one-line report as it comes back, then the summary, and records the summary with `finish_run`. If the queue agent fails after its retries, the run is marked stopped, with the error as its summary.
  - The tools:
    - `list_waiting_claims`: each waiting claim's id, type, summary, amount, submitted date and failures
    - `work_claim(claim_id)`, which runs `try_claim` and refuses past the cap ("The cap of 5 claims is reached, so CLM-1009 stays waiting")
  - Middleware: `TodoListMiddleware` with our own tool description, `ModelRetryMiddleware`, and the missed-claims check, which nudges at most 3 times.
  - Each time an update from the agent holds a new to-do list, `run_queue` saves it with `save_todos`.
- `backend/instructions/queue.md`, written from the wording and the manual:
  - its role: it organizes the run and doesn't decide claims itself
  - read the queue, choose an order and plan the to-do list within the cap
  - start each item with its claim id, mark it in progress, hand the claim to `work_claim`, and mark it completed when the report comes back, whatever the report says
  - set a claim that comes back to the queue to pending, and try it again later
  - check the queue before finishing
  - finish with a short summary for the handlers: how many were approved, declined and referred, the payouts waiting for sign-off, the referrals and why, and any claims left for a handler and why
- `get_instructions` returns both sets. The instructions page shows "Running the queue" and "Working a claim".
- `uv run -m agent` works every waiting claim (its cap is the number waiting), `uv run -m agent --cap 5` works up to five, and `uv run -m agent CLM-1001` works one.

**Success criteria**

- [x] pytest with stub models for the queue agent and each claim, none calling a real model:
  - *the to-do list is stored:* the queue agent writes a three-item list with `write_todos` and ticks it off, and `GET /api/runs/current` shows each change, ending with the summary
  - *the cap:* with a cap of 2, the third claim is refused, stays waiting with no steps, and the run finishes with 2 claims worked. Two parallel `work_claim` calls with one place left start only one claim
  - *one failed claim doesn't stop the run:* the claim agent on CLM-1001 raises, and CLM-1002 and CLM-1003 are still decided
  - *a failed claim goes back in the queue and is tried again:* CLM-1001 fails, then is decided on its second try in the same run, and counts once against the cap
  - *a claim that fails twice is left for a handler:* its report says so, its completed to-do item shows Left for a handler, and a third `work_claim` refuses it
  - *a referral is left for a handler:* a claim agent that refers its claim leaves a completed item that shows Left for a handler, and an approval over $1,000 waiting for sign-off shows Done
  - *the check for missed claims:* a queue agent that tries to finish after one claim with a cap of 2 is sent back with a message naming the next waiting claim, and then works it. A queue agent that ignores it is let go after 3 nudges
  - a queue agent that fails after its retries leaves the run stopped, with the error as its summary
- [x] pytest: `uv run -m agent`, `--cap 5` and `CLM-1001` call `run_queue` and `try_claim` with the right arguments
- [x] `GET /api/instructions` returns both sets. Neither mentions `data/evals/` or a handler's decision
- [x] vitest and Playwright: the instructions page shows both sets, read only
- [x] After `uv run -m backend.seed`, `uv run -m agent --cap 2` on the default model works two claims, prints two reports and a summary, and leaves 23 claims waiting. The run is finished, with its to-do list all ticked off
- [x] `npm run check:python` and `npm run check:ts` pass, with coverage of at least 80%

## Phase 5: A five-claim run, and the handover

**What it builds.** Nothing new. It runs the brief's acceptance test with the real model while watching the dashboard, then brings the documents up to date.

- Reseed, then run `uv run -m agent --cap 5` on the default model, with the queue page and then each claim's page open in the Playwright MCP browser.
- `docs/SPEC.md` describes the run, the to-do list, the status Left for a handler and what the agent read. `docs/TECH_STACK.md` describes the two agents, their middleware, the entry points, the default model and `OPENROUTER_IGNORE`. `docs/STATUS.md` describes the product as it now is, how to run it (including the settings in `.env`), the API in brief, and what the run showed.

**Success criteria**

- [x] After `uv run -m backend.seed`, with `npm run dev` running and the queue page open, `uv run -m agent --cap 5` works five claims on its own. The to-do list appears, fills in and is ticked off while it works, and the summary appears at the end. OpenRouter's activity page shows none of the run's calls served by Wafer (the backend and the dashboard ran as separate processes without auto-reload, the same servers `npm run dev` starts; the run went through `agent.__main__.run(["--cap", "5"])`, the code behind `uv run -m agent --cap 5`, from a script that also recorded each call's generation id)
- [x] Afterwards the queue shows 20 claims waiting, and none in progress
- [x] Each of the five claims' pages shows its steps, including the sections the agent read under "What the agent read", and its decision and reason (CLM-1011's page checked in the browser, and all five through the API the page reads)
- [x] Any claim that failed during the run shows its error steps, and is back in the queue or left for a handler (no claim failed in either acceptance run, so this rests on the tests in Phases 2 and 4)
- [x] `uv run -m backend.seed` resets the queue to 25 waiting claims and no runs
- [x] `docs/SPEC.md`, `docs/TECH_STACK.md` and `docs/STATUS.md` describe the product as it now is
- [x] `npm run check` passes in full: ruff, pyright, pytest with at least 80% coverage, ESLint, Prettier, tsc, vitest with at least 80% coverage, and Playwright

A run of the whole queue with `uv run -m agent` is left to you, since it makes 25 claims' worth of model calls on your key. Reseed afterwards to start again.
