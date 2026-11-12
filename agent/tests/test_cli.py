import pytest

from agent import __main__ as cli
from agent import claim_agent


@pytest.fixture
def worked(backend, monkeypatch):
    claims = []

    def try_claim(claim_id):
        claims.append(claim_id)
        return f"{claim_id}: decline"

    monkeypatch.setattr(claim_agent, "try_claim", try_claim)
    return claims


def test_works_every_waiting_claim(backend, worked, capsys):
    backend.post("/api/claims/CLM-1001/start")
    cli.work_queue([])
    assert worked == [f"CLM-{n}" for n in range(1002, 1026)]
    assert "CLM-1002: decline" in capsys.readouterr().out


def test_works_one_claim(worked):
    cli.work_queue(["CLM-1005"])
    assert worked == ["CLM-1005"]
