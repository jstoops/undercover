"""The UnderCover backend."""

import json
import re
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException

from backend.db import DATA, database_path, get_db
from backend.documents import Document, contents, sections
from backend.models import (
    Claim,
    ClaimSummary,
    Customer,
    DecisionInput,
    FailureInput,
    FinishInput,
    Handler,
    Instructions,
    PaymentInput,
    Policy,
    Run,
    RunInput,
    Section,
    SectionSummary,
    ShownTodoStatus,
    SignOffInput,
    Status,
    Step,
    StepInput,
    Todo,
    TodosInput,
)
from backend.seed import seed

INSTRUCTIONS = Path(__file__).parent / "instructions"
APPROVAL_LIMIT: float = json.loads((DATA / "company.json").read_text(encoding="utf-8"))[
    "payout_approval_limit"
]
STATUS_TEXT: dict[Status, str] = {
    "waiting": "waiting",
    "in_progress": "in progress",
    "awaiting_sign_off": "waiting for sign-off",
    "decided": "decided",
    "left_for_handler": "left for a handler",
}
TRIES = 2
CLAIM_ID = re.compile(r"CLM-\d+")
SHOWN: dict[str, ShownTodoStatus] = {
    "pending": "to_do",
    "in_progress": "in_progress",
    "completed": "done",
}

QUEUE_SQL = """
SELECT c.claim_id, cu.name AS customer_name, c.claim_type, c.summary, c.submitted_on,
       c.amount_claimed, c.status, c.failures, d.decision, d.payout
FROM claims c
JOIN customers cu USING (customer_id)
LEFT JOIN decisions d USING (claim_id)
ORDER BY c.claim_id
"""
CLAIM_SQL = """
SELECT c.*, cu.name AS customer_name
FROM claims c JOIN customers cu USING (customer_id)
WHERE c.claim_id = ?
"""
SIGN_OFF_SQL = """
SELECT s.handler_id, h.name AS handler_name, s.signed_off_at
FROM sign_offs s JOIN handlers h USING (handler_id)
WHERE s.claim_id = ?
"""


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Seed the database on startup when it doesn't exist yet."""
    if not database_path().exists():
        seed(database_path())
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)
Db = Annotated[sqlite3.Connection, Depends(get_db)]


def one(db: sqlite3.Connection, sql: str, key: str) -> dict[str, Any] | None:
    """Return the single row that matches, or None."""
    row = db.execute(sql, (key,)).fetchone()
    return dict(row) if row else None


def found(db: sqlite3.Connection, sql: str, key: str, what: str) -> dict[str, Any]:
    """Return the single row that matches, or answer 404."""
    row = one(db, sql, key)
    if row is None:
        raise HTTPException(404, f"{what} {key} not found")
    return row


def now() -> str:
    """Return the time now, in UTC."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def cents(amount: float) -> int:
    """Return an amount in whole cents, so amounts compare exactly."""
    return round(amount * 100)


def money(amount: float) -> str:
    """Show an amount in US dollars, such as $1,250.00."""
    return f"${amount:,.2f}"


def require_status(claim: Claim, *allowed: Status) -> None:
    """Answer 409 unless the claim is in one of the allowed states."""
    if claim.status not in allowed:
        raise HTTPException(
            409, f"Claim {claim.claim_id} is {STATUS_TEXT[claim.status]}"
        )


def load_claim(db: sqlite3.Connection, claim_id: str) -> Claim:
    """Read a claim in full, with its decision, sign-off and payment."""
    row = found(db, CLAIM_SQL, claim_id, "Claim")
    return Claim.model_validate(
        {
            **row,
            "items": json.loads(row["items"]),
            "documents": json.loads(row["documents"]),
            "decision": one(db, "SELECT * FROM decisions WHERE claim_id = ?", claim_id),
            "sign_off": one(db, SIGN_OFF_SQL, claim_id),
            "payment": one(db, "SELECT * FROM payments WHERE claim_id = ?", claim_id),
        }
    )


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims(db: Db) -> list[ClaimSummary]:
    """List the claims queue with each claim's status and decision."""
    return [ClaimSummary.model_validate(dict(row)) for row in db.execute(QUEUE_SQL)]


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, db: Db) -> Claim:
    """Read a claim in full, with its decision, sign-off and payment."""
    return load_claim(db, claim_id)


