import re
import sqlite3
from contextlib import closing

import pytest

from backend.db import database_path


def start(client, claim_id):
    return client.post(f"/api/claims/{claim_id}/start")


def decide(client, claim_id, decision, payout):
    return client.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "decision": decision,
            "payout": payout,
            "reason": "The wording covers it.",
            "policy_section": "Section 3, Trip Delay",
        },
    )


def pay(client, claim_id, amount):
    return client.post(f"/api/claims/{claim_id}/payment", json={"amount": amount})


def sign_off(client, claim_id, handler_id):
    return client.post(
        f"/api/claims/{claim_id}/sign-off", json={"handler_id": handler_id}
    )


def approved(client, claim_id, payout):
    start(client, claim_id)
    return decide(client, claim_id, "approve", payout)


def test_get_instructions(client):
    instructions = client.get("/api/instructions").json()
    claim = instructions["claim"]
    assert claim.startswith("# The UnderCover Agent: working a claim")
    assert "$1,000" in claim
    assert "`list_sections`" in claim
    assert "`read_section`" in claim
    assert "A recorded decision is final" in claim
    queue = instructions["queue"]
    assert queue.startswith("# The UnderCover Agent: running the queue")
    for name in ("list_waiting_claims", "write_todos", "work_claim"):
        assert f"`{name}`" in queue
    assert "Don't finish while a claim you could still work is waiting" in queue
    for text in (claim, queue):
        assert "evals" not in text
        assert "handlers' decisions" not in text


@pytest.mark.parametrize("agent", ["claim", "queue"])
def test_instructions_give_a_goal_not_a_script(client, agent):
    text = client.get("/api/instructions").json()[agent]
    assert "## Your goal" in text
    assert not re.search(r"^\s*\d+\. ", text, re.MULTILINE)


def test_start_claim(client):
    response = start(client, "CLM-1001")
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"
    again = start(client, "CLM-1001")
    assert again.status_code == 409
    assert again.json()["detail"] == "Claim CLM-1001 is in progress"


def fail(client, claim_id, reason="The model provider timed out"):
    return client.post(
        f"/api/claims/{claim_id}/failure",
        json={"thread_id": "t1", "reason": reason},
    )


def test_a_failed_claim_goes_back_in_the_queue_once(client):
    start(client, "CLM-1001")
    first = fail(client, "CLM-1001")
    assert first.status_code == 200
    assert first.json()["status"] == "waiting"
    assert first.json()["failures"] == 1
    start(client, "CLM-1001")
    second = fail(client, "CLM-1001", "The agent finished without a decision")
    assert second.json()["status"] == "left_for_handler"
    assert second.json()["failures"] == 2
    refused = start(client, "CLM-1001")
    assert refused.status_code == 409
    assert refused.json()["detail"] == "Claim CLM-1001 is left for a handler"
    errors = [
        (s["kind"], s["thread_id"], s["content"])
        for s in client.get("/api/claims/CLM-1001/steps").json()
    ]
    assert errors == [
        ("error", "t1", "The model provider timed out"),
        ("error", "t1", "The agent finished without a decision"),
    ]
    queue = {c["claim_id"]: c for c in client.get("/api/claims").json()}
    assert queue["CLM-1001"]["status"] == "left_for_handler"
    assert queue["CLM-1001"]["failures"] == 2


def test_only_a_claim_in_progress_can_fail(client):
    assert fail(client, "CLM-1001").status_code == 409
    approved(client, "CLM-1002", 420)
    pay(client, "CLM-1002", 420)
    assert fail(client, "CLM-1002").status_code == 409
    claim = client.get("/api/claims/CLM-1002").json()
    assert claim["status"] == "decided"
    assert claim["failures"] == 0
    assert claim["payment"]["amount"] == 420
    assert client.get("/api/claims/CLM-1002/steps").json() == []
    assert fail(client, "CLM-9999").status_code == 404
    start(client, "CLM-1003")
    assert fail(client, "CLM-1003", "").status_code == 422


def test_a_decided_claim_is_final(client):
    approved(client, "CLM-1001", 420)
    response = start(client, "CLM-1001")
    assert response.status_code == 409
    assert response.json()["detail"] == "Claim CLM-1001 is decided"
    assert decide(client, "CLM-1001", "decline", 0).status_code == 409


def test_steps(client):
    for kind, name in [("tool_call", "get_claim"), ("tool_result", "get_claim")]:
        response = client.post(
            "/api/claims/CLM-1001/steps",
            json={"thread_id": "t1", "kind": kind, "name": name, "content": "{}"},
        )
        assert response.status_code == 200
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [(s["kind"], s["name"]) for s in steps] == [
        ("tool_call", "get_claim"),
        ("tool_result", "get_claim"),
    ]
    assert steps[0]["thread_id"] == "t1"
    assert steps[0]["created_at"]
    assert client.get("/api/claims/CLM-1002/steps").json() == []


