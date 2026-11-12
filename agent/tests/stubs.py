"""Stub models for the agent's tests, which never call a real model."""

from typing import Any

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

REASON = "The delay was over the waiting period. The receipts total $420.00."


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    errors: list[Any] = []

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, *args, **kwargs):
        if self.errors:
            raise self.errors.pop(0)
        return super()._generate(*args, **kwargs)


def script(*replies, errors=()):
    """A stub that raises each of the errors in turn, then gives the replies."""
    return StubModel(messages=iter(replies), errors=list(errors))


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
