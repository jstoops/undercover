import json

import httpx
from langchain_core.messages import AIMessage, HumanMessage

from agent import claim_agent, main
from agent.tests.stubs import REASON, calls, decision, script

PROVIDER_ERROR = RuntimeError("The model provider is busy")


def steps(backend, claim_id):
    return backend.get(f"/api/claims/{claim_id}/steps").json()


def claim(backend, claim_id):
    return backend.get(f"/api/claims/{claim_id}").json()


def approve_and_pay(claim_id="CLM-1001", payout=420, **kwargs):
    return script(
        calls("decide_claim", decision(claim_id, "approve", payout), "1"),
        calls("pay_claim", {"claim_id": claim_id, "amount": payout}, "2"),
        AIMessage(content="Approved and paid."),
        **kwargs,
    )


def test_approves_and_pays(backend):
    model = script(
        AIMessage(
            content="I will read the claim first.",
            tool_calls=[
                {"name": "get_claim", "args": {"claim_id": "CLM-1001"}, "id": "1"}
            ],
        ),
        calls("get_policy", {"policy_id": "POL-2001"}, "2"),
        calls("get_customer", {"customer_id": "CUS-3001"}, "3"),
        calls("decide_claim", decision("CLM-1001", "approve", 420), "4"),
        calls("pay_claim", {"claim_id": "CLM-1001", "amount": 420}, "5"),
        AIMessage(content="Approved $420.00 and paid."),
    )
    assert claim_agent.try_claim("CLM-1001", model) == "CLM-1001: approve $420.00, paid"
    record = claim(backend, "CLM-1001")
    assert record["status"] == "decided"
    assert record["decision"]["reason"] == REASON
    assert record["payment"]["amount"] == 420
    recorded = steps(backend, "CLM-1001")
    assert [(s["kind"], s["name"]) for s in recorded] == [
        ("reply", ""),
        ("tool_call", "get_claim"),
        ("tool_result", "get_claim"),
        ("tool_call", "get_policy"),
        ("tool_result", "get_policy"),
        ("tool_call", "get_customer"),
        ("tool_result", "get_customer"),
        ("tool_call", "decide_claim"),
        ("tool_result", "decide_claim"),
        ("tool_call", "pay_claim"),
        ("tool_result", "pay_claim"),
        ("reply", ""),
    ]
    assert len({s["thread_id"] for s in recorded}) == 1
    assert '"claim_id": "CLM-1001"' in recorded[1]["content"]
    assert "Rome" in recorded[2]["content"]
    assert recorded[-1]["content"] == "Approved $420.00 and paid."


def test_cannot_pay_over_the_limit(backend):
    line = claim_agent.try_claim("CLM-1003", approve_and_pay("CLM-1003", 3750))
    assert line == "CLM-1003: approve $3,750.00, waiting for sign-off"
    record = claim(backend, "CLM-1003")
    assert record["status"] == "awaiting_sign_off"
    assert record["payment"] is None
    paid = steps(backend, "CLM-1003")[-2]
    assert paid["kind"] == "tool_result"
    assert paid["name"] == "pay_claim"
    assert "held until a handler signs off" in paid["content"]


def test_declines(backend):
    model = script(
        calls("decide_claim", decision("CLM-1004", "decline", 0), "1"),
        AIMessage(content="Declined."),
    )
    assert claim_agent.try_claim("CLM-1004", model) == "CLM-1004: decline"
    assert claim(backend, "CLM-1004")["payment"] is None


def test_a_decided_claim_has_nothing_to_do(backend):
    refer = calls("decide_claim", decision("CLM-1004", "refer", 0), "1")
    claim_agent.try_claim("CLM-1004", script(refer, AIMessage(content="Referred.")))
    before = steps(backend, "CLM-1004")
    line = claim_agent.try_claim("CLM-1004", script(AIMessage(content="Again.")))
    assert line == "Claim CLM-1004 is decided, so there is nothing to do"
    assert steps(backend, "CLM-1004") == before


def test_a_provider_error_is_tried_again(backend):
    model = approve_and_pay(errors=[PROVIDER_ERROR])
    assert claim_agent.try_claim("CLM-1001", model) == "CLM-1001: approve $420.00, paid"
    assert claim(backend, "CLM-1001")["failures"] == 0


