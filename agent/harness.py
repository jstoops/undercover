"""The UnderCover Agent's harness: the model, the middleware and the two agents.

The queue agent plans a run as a to-do list and hands each claim to a claim
agent, which works it from a clean start. Their tools are in agent/tools.py,
and every call to the backend is in agent/api.py.
"""

import json
import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any, cast

import httpx
from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
    TodoListMiddleware,
    ToolCallRequest,
    ToolErrorMiddleware,
    ToolRetryMiddleware,
    hook_config,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import SecretStr

from agent import api, tools

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "z-ai/glm-5.3-flash"
DEFAULT_IGNORED_PROVIDERS = "wafer"
MODEL_TIMEOUT = 120
MODEL_RETRIES = 3
TOOL_RETRIES = 2
RETRY_DELAY = 1.0
MODEL_CALL_LIMIT = 30
MAX_REMINDERS = 3
TODO_TOOL = (
    "Write your to-do list for this run. It replaces the whole list, so send every"
    " item each time, in order. Each item has its content, starting with its claim"
    " id, and a status: pending, in_progress or completed."
)

Agent = CompiledStateGraph[Any, Any, Any, Any]
Middleware = AgentMiddleware[Any, Any, Any]
ToolHandler = Callable[[ToolCallRequest], ToolMessage | Command[Any]]


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


def model_retries() -> ModelRetryMiddleware:
    """Try a failed model call again, such as a provider error or a timeout."""
    return ModelRetryMiddleware(
        max_retries=MODEL_RETRIES, initial_delay=RETRY_DELAY, on_failure="error"
    )


def show_refusal(error: Exception, request: ToolCallRequest) -> str | None:
    """Show the model the backend's refusal, such as a payment held for sign-off."""
    if isinstance(error, api.Refused):
        return json.dumps({"detail": error.detail})
    return None


@dataclass(frozen=True)
class ClaimContext:
    """The claim a claim agent is working, and the thread that labels this try."""

    claim_id: str
    thread_id: str


class RecordSteps(AgentMiddleware[AgentState[Any], ClaimContext, Any]):
    """Record each reply, tool call and tool result of a claim agent on its claim."""

    def after_model(
        self, state: AgentState[Any], runtime: Runtime[ClaimContext]
    ) -> dict[str, Any] | None:
        """Record what the model said and the tools it called."""
        message = state["messages"][-1]
        if isinstance(message, AIMessage):
            steps = [("reply", "", message.text)] if message.text else []
            steps += [
                ("tool_call", call["name"], json.dumps(call["args"]))
                for call in message.tool_calls
            ]
            for kind, name, content in steps:
                record(runtime.context, kind, name, content)
        return None

    def wrap_tool_call(
        self, request: ToolCallRequest, handler: ToolHandler
    ) -> ToolMessage | Command[Any]:
        """Record what a tool returned, refusals included."""
        result = handler(request)
        if isinstance(result, ToolMessage):
            context = cast(ClaimContext, request.runtime.context)
            record(context, "tool_result", result.name or "", result.text)
        return result


def record(context: ClaimContext, kind: str, name: str, content: str) -> None:
    """Record one step on the claim being worked."""
    api.add_step(context.claim_id, context.thread_id, kind, name, content)


class ShowProgress(AgentMiddleware[AgentState[Any], tools.RunContext, Any]):
    """Show how a run is going: its to-do list on the dashboard, each claim's report."""

    def wrap_tool_call(
        self, request: ToolCallRequest, handler: ToolHandler
    ) -> ToolMessage | Command[Any]:
        """Save each new to-do list, and print each claim's one-line report."""
        result = handler(request)
        call = request.tool_call
        if call["name"] == "write_todos" and isinstance(result, Command):
            run = cast(tools.RunContext, request.runtime.context)
            api.save_todos(run.run_id, call["args"]["todos"])
        if call["name"] == "work_claim" and isinstance(result, ToolMessage):
            print(result.text, flush=True)
        return result


