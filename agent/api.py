"""The UnderCover backend's API: every call the agent makes, and where it goes."""

from typing import Any, Literal

import httpx

BASE_URL = "http://127.0.0.1:8000/api"
TIMEOUT = 30

Document = Literal["policy-wording", "claims-manual"]
DecisionKind = Literal["approve", "decline", "refer"]
Json = dict[str, Any]

client = httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)


class Refused(Exception):
    """The backend refused a request and said why, such as a claim already decided."""

    def __init__(self, detail: Any) -> None:
        super().__init__(detail)
        self.detail = detail


def call(method: str, path: str, body: Json | None = None) -> Any:
    """Call the backend and return its reply, or raise Refused when it says no."""
    response = client.request(method, path, json=body)
    if response.is_client_error:
        raise Refused(response.json()["detail"])
    return response.raise_for_status().json()


def list_claims() -> list[Json]:
    """The claims queue, with each claim's status and decision."""
    return call("GET", "/claims")


def waiting_claims() -> list[Json]:
    """The claims waiting in the queue, in order."""
    return [claim for claim in list_claims() if claim["status"] == "waiting"]


def get_claim(claim_id: str) -> Json:
    """A claim in full, with its decision, sign-off and payment."""
    return call("GET", f"/claims/{claim_id}")


def get_policy(policy_id: str) -> Json:
    """A policy: its plan, add-ons, purchase date, trip and travelers."""
    return call("GET", f"/policies/{policy_id}")


def get_customer(customer_id: str) -> Json:
    """A customer's name, customer-since date and earlier claims."""
    return call("GET", f"/customers/{customer_id}")


def list_sections(document: Document) -> list[Json]:
    """The sections of the policy wording or the claims manual, with their topics."""
    return call("GET", f"/documents/{document}/sections")


def read_section(document: Document, number: int) -> Json:
    """One section of the policy wording or the claims manual."""
    return call("GET", f"/documents/{document}/sections/{number}")


def get_instructions() -> dict[str, str]:
    """The agent's instructions: for running the queue and for working a claim."""
    return call("GET", "/instructions")


def start_claim(claim_id: str) -> Json:
    """Mark a waiting claim as in progress."""
    return call("POST", f"/claims/{claim_id}/start")


def add_step(claim_id: str, thread_id: str, kind: str, name: str, content: str) -> None:
    """Record one step the agent took on a claim."""
    step = {"thread_id": thread_id, "kind": kind, "name": name, "content": content}
    call("POST", f"/claims/{claim_id}/steps", step)


def fail_claim(claim_id: str, thread_id: str, reason: str) -> Json:
    """Record that the agent failed on a claim, which goes back in the queue."""
    failure = {"thread_id": thread_id, "reason": reason}
    return call("POST", f"/claims/{claim_id}/failure", failure)


def decide_claim(
    claim_id: str,
    decision: DecisionKind,
    payout: float,
    reason: str,
    policy_section: str,
) -> Json:
    """Record the decision on a claim in progress."""
    return call(
        "POST",
        f"/claims/{claim_id}/decision",
        {
            "decision": decision,
            "payout": payout,
            "reason": reason,
            "policy_section": policy_section,
        },
    )


def pay_claim(claim_id: str, amount: float) -> Json:
    """Pay a claim's approved payout."""
    return call("POST", f"/claims/{claim_id}/payment", {"amount": amount})


def start_run(cap: int) -> int:
    """Start a run of the queue and return its id."""
    return call("POST", "/runs", {"cap": cap})["run_id"]


def save_todos(run_id: int, todos: list[Any]) -> None:
    """Save a run's to-do list as it now stands."""
    call("PUT", f"/runs/{run_id}/todos", {"todos": todos})


def finish_run(run_id: int, outcome: str, summary: str) -> None:
    """Record how a run ended, finished or stopped, and its summary."""
    call("POST", f"/runs/{run_id}/finish", {"outcome": outcome, "summary": summary})
