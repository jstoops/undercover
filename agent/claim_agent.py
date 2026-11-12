"""The claim agent: works one claim from a clean start and reports back in one line."""

import json
import uuid
from typing import Any, Literal

import httpx
from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ToolRetryMiddleware,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import tool

from agent import main

Document = Literal["policy-wording", "claims-manual"]
TOOL_RETRIES = 2
MODEL_CALL_LIMIT = 30


@tool
def get_claim(claim_id: str) -> str:
    """Read a claim: the customer's story, the items claimed and the documents."""
    return main.call("GET", f"/api/claims/{claim_id}")


@tool
def get_policy(policy_id: str) -> str:
    """Read the policy named on a claim: plan, add-ons, dates, trip and travelers."""
    return main.call("GET", f"/api/policies/{policy_id}")


@tool
def get_customer(customer_id: str) -> str:
    """Read the customer named on a claim: their name and earlier claims."""
    return main.call("GET", f"/api/customers/{customer_id}")


@tool
def list_sections(document: Document) -> str:
    """List the sections of the policy wording or the claims manual, with topics."""
    return main.call("GET", f"/api/documents/{document}/sections")


@tool
def read_section(document: Document, number: int) -> str:
    """Read one numbered section of the policy wording or the claims manual."""
    return main.call("GET", f"/api/documents/{document}/sections/{number}")


@tool
def decide_claim(
    claim_id: str,
    decision: Literal["approve", "decline", "refer"],
    payout: float,
    reason: str,
    policy_section: str,
) -> str:
    """Record your decision on a claim. A decline or a referral has a payout of 0."""
    return main.call(
        "POST",
        f"/api/claims/{claim_id}/decision",
        {
            "decision": decision,
            "payout": payout,
            "reason": reason,
            "policy_section": policy_section,
        },
    )


@tool
def pay_claim(claim_id: str, amount: float) -> str:
    """Pay a claim's approved payout. Over $1,000 it waits for a handler's sign-off."""
    return main.call("POST", f"/api/claims/{claim_id}/payment", {"amount": amount})


TOOLS = [
    get_claim,
    get_policy,
    get_customer,
    list_sections,
    read_section,
    decide_claim,
    pay_claim,
]


def instructions(client: httpx.Client) -> str:
    """Return the claim agent's instructions, fetched through the API."""
    return client.get("/api/instructions").raise_for_status().json()["instructions"]


def steps(message: BaseMessage) -> list[dict[str, str]]:
    """Turn one of the agent's messages into the steps the dashboard shows."""
    if isinstance(message, ToolMessage):
        return [
            {"kind": "tool_result", "name": message.name or "", "content": message.text}
        ]
    if not isinstance(message, AIMessage):
        return []
    said = [{"kind": "reply", "name": "", "content": message.text}]
    calls = [
        {"kind": "tool_call", "name": c["name"], "content": json.dumps(c["args"])}
        for c in message.tool_calls
    ]
    return (said if message.text else []) + calls


def run_claim(
    client: httpx.Client, claim_id: str, thread_id: str, llm: BaseChatModel
) -> None:
    """Run the claim agent on a claim in progress, recording each step as it goes."""
    middleware: list[AgentMiddleware[Any, Any, Any]] = [
        main.model_retries(),
        ToolRetryMiddleware(
            max_retries=TOOL_RETRIES,
            retry_on=(httpx.TransportError,),
            on_failure="error",
            initial_delay=main.RETRY_DELAY,
        ),
        ModelCallLimitMiddleware(run_limit=MODEL_CALL_LIMIT, exit_behavior="error"),
    ]
    agent = create_agent(
        llm, tools=TOOLS, system_prompt=instructions(client), middleware=middleware
    )
    for update in agent.stream(
        {"messages": [{"role": "user", "content": f"Please decide {claim_id}."}]},
        config={"configurable": {"thread_id": thread_id}},
        stream_mode="updates",
    ):
        for message in main.messages_in(update):
            for step in steps(message):
                client.post(
                    f"/api/claims/{claim_id}/steps",
                    json={"thread_id": thread_id, **step},
                ).raise_for_status()


def outcome(claim: dict[str, Any]) -> str:
    """Say in one line how a claim was decided, from its record."""
    decision = claim["decision"]
    if decision["decision"] != "approve":
        return f"{claim['claim_id']}: {decision['decision']}"
    if claim["payment"]:
        state = "paid"
    elif claim["status"] == "awaiting_sign_off":
        state = "waiting for sign-off"
    else:
        state = "not paid"
    return f"{claim['claim_id']}: approve ${decision['payout']:,.2f}, {state}"


def failed(claim: dict[str, Any], reason: str) -> str:
    """Say in one line that a claim failed, and where it went."""
    if claim["status"] == "left_for_handler":
        return f"{claim['claim_id']}: failed again ({reason}), left for a handler"
    return f"{claim['claim_id']}: failed ({reason}), back in the queue for another try"


def try_claim(claim_id: str, llm: BaseChatModel | None = None) -> str:
    """Work one claim on a fresh thread and say in one line how it ended."""
    thread_id = str(uuid.uuid4())
    with main.backend() as client:
        started = client.post(f"/api/claims/{claim_id}/start")
        if started.is_error:
            return f"{started.json()['detail']}, so there is nothing to do"
        error = None
        try:
            run_claim(client, claim_id, thread_id, llm or main.model())
        except Exception as raised:  # One bad claim must never stop the run.
            error = f"{type(raised).__name__}: {raised}"[:300]
        claim = client.get(f"/api/claims/{claim_id}").raise_for_status().json()
        if claim["status"] != "in_progress":
            return outcome(claim) + (f", after an error: {error}" if error else "")
        reason = error or "the agent finished without recording a decision"
        response = client.post(
            f"/api/claims/{claim_id}/failure",
            json={"thread_id": thread_id, "reason": reason},
        )
        return failed(response.raise_for_status().json(), reason)