@app.get("/api/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str, db: Db) -> Policy:
    """Read a policy: its plan, add-ons, purchase date, trip and travelers."""
    row = found(db, "SELECT * FROM policies WHERE policy_id = ?", policy_id, "Policy")
    return Policy.model_validate(
        {
            **row,
            "add_ons": json.loads(row["add_ons"]),
            "trip": json.loads(row["trip"]),
            "travelers": json.loads(row["travelers"]),
        }
    )


@app.get("/api/customers/{customer_id}", operation_id="get_customer")
def get_customer(customer_id: str, db: Db) -> Customer:
    """Read a customer's name, customer-since date and earlier claims."""
    row = found(
        db, "SELECT * FROM customers WHERE customer_id = ?", customer_id, "Customer"
    )
    return Customer.model_validate(
        {**row, "previous_claims": json.loads(row["previous_claims"])}
    )


@app.get("/api/documents/{document}/sections", operation_id="list_sections")
def list_sections(document: Document) -> list[SectionSummary]:
    """List the sections of the wording or the manual, with the topics of each."""
    return contents(document)


@app.get("/api/documents/{document}/sections/{number}", operation_id="read_section")
def read_section(document: Document, number: int) -> Section:
    """Read one section of the policy wording or the claims manual."""
    for section in sections(document):
        if section.number == number:
            return section
    raise HTTPException(404, f"Section {number} of the {document} not found")


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers(db: Db) -> list[Handler]:
    """List the claims handlers."""
    rows = db.execute("SELECT * FROM handlers ORDER BY handler_id")
    return [Handler.model_validate(dict(row)) for row in rows]


@app.get("/api/instructions", operation_id="get_instructions")
def get_instructions() -> Instructions:
    """Read the UnderCover Agent's instructions for running the queue and a claim."""
    return Instructions(
        queue=(INSTRUCTIONS / "queue.md").read_text(encoding="utf-8"),
        claim=(INSTRUCTIONS / "claim.md").read_text(encoding="utf-8"),
    )


@app.post("/api/claims/{claim_id}/start", operation_id="start_claim")
def start_claim(claim_id: str, db: Db) -> Claim:
    """Mark a waiting claim as in progress while the agent works on it."""
    require_status(load_claim(db, claim_id), "waiting")
    with db:
        db.execute(
            "UPDATE claims SET status = 'in_progress' WHERE claim_id = ?", (claim_id,)
        )
    return load_claim(db, claim_id)


def insert_step(db: sqlite3.Connection, claim_id: str, step: StepInput) -> Step:
    """Record one step on a claim, in the caller's transaction."""
    row = db.execute(
        "INSERT INTO steps (claim_id, thread_id, kind, name, content, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?) RETURNING *",
        (claim_id, step.thread_id, step.kind, step.name, step.content, now()),
    ).fetchone()
    return Step.model_validate(dict(row))


def record_failure(
    db: sqlite3.Connection, claim: Claim, thread_id: str, reason: str
) -> None:
    """Send a failed claim back to the queue, or leave it for a handler."""
    failures = claim.failures + 1
    db.execute(
        "UPDATE claims SET status = ?, failures = ? WHERE claim_id = ?",
        (
            "left_for_handler" if failures >= TRIES else "waiting",
            failures,
            claim.claim_id,
        ),
    )
    step = StepInput(thread_id=thread_id, kind="error", name="", content=reason)
    insert_step(db, claim.claim_id, step)


@app.post("/api/claims/{claim_id}/steps", operation_id="add_step")
def add_step(claim_id: str, step: StepInput, db: Db) -> Step:
    """Record one step the agent took on a claim."""
    found(db, "SELECT claim_id FROM claims WHERE claim_id = ?", claim_id, "Claim")
    with db:
        return insert_step(db, claim_id, step)


@app.post("/api/claims/{claim_id}/failure", operation_id="fail_claim")
def fail_claim(claim_id: str, failure: FailureInput, db: Db) -> Claim:
    """Record that the agent failed on a claim, which goes back in the queue."""
    claim = load_claim(db, claim_id)
    require_status(claim, "in_progress")
    with db:
        record_failure(db, claim, failure.thread_id, failure.reason)
    return load_claim(db, claim_id)


@app.get("/api/claims/{claim_id}/steps", operation_id="list_steps")
def list_steps(claim_id: str, db: Db) -> list[Step]:
    """List the steps the agent has taken on a claim, oldest first."""
    found(db, "SELECT claim_id FROM claims WHERE claim_id = ?", claim_id, "Claim")
    rows = db.execute(
        "SELECT * FROM steps WHERE claim_id = ? ORDER BY step_id", (claim_id,)
    )
    return [Step.model_validate(dict(row)) for row in rows]


@app.post("/api/claims/{claim_id}/decision", operation_id="decide_claim")
def decide_claim(claim_id: str, decision: DecisionInput, db: Db) -> Claim:
    """Record the decision on a claim in progress: approve, decline or refer."""
    require_status(load_claim(db, claim_id), "in_progress")
    payout = round(decision.payout, 2)
    over_limit = decision.decision == "approve" and payout > APPROVAL_LIMIT
    with db:
        db.execute(
            "INSERT INTO decisions VALUES (?, ?, ?, ?, ?, ?)",
            (
                claim_id,
                decision.decision,
                payout,
                decision.reason,
                decision.policy_section,
                now(),
            ),
        )
        db.execute(
            "UPDATE claims SET status = ? WHERE claim_id = ?",
            ("awaiting_sign_off" if over_limit else "decided", claim_id),
        )
    return load_claim(db, claim_id)


@app.post("/api/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, payment: PaymentInput, db: Db) -> Claim:
    """Pay a claim's approved payout; over $1,000 it waits for a handler's sign-off."""
    claim = load_claim(db, claim_id)
    decision = claim.decision
    if decision is None or decision.decision != "approve":
        raise HTTPException(
            409, f"Claim {claim_id} is not approved, so it can't be paid"
        )
    if claim.payment is not None:
        raise HTTPException(409, f"Claim {claim_id} has already been paid")
    if decision.payout > APPROVAL_LIMIT and claim.sign_off is None:
        raise HTTPException(
            403,
            f"The payout on claim {claim_id} is over {money(APPROVAL_LIMIT)}, "
            "so the payment is held until a handler signs off",
        )
    if cents(payment.amount) != cents(decision.payout):
        raise HTTPException(
            409, f"The payment must be the approved payout of {money(decision.payout)}"
        )
    with db:
        db.execute(
            "INSERT INTO payments VALUES (?, ?, ?)", (claim_id, decision.payout, now())
        )
    return load_claim(db, claim_id)


@app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off_claim")
def sign_off_claim(claim_id: str, sign_off: SignOffInput, db: Db) -> Claim:
    """Sign off an approval over $1,000 as a handler, which pays it."""
    require_status(load_claim(db, claim_id), "awaiting_sign_off")
    handler = found(
        db,
        "SELECT * FROM handlers WHERE handler_id = ?",
        sign_off.handler_id,
        "Handler",
    )
    if not handler["can_approve_over_limit"]:
        raise HTTPException(
            403,
            f"{handler['name']} can't sign off payouts over {money(APPROVAL_LIMIT)}",
        )
    signed_off_at = now()
    with db:
        db.execute(
            "INSERT INTO sign_offs VALUES (?, ?, ?)",
            (claim_id, sign_off.handler_id, signed_off_at),
        )
        db.execute(
            "INSERT INTO payments SELECT claim_id, payout, ? FROM decisions"
            " WHERE claim_id = ?",
            (signed_off_at, claim_id),
        )
        db.execute(
            "UPDATE claims SET status = 'decided' WHERE claim_id = ?", (claim_id,)
        )
    return load_claim(db, claim_id)


def shown_status(db: sqlite3.Connection, content: str, status: str) -> ShownTodoStatus:
    """Show a completed item for a referred or failed claim as left for a handler."""
    claim_id = CLAIM_ID.search(content)
    if status != "completed" or claim_id is None:
        return SHOWN[status]
    row = one(
        db,
        "SELECT c.status, d.decision FROM claims c"
        " LEFT JOIN decisions d USING (claim_id) WHERE c.claim_id = ?",
        claim_id.group(),
    )
    if row and (row["status"] == "left_for_handler" or row["decision"] == "refer"):
        return "left_for_handler"
    return "done"


def load_run(db: sqlite3.Connection, run_id: int) -> Run:
    """Read a run with its to-do list."""
    row = db.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"Run {run_id} not found")
    todos = db.execute(
        "SELECT * FROM todos WHERE run_id = ? ORDER BY position", (run_id,)
    )
    return Run.model_validate(
        {
            **dict(row),
            "todos": [
                Todo(
                    position=todo["position"],
                    content=todo["content"],
                    status=shown_status(db, todo["content"], todo["status"]),
                )
                for todo in todos.fetchall()
            ],
        }
    )


def running(db: sqlite3.Connection, run_id: int) -> Run:
    """Read a run, or answer 409 unless it is still running."""
    run = load_run(db, run_id)
    if run.status != "running":
        raise HTTPException(409, f"Run {run_id} is {run.status}")
    return run


@app.post("/api/runs", operation_id="start_run")
def start_run(run: RunInput, db: Db) -> Run:
    """Start a run of the queue, stopping any earlier run that never finished."""
    with db:
        if db.execute("SELECT 1 FROM runs WHERE status = 'running'").fetchone():
            db.execute(
                "UPDATE runs SET status = 'stopped', finished_at = ?, summary = ?"
                " WHERE status = 'running'",
                (now(), "The run stopped before it finished."),
            )
            stuck = db.execute(
                "SELECT claim_id FROM claims WHERE status = 'in_progress'"
            ).fetchall()
            for row in stuck:
                record_failure(
                    db,
                    load_claim(db, row["claim_id"]),
                    "",
                    "The run stopped before this claim was decided",
                )
        row = db.execute(
            "INSERT INTO runs (cap, status, started_at) VALUES (?, 'running', ?)"
            " RETURNING run_id",
            (run.cap, now()),
        ).fetchone()
    return load_run(db, row["run_id"])


@app.get("/api/runs/current", operation_id="get_current_run")
def get_current_run(db: Db) -> Run | None:
    """Read the latest run with its to-do list, or nothing before the first run."""
    row = db.execute("SELECT max(run_id) AS run_id FROM runs").fetchone()
    return load_run(db, row["run_id"]) if row["run_id"] else None


@app.put("/api/runs/{run_id}/todos", operation_id="save_todos")
def save_todos(run_id: int, todos: TodosInput, db: Db) -> Run:
    """Save the queue agent's to-do list for a run as it now stands."""
    running(db, run_id)
    with db:
        db.execute("DELETE FROM todos WHERE run_id = ?", (run_id,))
        db.executemany(
            "INSERT INTO todos VALUES (?, ?, ?, ?)",
            [
                (run_id, position, todo.content, todo.status)
                for position, todo in enumerate(todos.todos, start=1)
            ],
        )
    return load_run(db, run_id)


@app.post("/api/runs/{run_id}/finish", operation_id="finish_run")
def finish_run(run_id: int, finish: FinishInput, db: Db) -> Run:
    """Record how a run ended, finished or stopped, and its summary."""
    running(db, run_id)
    with db:
        db.execute(
            "UPDATE runs SET status = ?, finished_at = ?, summary = ? WHERE run_id = ?",
            (finish.outcome, now(), finish.summary, run_id),
        )
    return load_run(db, run_id)
