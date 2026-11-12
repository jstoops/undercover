import json
import sqlite3
from contextlib import closing

from fastapi.testclient import TestClient

from backend import seed
from backend.db import DATA
from backend.main import app


def test_seed_loads_the_records(tmp_path):
    counts = seed.seed(tmp_path / "undercover.db")
    assert counts == {"claims": 25, "policies": 50, "customers": 49, "handlers": 3}


def test_seed_loads_only_the_queue(tmp_path):
    path = tmp_path / "undercover.db"
    seed.seed(path)
    with closing(sqlite3.connect(path)) as db:
        ids = {row[0] for row in db.execute("SELECT claim_id FROM claims")}
        statuses = {row[0] for row in db.execute("SELECT status FROM claims")}
    queue = json.loads((DATA / "claims.json").read_text(encoding="utf-8"))
    assert ids == {claim["claim_id"] for claim in queue}
    assert "CLM-1901" not in ids
    assert statuses == {"waiting"}


def test_seed_resets_the_database(tmp_path):
    path = tmp_path / "undercover.db"
    seed.seed(path)
    with closing(sqlite3.connect(path)) as db:
        db.execute("UPDATE claims SET status = 'decided', failures = 1")
        db.execute("INSERT INTO runs (cap, status, started_at) VALUES (5, 'x', 'y')")
        db.execute("INSERT INTO todos VALUES (1, 1, 'CLM-1001', 'pending')")
        db.commit()
    seed.seed(path)
    with closing(sqlite3.connect(path)) as db:
        statuses = {row[0] for row in db.execute("SELECT status FROM claims")}
        failures = {row[0] for row in db.execute("SELECT failures FROM claims")}
        runs = db.execute("SELECT count(*) FROM runs").fetchone()[0]
        todos = db.execute("SELECT count(*) FROM todos").fetchone()[0]
    assert statuses == {"waiting"}
    assert failures == {0}
    assert (runs, todos) == (0, 0)


def test_main_reports_what_it_loaded(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "undercover.db"))
    seed.main()
    assert (
        "25 claims, 50 policies, 49 customers and 3 handlers" in capsys.readouterr().out
    )


def test_startup_seeds_a_missing_database(tmp_path, monkeypatch):
    path = tmp_path / "undercover.db"
    monkeypatch.setenv("UNDERCOVER_DB", str(path))
    with TestClient(app) as client:
        assert len(client.get("/api/claims").json()) == 25
    assert path.exists()