def test_steps_need_a_known_claim_and_kind(client):
    step = {"thread_id": "t1", "kind": "tool_call", "name": "x", "content": ""}
    assert client.post("/api/claims/CLM-9999/steps", json=step).status_code == 404
    assert client.get("/api/claims/CLM-9999/steps").status_code == 404
    bad = {**step, "kind": "thought"}
    assert client.post("/api/claims/CLM-1001/steps", json=bad).status_code == 422


def test_approve_and_pay_up_to_the_limit(client):
    response = approved(client, "CLM-1001", 420)
    assert response.json()["status"] == "decided"
    assert response.json()["decision"]["payout"] == 420
    paid = pay(client, "CLM-1001", 420.00)
    assert paid.status_code == 200
    assert paid.json()["payment"]["amount"] == 420
    assert paid.json()["payment"]["paid_at"]
    again = pay(client, "CLM-1001", 420)
    assert again.status_code == 409
    assert again.json()["detail"] == "Claim CLM-1001 has already been paid"
    queue = {c["claim_id"]: c for c in client.get("/api/claims").json()}
    assert queue["CLM-1001"]["status"] == "decided"
    assert queue["CLM-1001"]["decision"] == "approve"
    assert queue["CLM-1001"]["payout"] == 420


def test_exactly_the_limit_pays_without_sign_off(client):
    assert approved(client, "CLM-1002", 1000).json()["status"] == "decided"
    assert pay(client, "CLM-1002", 1000).status_code == 200


def test_payment_over_the_limit_waits_for_sign_off(client):
    assert approved(client, "CLM-1003", 1500).json()["status"] == "awaiting_sign_off"
    refused = pay(client, "CLM-1003", 1500)
    assert refused.status_code == 403
    assert "held until a handler signs off" in refused.json()["detail"]
    assert pay(client, "CLM-1003", 900).status_code == 403
    claim = client.get("/api/claims/CLM-1003").json()
    assert claim["payment"] is None
    assert claim["status"] == "awaiting_sign_off"


def test_sign_off_pays(client):
    approved(client, "CLM-1003", 1500)
    response = sign_off(client, "CLM-1003", "HND-01")
    assert response.status_code == 200
    claim = response.json()
    assert claim["status"] == "decided"
    assert claim["sign_off"]["handler_id"] == "HND-01"
    assert claim["sign_off"]["handler_name"] == "Dana Whitfield"
    assert claim["payment"]["amount"] == 1500
    assert pay(client, "CLM-1003", 1500).status_code == 409


def test_payment_must_be_the_payout(client):
    approved(client, "CLM-1001", 420)
    response = pay(client, "CLM-1001", 400)
    assert response.status_code == 409
    assert response.json()["detail"] == (
        "The payment must be the approved payout of $420.00"
    )
    assert client.get("/api/claims/CLM-1001").json()["payment"] is None


@pytest.mark.parametrize("decision", ["decline", "refer"])
def test_decline_and_refer_are_not_paid(client, decision):
    start(client, "CLM-1004")
    response = decide(client, "CLM-1004", decision, 0)
    assert response.json()["status"] == "decided"
    assert response.json()["decision"]["payout"] == 0
    assert pay(client, "CLM-1004", 10).status_code == 409


def test_state_checks(client):
    assert decide(client, "CLM-1001", "decline", 0).status_code == 409
    assert pay(client, "CLM-1001", 10).status_code == 409
    approved(client, "CLM-1001", 420)
    assert sign_off(client, "CLM-1001", "HND-01").status_code == 409
    approved(client, "CLM-1003", 1500)
    assert sign_off(client, "CLM-1003", "HND-99").status_code == 404
    assert start(client, "CLM-9999").status_code == 404


def test_only_a_handler_who_can_approve_over_the_limit_signs_off(client):
    with closing(sqlite3.connect(database_path())) as db:
        db.execute("UPDATE handlers SET can_approve_over_limit = 0")
        db.commit()
    approved(client, "CLM-1003", 1500)
    response = sign_off(client, "CLM-1003", "HND-02")
    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Marcus Oyelaran can't sign off payouts over $1,000.00"
    )


@pytest.mark.parametrize(
    ("decision", "payout"),
    [("approve", 0), ("decline", 10), ("refer", 5), ("maybe", 0), ("approve", -5)],
)
def test_decision_input_checks(client, decision, payout):
    start(client, "CLM-1001")
    assert decide(client, "CLM-1001", decision, payout).status_code == 422


def test_payment_input_checks(client):
    approved(client, "CLM-1001", 420)
    assert pay(client, "CLM-1001", 0).status_code == 422
