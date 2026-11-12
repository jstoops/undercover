import pytest

from agent import __main__ as cli
from agent import api, harness

MODEL = object()


@pytest.fixture
def ran(backend, monkeypatch):
    calls = []
    monkeypatch.setattr(harness, "model", lambda: MODEL)
    monkeypatch.setattr(
        harness,
        "work_claim",
        lambda claim_id, model: (
            calls.append(("claim", claim_id, model)) or f"{claim_id}: decline"
        ),
    )
    monkeypatch.setattr(
        harness,
        "run_queue",
        lambda cap, model: calls.append(("queue", cap, model)) or "The summary.",
    )
    return calls


def test_works_every_waiting_claim(backend, ran, capsys):
    backend.post("/api/claims/CLM-1001/start")
    cli.run([])
    assert ran == [("queue", 24, MODEL)]
    assert capsys.readouterr().out == "The summary.\n"


def test_works_up_to_a_cap(ran):
    cli.run(["--cap", "5"])
    assert ran == [("queue", 5, MODEL)]


def test_works_one_claim(ran, capsys):
    cli.run(["CLM-1005"])
    assert ran == [("claim", "CLM-1005", MODEL)]
    assert capsys.readouterr().out == "CLM-1005: decline\n"


def test_says_when_nothing_is_waiting(ran, monkeypatch, capsys):
    monkeypatch.setattr(api, "waiting_claims", list)
    cli.run([])
    assert ran == []
    assert capsys.readouterr().out == "No claims are waiting.\n"
