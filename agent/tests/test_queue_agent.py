import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent import main, queue_agent
from agent.tests.stubs import ClaimStub, calls, script

BOOM = RuntimeError("The model provider is down")


@pytest.fixture
def claims(backend, monkeypatch):
    """Script the claim agents: an action for each try at each claim."""
    monkeypatch.setattr(main, "MODEL_RETRIES", 0)
    stub = ClaimStub(actions={})
    monkeypatch.setattr(main, "model", lambda: stub)
    return stub.actions


def work(*claim_ids):
    return [calls("work_claim", {"claim_id": c}, f"work-{c}") for c in claim_ids]


def todos(call_id, *items):
    return calls(
        "write_todos",
        {"todos": [{"content": c, "status": s} for c, s in items]},
        call_id,
    )


def status(backend, claim_id):
    return backend.get(f"/api/claims/{claim_id}").json()["status"]


def current_run(backend):
    return backend.get("/api/runs/current").json()


def test_the_todo_list_is_saved_and_shown(backend, claims, monkeypatch):
    claims["CLM-1001"] = [("approve", 420)]
    saved = []
    real_save = queue_agent.save_todos

    def save_todos(client, run_id, items):
        saved.append([item["status"] for item in items])
        real_save(client, run_id, items)

    monkeypatch.setattr(queue_agent, "save_todos", save_todos)
    summary = "Worked 1 claim: 1 approved."
    model = script(
        calls("list_waiting_claims", {}, "list"),
        todos("t1", ("CLM-1001: flight", "in_progress"), ("Summary", "pending")),
        *work("CLM-1001"),
        todos("t2", ("CLM-1001: flight", "completed"), ("Summary", "in_progress")),
        todos("t3", ("CLM-1001: flight", "completed"), ("Summary", "completed")),
        AIMessage(content=summary),
    )
    assert queue_agent.run_queue(1, model) == summary
    assert saved == [
        ["in_progress", "pending"],
        ["completed", "in_progress"],
        ["completed", "completed"],
    ]
    run = current_run(backend)
    assert run["status"] == "finished"
    assert run["summary"] == summary
    assert [(t["content"], t["status"]) for t in run["todos"]] == [
        ("CLM-1001: flight", "completed"),
        ("Summary", "completed"),
    ]
    system = model.seen[0][0]
    assert isinstance(system, SystemMessage)
    assert system.text.startswith("# The UnderCover Agent: running the queue")
    assert "Your cap for this run is 1 claims" in model.seen[0][1].text


def test_the_cap(backend, claims, capsys):
    claims.update({"CLM-1001": [("approve", 420)], "CLM-1002": [("decline", 0)]})
    model = script(
        *work("CLM-1001", "CLM-1002", "CLM-1003"), AIMessage(content="Done.")
    )
    queue_agent.run_queue(2, model)
    out = capsys.readouterr().out
    assert "CLM-1001: approve $420.00, not paid" in out
    assert "CLM-1002: decline" in out
    assert "The cap of 2 claims is reached, so CLM-1003 stays waiting" in out
    assert status(backend, "CLM-1003") == "waiting"
    assert backend.get("/api/claims/CLM-1003/steps").json() == []
    assert current_run(backend)["status"] == "finished"


def test_parallel_calls_keep_to_the_cap(backend, claims):
    claims.update({"CLM-1001": [("approve", 420)], "CLM-1002": [("approve", 420)]})
    both = AIMessage(
        content="",
        tool_calls=[
            {"name": "work_claim", "args": {"claim_id": c}, "id": c}
            for c in ("CLM-1001", "CLM-1002")
        ],
    )
    queue_agent.run_queue(1, script(both, AIMessage(content="Done.")))
    statuses = sorted([status(backend, "CLM-1001"), status(backend, "CLM-1002")])
    assert statuses == ["decided", "waiting"]


def test_a_failed_claim_does_not_stop_the_run(backend, claims):
    claims.update(
        {
            "CLM-1001": [BOOM, BOOM],
            "CLM-1002": [("approve", 420)],
            "CLM-1003": [("decline", 0)],
        }
    )
    model = script(
        *work("CLM-1001", "CLM-1002", "CLM-1003"),
        AIMessage(content="Done."),
        *work("CLM-1001"),
        AIMessage(content="Done, with CLM-1001 left for a handler."),
    )
    summary = queue_agent.run_queue(3, model)
    assert summary == "Done, with CLM-1001 left for a handler."
    assert status(backend, "CLM-1002") == "decided"
    assert status(backend, "CLM-1003") == "decided"
    assert status(backend, "CLM-1001") == "left_for_handler"


