"""Runs of the queue agent, each with its to-do list and summary."""

import sqlite3

from fastapi import APIRouter, HTTPException

from backend.claims import load_claim, record_failure
from backend.db import Db, found, now
from backend.models import FinishInput, Run, RunInput, TodosInput

router = APIRouter()


def load_run(db: sqlite3.Connection, run_id: int) -> Run:
    """Read a run with its to-do list, or answer 404."""
    row = found(db, "SELECT * FROM runs WHERE run_id = ?", run_id, "Run")
    todos = db.execute(
        "SELECT position, content, status FROM todos WHERE run_id = ?"
        " ORDER BY position",
        (run_id,),
    )
    return Run.model_validate({**row, "todos": [dict(t) for t in todos]})


def running(db: sqlite3.Connection, run_id: int) -> Run:
    """Read a run, or answer 409 unless it is still running."""
    run = load_run(db, run_id)
    if run.status != "running":
        raise HTTPException(409, f"Run {run_id} is {run.status}")
    return run


@router.post("/runs", operation_id="start_run")
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


@router.get("/runs/current", operation_id="get_current_run")
def get_current_run(db: Db) -> Run | None:
    """Read the latest run with its to-do list, or nothing before the first run."""
    row = db.execute("SELECT max(run_id) AS run_id FROM runs").fetchone()
    return load_run(db, row["run_id"]) if row["run_id"] else None


@router.put("/runs/{run_id}/todos", operation_id="save_todos")
def save_todos(run_id: int, todos: TodosInput, db: Db) -> Run:
    """Save the queue agent's to-do list for a run as it now stands."""
    running(db, run_id)
    with db:
        db.execute("DELETE FROM todos WHERE run_id = ?", (run_id,))
        db.executemany(
            "INSERT INTO todos (run_id, position, content, status) VALUES (?, ?, ?, ?)",
            [
                (run_id, position, todo.content, todo.status)
                for position, todo in enumerate(todos.todos, start=1)
            ],
        )
    return load_run(db, run_id)


@router.post("/runs/{run_id}/finish", operation_id="finish_run")
def finish_run(run_id: int, finish: FinishInput, db: Db) -> Run:
    """Record how a run ended, finished or stopped, and its summary."""
    running(db, run_id)
    with db:
        db.execute(
            "UPDATE runs SET status = ?, finished_at = ?, summary = ? WHERE run_id = ?",
            (finish.outcome, now(), finish.summary, run_id),
        )
    return load_run(db, run_id)