class MissedClaimsCheck(AgentMiddleware[AgentState[Any], tools.RunContext, Any]):
    """Before the queue agent finishes, send it back to claims within its cap."""

    @hook_config(can_jump_to=["model"])
    def after_model(
        self, state: AgentState[Any], runtime: Runtime[tools.RunContext]
    ) -> dict[str, Any] | None:
        """When the agent replies without a tool call, look for claims it missed."""
        last = state["messages"][-1]
        run = runtime.context
        if not isinstance(last, AIMessage) or last.tool_calls:
            return None
        if run.reminders >= MAX_REMINDERS:
            return None
        missed = run.within_reach([claim["claim_id"] for claim in api.waiting_claims()])
        if not missed:
            return None
        run.reminders += 1
        reminder = (
            f"Before you finish: {', '.join(missed)} still waiting within your cap of"
            f" {run.cap} claims. Work them with work_claim, then write your summary."
        )
        return {"messages": [HumanMessage(content=reminder)], "jump_to": "model"}


def claim_agent(model: BaseChatModel) -> Agent:
    """Build a claim agent, which works one claim from a clean start each time."""
    middleware: list[Middleware] = [
        RecordSteps(),
        ToolErrorMiddleware(on_error=show_refusal),
        ToolRetryMiddleware(
            max_retries=TOOL_RETRIES,
            retry_on=(httpx.TransportError,),
            initial_delay=RETRY_DELAY,
            on_failure="error",
        ),
        model_retries(),
        ModelCallLimitMiddleware(run_limit=MODEL_CALL_LIMIT, exit_behavior="error"),
    ]
    return create_agent(
        model,
        tools=tools.CLAIM_TOOLS,
        system_prompt=api.get_instructions()["claim"],
        middleware=middleware,
        context_schema=ClaimContext,
    )


def queue_agent(model: BaseChatModel) -> Agent:
    """Build the queue agent, which plans a run and hands out each claim."""
    middleware: list[Middleware] = [
        TodoListMiddleware(system_prompt="", tool_description=TODO_TOOL),
        ShowProgress(),
        model_retries(),
        MissedClaimsCheck(),
    ]
    return create_agent(
        model,
        tools=tools.QUEUE_TOOLS,
        system_prompt=api.get_instructions()["queue"],
        middleware=middleware,
        context_schema=tools.RunContext,
    )


def outcome(claim: api.Json) -> str:
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


def failure(claim: api.Json, reason: str) -> str:
    """Say in one line that a claim failed, and where it went."""
    if claim["status"] == "left_for_handler":
        return f"{claim['claim_id']}: failed again ({reason}), left for a handler"
    return f"{claim['claim_id']}: failed ({reason}), back in the queue for another try"


def try_claim(claim_id: str, agent: Agent) -> str:
    """Have a claim agent work one claim, put right any failure, and report."""
    try:
        api.start_claim(claim_id)
    except api.Refused as refused:
        return f"{refused.detail}, so there is nothing to do"
    context = ClaimContext(claim_id, thread_id=str(uuid.uuid4()))
    request = {"role": "user", "content": f"Please decide {claim_id}."}
    error = None
    try:
        agent.invoke({"messages": [request]}, context=context)
    except Exception as raised:  # One bad claim must never stop the run.
        error = f"{type(raised).__name__}: {raised}"[:300]
    claim = api.get_claim(claim_id)
    if claim["status"] != "in_progress":
        return outcome(claim) + (f", after an error: {error}" if error else "")
    reason = error or "the agent finished without recording a decision"
    return failure(api.fail_claim(claim_id, context.thread_id, reason), reason)


def work_claim(claim_id: str, model: BaseChatModel) -> str:
    """Work one claim with a claim agent of its own, and report in one line."""
    return try_claim(claim_id, claim_agent(model))


def run_queue(cap: int, model: BaseChatModel) -> str:
    """Work the waiting claims, up to the cap, and return the summary for handlers."""
    claims, queue = claim_agent(model), queue_agent(model)
    run = tools.RunContext(api.start_run(cap), cap, partial(try_claim, agent=claims))
    request = f"Please work the queue. Your cap for this run is {cap} claims."
    try:
        state = queue.invoke(
            {"messages": [{"role": "user", "content": request}]}, context=run
        )
    except Exception as error:
        api.finish_run(run.run_id, "stopped", f"The run stopped: {error!r}")
        raise
    summary = state["messages"][-1].text
    api.finish_run(run.run_id, "finished", summary)
    return summary