def test_a_failed_claim_goes_back_in_the_queue_and_is_tried_again(
    backend, claims, capsys
):
    claims["CLM-1001"] = [BOOM, ("approve", 420)]
    model = script(*work("CLM-1001", "CLM-1001"), AIMessage(content="Done."))
    queue_agent.run_queue(1, model)
    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        "CLM-1001: failed (RuntimeError: The model provider is down),"
        " back in the queue for another try",
        "CLM-1001: approve $420.00, not paid",
    ]
    claim = backend.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["failures"] == 1


def test_a_claim_that_fails_twice_is_left_for_a_handler(backend, claims, capsys):
    claims["CLM-1001"] = [BOOM, BOOM]
    model = script(
        todos("t1", ("CLM-1001: flight", "in_progress")),
        *work("CLM-1001", "CLM-1001", "CLM-1001"),
        todos("t2", ("CLM-1001: flight", "completed")),
        AIMessage(content="Done."),
    )
    queue_agent.run_queue(1, model)
    lines = capsys.readouterr().out.splitlines()
    assert lines[1] == (
        "CLM-1001: failed again (RuntimeError: The model provider is down),"
        " left for a handler"
    )
    assert lines[2] == (
        "Claim CLM-1001 is left for a handler, so there is nothing to do"
    )
    assert status(backend, "CLM-1001") == "left_for_handler"
    assert current_run(backend)["todos"][0]["status"] == "completed"


def test_the_todo_list_shows_progress_and_the_queue_shows_outcomes(backend, claims):
    claims.update({"CLM-1001": [("refer", 0)], "CLM-1003": [("approve", 3750)]})
    model = script(
        *work("CLM-1001", "CLM-1003"),
        todos(
            "t1", ("CLM-1001: flight", "completed"), ("CLM-1003: wrist", "completed")
        ),
        AIMessage(content="Done."),
    )
    queue_agent.run_queue(2, model)
    assert status(backend, "CLM-1001") == "decided"
    assert status(backend, "CLM-1003") == "awaiting_sign_off"
    shown = [todo["status"] for todo in current_run(backend)["todos"]]
    assert shown == ["completed", "completed"]


def test_the_check_for_missed_claims(backend, claims):
    claims.update({"CLM-1001": [("approve", 420)], "CLM-1002": [("approve", 420)]})
    model = script(
        *work("CLM-1001"),
        AIMessage(content="Done."),
        *work("CLM-1002"),
        AIMessage(content="All done."),
    )
    assert queue_agent.run_queue(2, model) == "All done."
    reminder = model.seen[2][-1]
    assert isinstance(reminder, HumanMessage)
    assert reminder.text.startswith("Before you finish: CLM-1002 still waiting")
    assert "cap of 2 claims" in reminder.text
    assert status(backend, "CLM-1002") == "decided"
    assert current_run(backend)["summary"] == "All done."


def test_the_check_gives_up_after_three_reminders(backend, claims):
    claims["CLM-1001"] = [("approve", 420)]
    model = script(*work("CLM-1001"), *[AIMessage(content="Done.") for _ in range(4)])
    assert queue_agent.run_queue(2, model) == "Done."
    reminders = [m for m in model.seen[-1] if isinstance(m, HumanMessage)]
    assert len(reminders) == 1 + queue_agent.MAX_NUDGES
    assert status(backend, "CLM-1002") == "waiting"


def test_a_queue_agent_that_fails_stops_the_run(backend, claims):
    with pytest.raises(RuntimeError, match="The model provider is down"):
        queue_agent.run_queue(5, script(errors=[BOOM]))
    run = current_run(backend)
    assert run["status"] == "stopped"
    assert "The model provider is down" in run["summary"]


def test_list_waiting_claims(backend):
    backend.post("/api/claims/CLM-1001/start")
    tools = queue_agent.queue_tools(queue_agent.Run(1, 5))
    listed = json.loads(tools[0].invoke({}))
    assert len(listed) == 24
    assert listed[0] == {
        "claim_id": "CLM-1002",
        "claim_type": "baggage",
        "summary": "Suitcase lost on a connecting flight",
        "amount_claimed": 1150.0,
        "submitted_on": "2026-07-20",
        "failures": 0,
    }
