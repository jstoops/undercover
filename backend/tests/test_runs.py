import pytest


def start_run(client, cap=5):
    return client.post("/api/runs", json={"cap": cap})


def save(client, run_id, *todos):
    return client.put(
        f"/api/runs/{run_id}/todos",
        json={"todos": [{"content": c, "status": s} for c, s in todos]},
    )


def finish(client, run_id, outcome="finished", summary="Worked 5 claims."):
    return client.post(
        f"/api/runs/{run_id}/finish", json={"outcome": outcome, "summary": summary}
    )


def decide(client, claim_id, decision, payout):
    client.post(f"/api/claims/{claim_id}/start")
    client.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "decision": decision,
            "payout": payout,
            "reason": "The wording covers it.",
            "policy_section": "Section 3, Trip Delay",
        },
    )


def shown(run):
    return [
        (todo["position"], todo["content"], todo["status"]) for todo in run["todos"]
    ]


def test_start_a_run(client):
    assert client.get("/api/runs/current").json() is None
    run = start_run(client).json()
    assert run["run_id"] == 1
    assert run["cap"] == 5
    assert run["status"] == "running"
    assert run["started_at"]
    assert run["finished_at"] is None
    assert run["summary"] is None
    assert run["todos"] == []
    assert client.get("/api/runs/current").json() == run


def test_save_the_todo_list(client):
    run_id = start_run(client).json()["run_id"]
    items = ["CLM-1001: flight canceled", "CLM-1002: bag lost", "Write the summary"]
    saved = save(client, run_id, *[(item, "pending") for item in items])
    assert [todo["status"] for todo in saved.json()["todos"]] == ["pending"] * 3
    ticked = save(
        client,
        run_id,
        (items[0], "in_progress"),
        (items[1], "completed"),
        (items[2], "pending"),
    ).json()
    assert shown(ticked) == [
        (1, items[0], "in_progress"),
        (2, items[1], "completed"),
        (3, items[2], "pending"),
    ]
    assert client.get("/api/runs/current").json() == ticked


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/runs", {"cap": 0}),
        ("/api/runs/1/todos", {"todos": [{"content": "x", "status": "maybe"}]}),
    ],
)
def test_input_checks(client, path, body):
    start_run(client)
    method = client.put if path.endswith("todos") else client.post
    assert method(path, json=body).status_code == 422


def test_a_completed_item_stays_completed_however_its_claim_ended(client):
    run_id = start_run(client).json()["run_id"]
    decide(client, "CLM-1003", "approve", 3750)
    decide(client, "CLM-1004", "refer", 0)
    for _ in range(2):
        client.post("/api/claims/CLM-1005/start")
        client.post(
            "/api/claims/CLM-1005/failure", json={"thread_id": "t", "reason": "Boom"}
        )
    items = ["CLM-1003: wrist", "CLM-1004: bag late", "CLM-1005: passport"]
    run = save(client, run_id, *[(item, "completed") for item in items]).json()
    assert [todo["status"] for todo in run["todos"]] == ["completed"] * 3


def test_finish_a_run(client):
    run_id = start_run(client).json()["run_id"]
    run = finish(client, run_id).json()
    assert run["status"] == "finished"
    assert run["summary"] == "Worked 5 claims."
    assert run["finished_at"]
    assert save(client, run_id, ("CLM-1001", "pending")).status_code == 409
    again = finish(client, run_id)
    assert again.status_code == 409
    assert again.json()["detail"] == "Run 1 is finished"
    assert finish(client, 99).status_code == 404
    assert save(client, 99).status_code == 404


def test_a_new_run_stops_one_that_never_finished(client):
    first = start_run(client).json()["run_id"]
    client.post("/api/claims/CLM-1002/start")
    second = start_run(client).json()
    assert second["run_id"] == first + 1
    current = client.get("/api/runs/current").json()
    assert current["run_id"] == second["run_id"]
    assert current["status"] == "running"
    claim = client.get("/api/claims/CLM-1002").json()
    assert claim["status"] == "waiting"
    assert claim["failures"] == 1
    steps = client.get("/api/claims/CLM-1002/steps").json()
    assert [(s["kind"], s["content"]) for s in steps] == [
        ("error", "The run stopped before this claim was decided")
    ]
    assert finish(client, first).json()["detail"] == "Run 1 is stopped"


def test_a_claim_in_progress_outside_a_run_is_left_alone(client):
    client.post("/api/claims/CLM-1002/start")
    start_run(client)
    assert client.get("/api/claims/CLM-1002").json()["status"] == "in_progress"
