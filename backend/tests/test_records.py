import pytest

from backend.db import DATA


def test_list_claims(client):
    claims = client.get("/api/claims").json()
    assert [claim["claim_id"] for claim in claims] == [
        f"CLM-{n}" for n in range(1001, 1026)
    ]
    assert {claim["status"] for claim in claims} == {"waiting"}
    assert {claim["decision"] for claim in claims} == {None}
    assert claims[0]["customer_name"] == "Maya Patel"


def test_get_claim(client):
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["story"].startswith("My flight home from Rome")
    assert len(claim["items"]) == 3
    assert len(claim["documents"]) == 4
    assert claim["amount_claimed"] == 420.0
    assert claim["status"] == "waiting"
    assert claim["customer_name"] == "Maya Patel"
    assert claim["decision"] is None
    assert claim["sign_off"] is None
    assert claim["payment"] is None


def test_get_policy(client):
    policy = client.get("/api/policies/POL-2001").json()
    assert policy["plan"] == "premium"
    assert policy["add_ons"] == []
    assert policy["trip"] == {
        "destination": "Rome, Italy",
        "departs_on": "2026-06-10",
        "returns_on": "2026-06-18",
        "trip_cost": 3100.0,
    }
    assert policy["travelers"] == ["Maya Patel"]


def test_get_customer_leaves_out_contact_details(client):
    customer = client.get("/api/customers/CUS-3001").json()
    assert customer["name"] == "Maya Patel"
    assert customer["customer_since"] == "2023-04-11"
    assert [c["claim_id"] for c in customer["previous_claims"]] == ["CLM-0412"]
    assert set(customer) == {
        "customer_id",
        "name",
        "customer_since",
        "previous_claims",
    }


def test_get_policy_wording(client):
    wording = client.get("/api/policy-wording").json()["policy_wording"]
    assert wording == (DATA / "policy_wording.md").read_text(encoding="utf-8")


def test_list_handlers(client):
    handlers = client.get("/api/handlers").json()
    assert [h["name"] for h in handlers] == [
        "Dana Whitfield",
        "Marcus Oyelaran",
        "Priya Raman",
    ]


@pytest.mark.parametrize(
    "path",
    ["/api/claims/CLM-9999", "/api/policies/POL-9999", "/api/customers/CUS-9999"],
)
def test_unknown_records(client, path):
    response = client.get(path)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]
