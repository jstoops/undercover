import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage

from agent import main
from backend.main import app

REASON = "The delay was over the waiting period. The receipts total $420.00."


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


def script(*replies):
    return StubModel(messages=iter(replies))


def calls(name, args, call_id):
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": call_id}]
    )


def decision(claim_id, kind, payout):
    return {
        "claim_id": claim_id,
        "decision": kind,
        "payout": payout,
        "reason": REASON,
        "policy_section": "Section 3, Trip Delay",
    }


@pytest.fixture
def backend(client, monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    return client


def test_run_approves_and_pays(backend):
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
    assert main.run("CLM-1001", "thread-1", model) == "Approved $420.00 and paid."
    claim = backend.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["decision"]["reason"] == REASON
    assert claim["payment"]["amount"] == 420
    steps = backend.get("/api/claims/CLM-1001/steps").json()
    assert [(s["kind"], s["name"]) for s in steps] == [
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
    assert {s["thread_id"] for s in steps} == {"thread-1"}
    assert '"claim_id": "CLM-1001"' in steps[1]["content"]
    assert "Rome" in steps[2]["content"]
    assert steps[-1]["content"] == "Approved $420.00 and paid."


def test_run_cannot_pay_over_the_limit(backend):
    model = script(
        calls("get_claim", {"claim_id": "CLM-1003"}, "1"),
        calls("decide_claim", decision("CLM-1003", "approve", 3750), "2"),
        calls("pay_claim", {"claim_id": "CLM-1003", "amount": 3750}, "3"),
        AIMessage(content="Approved $3,750.00; waiting for a handler's sign-off."),
    )
    main.run("CLM-1003", "thread-2", model)
    claim = backend.get("/api/claims/CLM-1003").json()
    assert claim["status"] == "awaiting_sign_off"
    assert claim["payment"] is None
    paid = backend.get("/api/claims/CLM-1003/steps").json()[-2]
    assert paid["kind"] == "tool_result"
    assert paid["name"] == "pay_claim"
    assert "held until a handler signs off" in paid["content"]


def test_run_declines(backend):
    model = script(
        calls("decide_claim", decision("CLM-1004", "decline", 0), "1"),
        AIMessage(content="Declined."),
    )
    main.run("CLM-1004", "thread-3", model)
    claim = backend.get("/api/claims/CLM-1004").json()
    assert claim["status"] == "decided"
    assert claim["decision"]["decision"] == "decline"
    assert claim["payment"] is None


def test_run_refuses_a_decided_claim(backend):
    refer = calls("decide_claim", decision("CLM-1004", "refer", 0), "1")
    main.run("CLM-1004", "t", script(refer, AIMessage(content="Referred.")))
    with pytest.raises(Exception, match="409 Conflict"):
        main.run("CLM-1004", "t", script(AIMessage(content="Again.")))


def test_system_prompt_is_the_instructions_alone(backend):
    prompt = main.system_prompt(main.backend())
    assert prompt == backend.get("/api/instructions").json()["instructions"]
    assert "held until a handler signs off" in prompt
    assert "## 10. How we work out your payment" not in prompt


def test_run_records_the_sections_it_reads(backend):
    model = script(
        calls("list_sections", {"document": "claims-manual"}, "1"),
        calls("read_section", {"document": "claims-manual", "number": 7}, "2"),
        AIMessage(content="Read the notes."),
    )
    main.run("CLM-1020", "thread-4", model)
    steps = backend.get("/api/claims/CLM-1020/steps").json()
    assert [(s["kind"], s["name"]) for s in steps] == [
        ("tool_call", "list_sections"),
        ("tool_result", "list_sections"),
        ("tool_call", "read_section"),
        ("tool_result", "read_section"),
        ("reply", ""),
    ]
    assert "Wild animals" in steps[1]["content"]
    assert json.loads(steps[2]["content"]) == {"document": "claims-manual", "number": 7}
    section = json.loads(steps[3]["content"])
    assert section["title"] == "Interpretation notes"
    assert "Monkeys, gulls, bears" in section["text"]


def test_steps_skip_other_messages():
    assert main.steps(HumanMessage(content="Hello")) == []


def payload(monkeypatch, **env):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    for name in ("MODEL_NAME", "OPENROUTER_IGNORE"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return main.model()._get_request_payload([HumanMessage(content="Hi")])


def test_the_default_model(monkeypatch):
    request = payload(monkeypatch)
    assert request["model"] == "z-ai/glm-5.3-flash"
    assert request["reasoning_effort"] == "low"
    assert request["extra_body"] == {"provider": {"ignore": ["wafer"]}}


def test_model_name(monkeypatch):
    request = payload(monkeypatch, MODEL_NAME="openrouter/free")
    assert request["model"] == "openrouter/free"
    assert "reasoning_effort" not in request
    assert request["extra_body"] == {"provider": {"ignore": ["wafer"]}}


@pytest.mark.parametrize("model_name", ["", "openrouter/free"])
def test_providers_to_skip(monkeypatch, model_name):
    env = {"MODEL_NAME": model_name} if model_name else {}
    request = payload(monkeypatch, OPENROUTER_IGNORE="wafer, deepinfra", **env)
    assert request["extra_body"] == {"provider": {"ignore": ["wafer", "deepinfra"]}}
    request = payload(monkeypatch, OPENROUTER_IGNORE="", **env)
    assert "extra_body" not in request
