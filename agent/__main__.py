"""Work the claims queue.

uv run -m agent works every waiting claim, uv run -m agent --cap 5 works up to
five, and uv run -m agent CLM-1001 works one claim.
"""

import argparse

from agent import claim_agent, queue_agent


def run(argv: list[str] | None = None) -> None:
    """Run the queue agent on the queue, or the claim agent on one claim."""
    parser = argparse.ArgumentParser(prog="uv run -m agent")
    parser.add_argument("claim_id", nargs="?", help="work just this claim")
    parser.add_argument("--cap", type=int, help="work at most this many claims")
    args = parser.parse_args(argv)
    if args.claim_id:
        print(claim_agent.try_claim(args.claim_id))
        return
    cap = args.cap or len(queue_agent.waiting_claims())
    if cap == 0:
        print("No claims are waiting.")
        return
    print(queue_agent.run_queue(cap))


if __name__ == "__main__":
    run()
