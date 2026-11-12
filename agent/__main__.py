"""Work the claims queue: uv run -m agent, or uv run -m agent CLM-1001 for one claim."""

import sys

from agent import claim_agent, main


def waiting_claims() -> list[str]:
    """Return the ids of the claims waiting in the queue, in order."""
    with main.backend() as client:
        claims = client.get("/api/claims").raise_for_status().json()
    return [claim["claim_id"] for claim in claims if claim["status"] == "waiting"]


def work_queue(claim_ids: list[str]) -> None:
    """Work the claims given, or every waiting claim, printing how each one ended."""
    for claim_id in claim_ids or waiting_claims():
        print(claim_agent.try_claim(claim_id))


if __name__ == "__main__":
    work_queue(sys.argv[1:])
