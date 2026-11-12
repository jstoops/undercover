"""Work the claims queue: uv run -m agent, or uv run -m agent CLM-1001 for one claim."""

import sys
import uuid
from typing import Any

from agent import main


def waiting_claims() -> list[str]:
    """Return the ids of the claims waiting in the queue, in order."""
    with main.backend() as client:
        claims = client.get("/api/claims").raise_for_status().json()
    return [claim["claim_id"] for claim in claims if claim["status"] == "waiting"]


def outcome(claim: dict[str, Any]) -> str:
    """Say in one line where a claim stands."""
    decision = claim["decision"]
    if decision is None:
        return f"{claim['claim_id']}: no decision yet"
    if decision["decision"] != "approve":
        return f"{claim['claim_id']}: {decision['decision']}"
    if claim["payment"]:
        state = "paid"
    elif claim["status"] == "awaiting_sign_off":
        state = "waiting for sign-off"
    else:
        state = "not paid"
    return f"{claim['claim_id']}: approve ${decision['payout']:,.2f}, {state}"


def work_queue(claim_ids: list[str]) -> None:
    """Run the agent on the claims given, or on every waiting claim."""
    for claim_id in claim_ids or waiting_claims():
        reply = main.run(claim_id, str(uuid.uuid4()))
        with main.backend() as client:
            claim = client.get(f"/api/claims/{claim_id}").raise_for_status().json()
        print(outcome(claim))
        print(f"  {reply}")


if __name__ == "__main__":
    work_queue(sys.argv[1:])
