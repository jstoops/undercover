"""Reset the database from UnderCover's records in data/: uv run -m backend.seed"""

import json
from contextlib import closing
from pathlib import Path
from typing import Any

from backend.db import DATA, SCHEMA, connect, database_path


def load(name: str) -> list[dict[str, Any]]:
    """Read one of the JSON records in data/."""
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def seed(path: Path) -> dict[str, int]:
    """Recreate the database with every claim waiting, and return what was loaded."""
    customers = load("customers.json")
    policies = load("policies.json")
    claims = load("claims.json")
    handlers = load("handlers.json")
    with closing(connect(path)) as db:
        db.executescript(SCHEMA)
        db.executemany(
            "INSERT INTO customers VALUES (?, ?, ?, ?)",
            [
                (
                    c["customer_id"],
                    c["name"],
                    c["customer_since"],
                    json.dumps(c["previous_claims"]),
                )
                for c in customers
            ],
        )
        db.executemany(
            "INSERT INTO policies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    p["policy_id"],
                    p["customer_id"],
                    p["plan"],
                    json.dumps(p["add_ons"]),
                    p["purchased_on"],
                    p["sold_through"],
                    json.dumps(p["trip"]),
                    json.dumps(p["travelers"]),
                    p["status"],
                )
                for p in policies
            ],
        )
        db.executemany(
            "INSERT INTO claims"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'waiting', 0)",
            [
                (
                    c["claim_id"],
                    c["policy_id"],
                    c["customer_id"],
                    c["claim_type"],
                    c["submitted_on"],
                    c["incident_date"],
                    c["incident_location"],
                    c["summary"],
                    c["story"],
                    json.dumps(c["items"]),
                    c["amount_claimed"],
                    json.dumps(c["documents"]),
                )
                for c in claims
            ],
        )
        db.executemany(
            "INSERT INTO handlers VALUES (?, ?, ?, ?)",
            [
                (h["handler_id"], h["name"], h["role"], h["can_approve_over_limit"])
                for h in handlers
            ],
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
