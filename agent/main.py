"""The UnderCover Agent."""

import json
import os
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

BACKEND_URL = "http://127.0.0.1:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "z-ai/glm-5.3-flash"
DEFAULT_IGNORED_PROVIDERS = "wafer"
MODEL_TIMEOUT = 120

Document = Literal["policy-wording", "claims-manual"]


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


def call(method: str, path: str, body: dict[str, Any] | None = None) -> str:
    """Call the backend and return its reply as text, refusals included."""
    with backend() as client:
        return client.request(method, path, json=body).text


@tool
def get_claim(claim_id: str) -> str:
    """Read a claim: the customer's story, the items claimed and the documents."""
    return call("GET", f"/api/claims/{claim_id}")


@tool
def get_policy(policy_id: str) -> str:
    """Read the policy named on a claim: plan, add-ons, dates, trip and travelers."""
    return call("GET", f"/api/policies/{policy_id}")


@tool
def get_customer(customer_id: str) -> str:
    """Read the customer named on a claim: their name and earlier claims."""
    return call("GET", f"/api/customers/{customer_id}")


@tool
def list_sections(document: Document) -> str:
    """List the sections of the policy wording or the claims manual, with topics."""
    return call("GET", f"/api/documents/{document}/sections")


@tool
def read_section(document: Document, number: int) -> str:
    """Read one numbered section of the policy wording or the claims manual."""
    return call("GET", f"/api/documents/{document}/sections/{number}")


@tool
def decide_claim(
    claim_id: str,
    decision: Literal["approve", "decline", "refer"],
    payout: float,
    reason: str,
    policy_section: str,
) -> str:
    """Record your decision on a claim. A decline or a referral has a payout of 0."""
    return call(
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
    return call("POST", f"/api/claims/{claim_id}/payment", {"amount": amount})


TOOLS = [
    get_claim,
    get_policy,
    get_customer,
    list_sections,
    read_section,
    decide_claim,
    pay_claim,
]


def ignored_providers() -> list[str]:
    """Return the OpenRouter providers to skip: OPENROUTER_IGNORE, or Wafer."""
    names = os.getenv("OPENROUTER_IGNORE", DEFAULT_IGNORED_PROVIDERS).split(",")
    return [name.strip() for name in names if name.strip()]


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GLM 5.3 Flash by default."""
    name = os.getenv("MODEL_NAME")
    ignore = ignored_providers()
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
        timeout=MODEL_TIMEOUT,
        extra_body={"provider": {"ignore": ignore}} if ignore else None,
    )


def system_prompt(client: httpx.Client) -> str:
    """Return the agent's instructions, fetched through the API."""
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


def messages_in(update: dict[str, Any]) -> list[BaseMessage]:
    """Return the new messages in one streamed update from the agent."""
    return [m for node in update.values() for m in (node or {}).get("messages", [])]


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Work one claim, recording each step with the backend, and return the reply."""
    with backend() as client:
        client.post(f"/api/claims/{claim_id}/start").raise_for_status()
        agent = create_agent(
            llm or model(), tools=TOOLS, system_prompt=system_prompt(client)
        )
        reply = ""
        for update in agent.stream(
            {"messages": [{"role": "user", "content": f"Please decide {claim_id}."}]},
            config={"configurable": {"thread_id": thread_id}},
            stream_mode="updates",
        ):
            for message in messages_in(update):
                for step in steps(message):
                    client.post(
                        f"/api/claims/{claim_id}/steps",
                        json={"thread_id": thread_id, **step},
                    ).raise_for_status()
                if isinstance(message, AIMessage) and message.text:
                    reply = message.text
    return reply
