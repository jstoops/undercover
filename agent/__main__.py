"""Work the claims queue.

uv run -m agent works every waiting claim, uv run -m agent --cap 5 works up to
five, and uv run -m agent CLM-1001 works one claim.
"""

import argparse

from dotenv import load_dotenv

from agent import api, harness


def run(argv: list[str] | None = None) -> None:
    """Run the queue agent on the queue, or a claim agent on one claim."""
    parser = argparse.ArgumentParser(prog="uv run -m agent")
    parser.add_argument("claim_id", nargs="?", help="work just this claim")
    parser.add_argument("--cap", type=int, help="work at most this many claims")
    args = parser.parse_args(argv)
    if args.claim_id:
        print(harness.work_claim(args.claim_id, harness.model()))
        return
    cap = args.cap or len(api.waiting_claims())
    if cap == 0:
        print("No claims are waiting.")
        return
    print(harness.run_queue(cap, harness.model()))


if __name__ == "__main__":
    load_dotenv(override=True)
    run()
