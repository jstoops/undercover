"""The queue agent: plans a run as a to-do list and hands out each claim."""

import json
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    TodoListMiddleware,
    hook_config,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langgraph.runtime import Runtime

from agent import claim_agent, main

MAX_NUDGES = 3
CLAIM_FIELDS = (
    "claim_id",
    "claim_type",
    "summary",
    "amount_claimed",
    "submitted_on",
    "failures",
)
TODO_TOOL = (
    "Write your to-do list for this run. It replaces the whole list, so send every"
    " item each time, in order. Each item has its content, starting with its claim"
    " id, and a status: pending, in_progress or completed."
)


@dataclass
class Run:
    """A run of the queue: its id, its cap and the claims it has started."""

    run_id: int
    cap: int
    started: set[str] = field(default_factory=set)
    lock: threading.Lock = field(default_factory=threading.Lock)

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


def waiting_claims() -> list[dict[str, Any]]:
    """Return the claims waiting in the queue, in order."""
    with main.backend() as client:
        claims = client.get("/api/claims").raise_for_status().json()
    return [claim for claim in claims if claim["status"] == "waiting"]


def queue_tools(run: Run) -> list[BaseTool]:
    """Return the queue agent's tools for this run."""

    @tool
    def list_waiting_claims() -> str:
        """List the waiting claims: id, type, summary, amount, date and failures."""
        claims = waiting_claims()
        return json.dumps([{key: c[key] for key in CLAIM_FIELDS} for c in claims])

    @tool
    def work_claim(claim_id: str) -> str:
        """Hand one waiting claim to a fresh claim agent and get its one-line report."""
        waiting = claim_id in {claim["claim_id"] for claim in waiting_claims()}
        if waiting and not run.reserve(claim_id):
            return (
                f"The cap of {run.cap} claims is reached, so {claim_id} stays waiting"
            )
        return claim_agent.try_claim(claim_id)

    return [list_waiting_claims, work_claim]


class MissedClaimsCheck(AgentMiddleware[AgentState[Any], Any, Any]):
    """Before the queue agent finishes, send it back to claims within its cap."""

    def __init__(self, run: Run) -> None:
        super().__init__()
        self.run = run
        self.nudges = 0

    @hook_config(can_jump_to=["model"])
    def after_model(
        self, state: AgentState[Any], runtime: Runtime[Any]
    ) -> dict[str, Any] | None:
        """When the agent replies without a tool call, look for missed claims."""
        last = state["messages"][-1]
        if not isinstance(last, AIMessage) or last.tool_calls:
            return None
        if self.nudges >= MAX_NUDGES:
            return None
        waiting = [claim["claim_id"] for claim in waiting_claims()]
        missed = self.run.within_reach(waiting)
        if not missed:
            return None
        self.nudges += 1
        reminder = (
            f"Before you finish: {', '.join(missed)} still waiting within your cap of"
            f" {self.run.cap} claims. Work them with work_claim, then write your"
            " summary."
        )
        return {"messages": [HumanMessage(content=reminder)], "jump_to": "model"}


def instructions(client: httpx.Client) -> str:
    """Return the queue agent's instructions, fetched through the API."""
    return client.get("/api/instructions").raise_for_status().json()["queue"]


def save_todos(client: httpx.Client, run_id: int, todos: list[dict[str, str]]) -> None:
    """Save the queue agent's to-do list, so the dashboard shows it."""
    client.put(f"/api/runs/{run_id}/todos", json={"todos": todos}).raise_for_status()


def finish(client: httpx.Client, run_id: int, outcome: str, summary: str) -> None:
    """Record how the run ended, and its summary."""
    client.post(
        f"/api/runs/{run_id}/finish", json={"outcome": outcome, "summary": summary}
    ).raise_for_status()


def report(client: httpx.Client, run: Run, update: dict[str, Any]) -> str | None:
    """Save a new to-do list, print each claim's report, and return any final reply."""
    reply = None
    for node in main.updates_in(update):
        if "todos" in node:
            save_todos(client, run.run_id, node["todos"])
        for message in node.get("messages", []):
            if isinstance(message, ToolMessage) and message.name == "work_claim":
                print(message.text, flush=True)
            if (
                isinstance(message, AIMessage)
                and message.text
                and not message.tool_calls
            ):
                reply = message.text
    return reply


def run_queue(cap: int, llm: BaseChatModel | None = None) -> str:
    """Work the waiting claims, up to the cap, and return the summary for handlers."""
    with main.backend() as client:
        started = client.post("/api/runs", json={"cap": cap}).raise_for_status()
        run = Run(started.json()["run_id"], cap)
        middleware: list[AgentMiddleware[Any, Any, Any]] = [
            TodoListMiddleware(system_prompt="", tool_description=TODO_TOOL),
            main.model_retries(),
            MissedClaimsCheck(run),
        ]
        agent = create_agent(
            llm or main.model(),
            tools=queue_tools(run),
            system_prompt=instructions(client),
            middleware=middleware,
        )
        request = f"Please work the queue. Your cap for this run is {cap} claims."
        summary = ""
        try:
            for update in agent.stream(
                {"messages": [{"role": "user", "content": request}]},
                config={"configurable": {"thread_id": str(uuid.uuid4())}},
                stream_mode="updates",
            ):
                summary = report(client, run, update) or summary
        except Exception as error:
            finish(client, run.run_id, "stopped", f"The run stopped: {error!r}")
            raise
        finish(client, run.run_id, "finished", summary)
    return summary
