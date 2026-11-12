"""Reset the database from UnderCover's records in data/: uv run -m backend.seed"""

import json
from contextlib import closing
from pathlib import Path
from typing import Any

from backend.db import DATA, SCHEMA, connect, database_path


def load(name: str) -> list[dict[str, Any]]:
    """Read one of the JSON records in data/."""
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def as_json(record: dict[str, Any], *fields: str) -> dict[str, Any]:
    """Return a record with the named fields stored as JSON text."""
    return record | {name: json.dumps(record[name]) for name in fields}


def seed(path: Path) -> dict[str, int]:
    """Recreate the database with every claim waiting, and return what was loaded."""
    customers = load("customers.json")
    policies = load("policies.json")
    claims = load("claims.json")
    handlers = load("handlers.json")
    with closing(connect(path)) as db:
        db.executescript(SCHEMA)
        db.executemany(
            "INSERT INTO customers (customer_id, name, customer_since, previous_claims)"
            " VALUES (:customer_id, :name, :customer_since, :previous_claims)",
            [as_json(c, "previous_claims") for c in customers],
        )
        db.executemany(
            "INSERT INTO policies (policy_id, customer_id, plan, add_ons, purchased_on,"
            " sold_through, trip, travelers, status)"
            " VALUES (:policy_id, :customer_id, :plan, :add_ons, :purchased_on,"
            " :sold_through, :trip, :travelers, :status)",
            [as_json(p, "add_ons", "trip", "travelers") for p in policies],
        )
        db.executemany(
            "INSERT INTO claims (claim_id, policy_id, customer_id, claim_type,"
            " submitted_on, incident_date, incident_location, summary, story, items,"
            " amount_claimed, documents, status, failures)"
            " VALUES (:claim_id, :policy_id, :customer_id, :claim_type,"
            " :submitted_on, :incident_date, :incident_location, :summary, :story,"
            " :items, :amount_claimed, :documents, 'waiting', 0)",
            [as_json(c, "items", "documents") for c in claims],
        )
        db.executemany(
            "INSERT INTO handlers (handler_id, name, role, can_approve_over_limit)"
            " VALUES (:handler_id, :name, :role, :can_approve_over_limit)",
            handlers,
        )
        db.commit()
    return {
        "claims": len(claims),
        "policies": len(policies),
        "customers": len(customers),
        "handlers": len(handlers),
    }


def main() -> None:
    """Seed the database and say what was loaded."""
    path = database_path()
    counts = seed(path)
    print(
        f"Seeded {path} with {counts['claims']} claims, {counts['policies']} policies, "
        f"{counts['customers']} customers and {counts['handlers']} handlers"
    )


if __name__ == "__main__":
    main()
