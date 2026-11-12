"""The UnderCover Agent's tools: the claim agent's seven and the queue agent's two."""

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import ClassVar

from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from agent import api

CLAIM_FIELDS = (
    "claim_id",
    "claim_type",
    "summary",
    "amount_claimed",
    "submitted_on",
    "failures",
)


@tool
def get_claim(claim_id: str) -> api.Json:
    """Read a claim: the customer's story, the items claimed and the documents."""
    return api.get_claim(claim_id)


@tool
def get_policy(policy_id: str) -> api.Json:
    """Read the policy named on a claim: plan, add-ons, dates, trip and travelers."""
    return api.get_policy(policy_id)


@tool
def get_customer(customer_id: str) -> api.Json:
    """Read the customer named on a claim: their name and earlier claims."""
    return api.get_customer(customer_id)


@tool
def list_sections(document: api.Document) -> list[api.Json]:
    """List the sections of the policy wording or the claims manual, with topics."""
    return api.list_sections(document)


@tool
def read_section(document: api.Document, number: int) -> api.Json:
    """Read one numbered section of the policy wording or the claims manual."""
    return api.read_section(document, number)


@tool
def decide_claim(
    claim_id: str,
    decision: api.DecisionKind,
    payout: float,
    reason: str,
    policy_section: str,
) -> api.Json:
    """Record your decision on a claim. A decline or a referral has a payout of 0."""
    return api.decide_claim(claim_id, decision, payout, reason, policy_section)


@tool
def pay_claim(claim_id: str, amount: float) -> api.Json:
    """Pay a claim's approved payout. Over $1,000 it waits for a handler's sign-off."""
    return api.pay_claim(claim_id, amount)


CLAIM_TOOLS = [
    get_claim,
    get_policy,
    get_customer,
    list_sections,
    read_section,
    decide_claim,
    pay_claim,
]


@dataclass
class RunContext:
    """One run of the queue, as the queue agent's tools and middleware see it.

    work_claim hands one claim to a fresh claim agent and returns its report.
    """

    run_id: int
    cap: int
    work_claim: Callable[[str], str]
    started: set[str] = field(default_factory=set)
    reminders: int = 0
    lock: ClassVar[threading.Lock] = threading.Lock()

    def reserve(self, claim_id: str) -> bool:
        """Count a claim against the cap, unless the cap is reached; a retry is free."""
        with self.lock:
            if claim_id not in self.started and len(self.started) >= self.cap:
                return False
            self.started.add(claim_id)
            return True

    def within_reach(self, waiting: list[str]) -> list[str]:
        """Return the waiting claims the run can still work: retries, then new ones."""
        again = [claim_id for claim_id in waiting if claim_id in self.started]
        new = [claim_id for claim_id in waiting if claim_id not in self.started]
        return again + new[: self.cap - len(self.started)]


@tool
def list_waiting_claims() -> list[api.Json]:
    """List the waiting claims: id, type, summary, amount, date and failures."""
    return [{key: claim[key] for key in CLAIM_FIELDS} for claim in api.waiting_claims()]


@tool
def work_claim(claim_id: str, runtime: ToolRuntime[RunContext]) -> str:
    """Hand one waiting claim to a fresh claim agent and get its one-line report."""
    run = runtime.context
    waiting = claim_id in {claim["claim_id"] for claim in api.waiting_claims()}
    if waiting and not run.reserve(claim_id):
        return f"The cap of {run.cap} claims is reached, so {claim_id} stays waiting"
    return run.work_claim(claim_id)


QUEUE_TOOLS = [list_waiting_claims, work_claim]