def test_a_claim_that_keeps_failing_is_left_for_a_handler(backend):
    errors = [PROVIDER_ERROR] * (main.MODEL_RETRIES + 1)
    first = claim_agent.try_claim("CLM-1001", script(errors=errors))
    assert first == (
        "CLM-1001: failed (RuntimeError: The model provider is busy),"
        " back in the queue for another try"
    )
    record = claim(backend, "CLM-1001")
    assert record["status"] == "waiting"
    assert record["failures"] == 1
    second = claim_agent.try_claim("CLM-1001", script(errors=errors))
    assert second == (
        "CLM-1001: failed again (RuntimeError: The model provider is busy),"
        " left for a handler"
    )
    assert claim(backend, "CLM-1001")["status"] == "left_for_handler"
    failures = [s for s in steps(backend, "CLM-1001") if s["kind"] == "error"]
    assert [s["content"] for s in failures] == [
        "RuntimeError: The model provider is busy"
    ] * 2
    assert failures[0]["thread_id"] != failures[1]["thread_id"]


def test_finishing_without_a_decision_is_a_failure(backend):
    line = claim_agent.try_claim("CLM-1001", script(AIMessage(content="Not sure.")))
    assert line == (
        "CLM-1001: failed (the agent finished without recording a decision),"
        " back in the queue for another try"
    )
    assert claim(backend, "CLM-1001")["status"] == "waiting"


def test_too_many_model_calls_is_a_failure(backend, monkeypatch):
    monkeypatch.setattr(claim_agent, "MODEL_CALL_LIMIT", 2)
    model = script(
        calls("get_claim", {"claim_id": "CLM-1001"}, "1"),
        calls("get_claim", {"claim_id": "CLM-1001"}, "2"),
        calls("get_claim", {"claim_id": "CLM-1001"}, "3"),
    )
    line = claim_agent.try_claim("CLM-1001", model)
    assert line.startswith("CLM-1001: failed (ModelCallLimitExceededError")
    assert claim(backend, "CLM-1001")["failures"] == 1


def test_a_backend_call_that_times_out_is_tried_again(backend, monkeypatch):
    real_call = main.call
    timeouts = [httpx.ReadTimeout("timed out")]

    def call(method, path, body=None):
        if timeouts:
            raise timeouts.pop()
        return real_call(method, path, body)

    monkeypatch.setattr(main, "call", call)
    model = script(
        calls("get_claim", {"claim_id": "CLM-1001"}, "0"),
        *approve_and_pay().messages,
    )
    assert claim_agent.try_claim("CLM-1001", model) == "CLM-1001: approve $420.00, paid"
    results = [s for s in steps(backend, "CLM-1001") if s["name"] == "get_claim"]
    assert "Rome" in results[1]["content"]


def test_an_error_after_the_decision_leaves_it_as_it_is(backend, monkeypatch):
    real_call = main.call

    def call(method, path, body=None):
        if path.endswith("/payment"):
            raise httpx.ConnectError("The backend went away")
        return real_call(method, path, body)

    monkeypatch.setattr(main, "call", call)
    line = claim_agent.try_claim("CLM-1001", approve_and_pay())
    assert line == (
        "CLM-1001: approve $420.00, not paid,"
        " after an error: ConnectError: The backend went away"
    )
    record = claim(backend, "CLM-1001")
    assert record["status"] == "decided"
    assert record["decision"]["payout"] == 420
    assert record["payment"] is None
    assert record["failures"] == 0
    decided = [s for s in steps(backend, "CLM-1001") if s["name"] == "decide_claim"]
    assert len(decided) == 2


def test_the_system_prompt_is_the_instructions_alone(backend):
    prompt = claim_agent.instructions(main.backend())
    assert prompt == backend.get("/api/instructions").json()["claim"]
    assert "held until a handler signs off" in prompt
    assert "## 10. How we work out your payment" not in prompt


def test_records_the_sections_it_reads(backend):
    model = script(
        calls("list_sections", {"document": "claims-manual"}, "1"),
        calls("read_section", {"document": "claims-manual", "number": 7}, "2"),
        AIMessage(content="Read the notes."),
    )
    claim_agent.run_claim(main.backend(), "CLM-1020", "thread-4", model)
    recorded = steps(backend, "CLM-1020")
    assert [(s["kind"], s["name"]) for s in recorded] == [
        ("tool_call", "list_sections"),
        ("tool_result", "list_sections"),
        ("tool_call", "read_section"),
        ("tool_result", "read_section"),
        ("reply", ""),
    ]
    assert "Wild animals" in recorded[1]["content"]
    assert json.loads(recorded[2]["content"]) == {
        "document": "claims-manual",
        "number": 7,
    }
    section = json.loads(recorded[3]["content"])
    assert section["title"] == "Interpretation notes"
    assert "Monkeys, gulls, bears" in section["text"]


def test_steps_skip_other_messages():
    assert claim_agent.steps(HumanMessage(content="Hello")) == []
