"""The read-only records: policies, customers, handlers, documents and instructions."""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.db import Db, found
from backend.documents import Document, contents, sections
from backend.models import (
    Customer,
    Handler,
    Instructions,
    Policy,
    Section,
    SectionSummary,
)

INSTRUCTIONS = Path(__file__).parent / "instructions"

router = APIRouter()


@router.get("/policies/{policy_id}", operation_id="get_policy")
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


@router.get("/customers/{customer_id}", operation_id="get_customer")
def get_customer(customer_id: str, db: Db) -> Customer:
    """Read a customer's name, customer-since date and earlier claims."""
    row = found(
        db, "SELECT * FROM customers WHERE customer_id = ?", customer_id, "Customer"
    )
    return Customer.model_validate(
        {**row, "previous_claims": json.loads(row["previous_claims"])}
    )


@router.get("/handlers", operation_id="list_handlers")
def list_handlers(db: Db) -> list[Handler]:
    """List the claims handlers."""
    rows = db.execute("SELECT * FROM handlers ORDER BY handler_id")
    return [Handler.model_validate(dict(row)) for row in rows]


@router.get("/documents/{document}/sections", operation_id="list_sections")
def list_sections(document: Document) -> list[SectionSummary]:
    """List the sections of the wording or the manual, with the topics of each."""
    return contents(document)


@router.get("/documents/{document}/sections/{number}", operation_id="read_section")
def read_section(document: Document, number: int) -> Section:
    """Read one section of the policy wording or the claims manual."""
    for section in sections(document):
        if section.number == number:
            return section
    raise HTTPException(404, f"Section {number} of the {document} not found")


@router.get("/instructions", operation_id="get_instructions")
def get_instructions() -> Instructions:
    """Read the UnderCover Agent's instructions for running the queue and a claim."""
    return Instructions(
        queue=(INSTRUCTIONS / "queue.md").read_text(encoding="utf-8"),
        claim=(INSTRUCTIONS / "claim.md").read_text(encoding="utf-8"),
    )
