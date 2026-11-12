"""The UnderCover database: SQLite, seeded from data/."""

import os
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, HTTPException

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

SCHEMA = """
DROP TABLE IF EXISTS todos;
DROP TABLE IF EXISTS runs;
DROP TABLE IF EXISTS steps;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS sign_offs;
DROP TABLE IF EXISTS decisions;
DROP TABLE IF EXISTS claims;
DROP TABLE IF EXISTS policies;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS handlers;

CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    customer_since TEXT NOT NULL,
    previous_claims TEXT NOT NULL
);

CREATE TABLE policies (
    policy_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers,
    plan TEXT NOT NULL,
    add_ons TEXT NOT NULL,
    purchased_on TEXT NOT NULL,
    sold_through TEXT NOT NULL,
    trip TEXT NOT NULL,
    travelers TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE claims (
    claim_id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL REFERENCES policies,
    customer_id TEXT NOT NULL REFERENCES customers,
    claim_type TEXT NOT NULL,
    submitted_on TEXT NOT NULL,
    incident_date TEXT NOT NULL,
    incident_location TEXT NOT NULL,
    summary TEXT NOT NULL,
    story TEXT NOT NULL,
    items TEXT NOT NULL,
    amount_claimed REAL NOT NULL,
    documents TEXT NOT NULL,
    status TEXT NOT NULL,
    failures INTEGER NOT NULL
);

CREATE TABLE handlers (
    handler_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    can_approve_over_limit INTEGER NOT NULL
);

CREATE TABLE decisions (
    claim_id TEXT PRIMARY KEY REFERENCES claims,
    decision TEXT NOT NULL,
    payout REAL NOT NULL,
    reason TEXT NOT NULL,
    policy_section TEXT NOT NULL,
    decided_at TEXT NOT NULL
);

CREATE TABLE sign_offs (
    claim_id TEXT PRIMARY KEY REFERENCES claims,
    handler_id TEXT NOT NULL REFERENCES handlers,
    signed_off_at TEXT NOT NULL
);

CREATE TABLE payments (
    claim_id TEXT PRIMARY KEY REFERENCES claims,
    amount REAL NOT NULL,
    paid_at TEXT NOT NULL
);

CREATE TABLE steps (
    step_id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL REFERENCES claims,
    thread_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cap INTEGER NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    summary TEXT
);

CREATE TABLE todos (
    run_id INTEGER NOT NULL REFERENCES runs,
    position INTEGER NOT NULL,
    content TEXT NOT NULL,
    status TEXT NOT NULL,
    PRIMARY KEY (run_id, position)
);
"""


def database_path() -> Path:
    """Return the database file: UNDERCOVER_DB, or undercover.db at the repo root."""
    return Path(os.getenv("UNDERCOVER_DB", str(ROOT / "undercover.db")))


def connect(path: Path) -> sqlite3.Connection:
    """Open the database with rows that read like dictionaries."""
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def get_db() -> Iterator[sqlite3.Connection]:
    """Give each request its own connection."""
    connection = connect(database_path())
    try:
        yield connection
    finally:
        connection.close()


Db = Annotated[sqlite3.Connection, Depends(get_db)]


def one(db: sqlite3.Connection, sql: str, key: str | int) -> dict[str, Any] | None:
    """Return the single row that matches, or None."""
    row = db.execute(sql, (key,)).fetchone()
    return dict(row) if row else None


def found(
    db: sqlite3.Connection, sql: str, key: str | int, what: str
) -> dict[str, Any]:
    """Return the single row that matches, or answer 404."""
    row = one(db, sql, key)
    if row is None:
        raise HTTPException(404, f"{what} {key} not found")
    return row


def now() -> str:
    """Return the time now, in UTC."""
    return datetime.now(UTC).isoformat(timespec="seconds")
