"""Stub models for the agent's tests, which never call a real model."""

import re
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

REASON = "The delay was over the waiting period. The receipts total $420.00."


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    errors: list[Any] = []
    seen: list[Any] = []

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, *args, **kwargs):
        self.seen.append(messages)
        if self.errors:
            raise self.errors.pop(0)
        return super()._generate(messages, *args, **kwargs)


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


class ClaimStub(BaseChatModel):
    """A claim agent's model that decides each claim as scripted, an action a try.

    An action is an exception to raise or a (decision, payout) pair to record.
    """

    actions: dict[str, list[Any]]

    @property
    def _llm_type(self) -> str:
        return "claim-stub"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, *args, **kwargs):
        last = messages[-1]
        if isinstance(last, ToolMessage):
            reply = AIMessage(content="Done.")
        else:
            claim_id = re.findall(r"CLM-\d+", last.text)[0]
            action = self.actions[claim_id].pop(0)
            if isinstance(action, Exception):
                raise action
            reply = calls("decide_claim", decision(claim_id, *action), "decide")
        return ChatResult(generations=[ChatGeneration(message=reply)])
