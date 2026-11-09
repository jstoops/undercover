"""The UnderCover backend."""

import json
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException

from backend.db import DATA, database_path, get_db
from backend.models import (
    Claim,
    ClaimSummary,
    Customer,
    Handler,
    Policy,
    PolicyWording,
)
from backend.seed import seed

QUEUE_SQL = """
SELECT c.claim_id, cu.name AS customer_name, c.claim_type, c.summary, c.submitted_on,
       c.amount_claimed, c.status, d.decision, d.payout
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


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording() -> PolicyWording:
    """Read the policy wording, the contract with the customer, as Markdown."""
    text = (DATA / "policy_wording.md").read_text(encoding="utf-8")
    return PolicyWording(policy_wording=text)


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers(db: Db) -> list[Handler]:
    """List the claims handlers."""
    rows = db.execute("SELECT * FROM handlers ORDER BY handler_id")
    return [Handler.model_validate(dict(row)) for row in rows]
