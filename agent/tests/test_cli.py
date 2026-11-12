import pytest
from fastapi.testclient import TestClient

from agent import __main__ as cli
from agent import main
from backend.main import app


@pytest.fixture
def ran(client, monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    claims = []
    monkeypatch.setattr(
        main, "run", lambda claim_id, _: claims.append(claim_id) or "Done."
    )
    return claims


def test_works_every_waiting_claim(client, ran, capsys):
    client.post("/api/claims/CLM-1001/start")
    cli.work_queue([])
    assert ran == [f"CLM-{n}" for n in range(1002, 1026)]
    out = capsys.readouterr().out
    assert "CLM-1002: no decision yet" in out
    assert "  Done." in out


def test_works_one_claim(ran):
    cli.work_queue(["CLM-1005"])
    assert ran == ["CLM-1005"]


def claim(client, claim_id):
    return client.get(f"/api/claims/{claim_id}").json()


def decide(client, claim_id, kind, payout):
    client.post(f"/api/claims/{claim_id}/start")
    client.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "decision": kind,
            "payout": payout,
            "reason": "Because.",
            "policy_section": "Section 3, Trip Delay",
        },
    )


def test_outcome(client):
    decide(client, "CLM-1001", "approve", 420)
    assert (
        cli.outcome(claim(client, "CLM-1001")) == "CLM-1001: approve $420.00, not paid"
    )
    client.post("/api/claims/CLM-1001/payment", json={"amount": 420})
    assert cli.outcome(claim(client, "CLM-1001")) == "CLM-1001: approve $420.00, paid"
    decide(client, "CLM-1003", "approve", 3750)
    assert cli.outcome(claim(client, "CLM-1003")) == (
        "CLM-1003: approve $3,750.00, waiting for sign-off"
    )
    decide(client, "CLM-1004", "decline", 0)
    assert cli.outcome(claim(client, "CLM-1004")) == "CLM-1004: decline"
