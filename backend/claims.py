"""The claims queue and the rules for working a claim, from start to payment."""

import json
import sqlite3

from fastapi import APIRouter, HTTPException

from backend.db import DATA, Db, found, now, one
from backend.models import (
    Claim,
    ClaimSummary,
    DecisionInput,
    FailureInput,
    PaymentInput,
    SignOffInput,
    Status,
    Step,
    StepInput,
)

APPROVAL_LIMIT: float = json.loads((DATA / "company.json").read_text(encoding="utf-8"))[
    "payout_approval_limit"
]
TRIES = 2
STATUS_TEXT: dict[Status, str] = {
    "waiting": "waiting",
    "in_progress": "in progress",
    "awaiting_sign_off": "waiting for sign-off",
    "decided": "decided",
    "left_for_handler": "left for a handler",
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

router = APIRouter()


def cents(amount: float) -> int:
    """Return an amount in whole cents, so amounts compare exactly."""
    return round(amount * 100)


def money(amount: float) -> str:
    """Show an amount in US dollars, such as $1,250.00."""
    return f"${amount:,.2f}"


def load_claim(db: sqlite3.Connection, claim_id: str) -> Claim:
    """Read a claim in full, with its decision, sign-off and payment, or answer 404."""
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


def require_status(claim: Claim, *allowed: Status) -> None:
    """Answer 409 unless the claim is in one of the allowed states."""
    if claim.status not in allowed:
        raise HTTPException(
            409, f"Claim {claim.claim_id} is {STATUS_TEXT[claim.status]}"
        )


def set_status(db: sqlite3.Connection, claim_id: str, status: Status) -> None:
    """Move a claim to a new status, in the caller's transaction."""
    db.execute("UPDATE claims SET status = ? WHERE claim_id = ?", (status, claim_id))


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
        "UPDATE claims SET failures = ? WHERE claim_id = ?", (failures, claim.claim_id)
    )
    set_status(
        db, claim.claim_id, "left_for_handler" if failures >= TRIES else "waiting"
    )
    step = StepInput(thread_id=thread_id, kind="error", name="", content=reason)
    insert_step(db, claim.claim_id, step)


@router.get("/claims", operation_id="list_claims")
def list_claims(db: Db) -> list[ClaimSummary]:
    """List the claims queue with each claim's status and decision."""
    return [ClaimSummary.model_validate(dict(row)) for row in db.execute(QUEUE_SQL)]


@router.get("/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, db: Db) -> Claim:
    """Read a claim in full, with its decision, sign-off and payment."""
    return load_claim(db, claim_id)


@router.post("/claims/{claim_id}/start", operation_id="start_claim")
def start_claim(claim_id: str, db: Db) -> Claim:
    """Mark a waiting claim as in progress while the agent works on it."""
    require_status(load_claim(db, claim_id), "waiting")
    with db:
        set_status(db, claim_id, "in_progress")
    return load_claim(db, claim_id)


@router.post("/claims/{claim_id}/steps", operation_id="add_step")
def add_step(claim_id: str, step: StepInput, db: Db) -> Step:
    """Record one step the agent took on a claim."""
    load_claim(db, claim_id)
    with db:
        return insert_step(db, claim_id, step)


@router.get("/claims/{claim_id}/steps", operation_id="list_steps")
def list_steps(claim_id: str, db: Db) -> list[Step]:
    """List the steps the agent has taken on a claim, oldest first."""
    load_claim(db, claim_id)
    rows = db.execute(
        "SELECT * FROM steps WHERE claim_id = ? ORDER BY step_id", (claim_id,)
    )
    return [Step.model_validate(dict(row)) for row in rows]


@router.post("/claims/{claim_id}/failure", operation_id="fail_claim")
def fail_claim(claim_id: str, failure: FailureInput, db: Db) -> Claim:
    """Record that the agent failed on a claim, which goes back in the queue."""
    claim = load_claim(db, claim_id)
    require_status(claim, "in_progress")
    with db:
        record_failure(db, claim, failure.thread_id, failure.reason)
    return load_claim(db, claim_id)


@router.post("/claims/{claim_id}/decision", operation_id="decide_claim")
def decide_claim(claim_id: str, decision: DecisionInput, db: Db) -> Claim:
    """Record the decision on a claim in progress: approve, decline or refer."""
    require_status(load_claim(db, claim_id), "in_progress")
    payout = round(decision.payout, 2)
    over_limit = decision.decision == "approve" and payout > APPROVAL_LIMIT
    with db:
        db.execute(
            "INSERT INTO decisions"
            " (claim_id, decision, payout, reason, policy_section, decided_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                claim_id,
                decision.decision,
                payout,
                decision.reason,
                decision.policy_section,
                now(),
            ),
        )
        set_status(db, claim_id, "awaiting_sign_off" if over_limit else "decided")
    return load_claim(db, claim_id)


@router.post("/claims/{claim_id}/payment", operation_id="pay_claim")
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
            "INSERT INTO payments (claim_id, amount, paid_at) VALUES (?, ?, ?)",
            (claim_id, decision.payout, now()),
        )
    return load_claim(db, claim_id)


@router.post("/claims/{claim_id}/sign-off", operation_id="sign_off_claim")
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
            "INSERT INTO sign_offs (claim_id, handler_id, signed_off_at)"
            " VALUES (?, ?, ?)",
            (claim_id, sign_off.handler_id, signed_off_at),
        )
        db.execute(
            "INSERT INTO payments (claim_id, amount, paid_at)"
            " SELECT claim_id, payout, ? FROM decisions WHERE claim_id = ?",
            (signed_off_at, claim_id),
        )
        set_status(db, claim_id, "decided")
    return load_claim(db, claim_id)
