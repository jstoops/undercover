def test_the_policy_wording_contents(client):
    sections = client.get("/api/documents/policy-wording/sections").json()
    assert [s["number"] for s in sections] == list(range(1, 13))
    assert sections[0]["title"] == "Your plan"
    assert sections[-1]["title"] == "Definitions"
    assert sections[7]["topics"] == [
        "Adventure Sports",
        "Pre-Existing Condition Waiver",
        "Electronics Plus",
    ]


def test_the_claims_manual_contents(client):
    sections = client.get("/api/documents/claims-manual/sections").json()
    assert [s["number"] for s in sections] == list(range(1, 15))
    notes = sections[6]
    assert notes["title"] == "Interpretation notes"
    assert {"Unattended belongings", "Wild animals", "Pre-existing conditions"} <= set(
        notes["topics"]
    )


def test_read_a_section(client):
    section = client.get("/api/documents/claims-manual/sections/10").json()
    assert section["document"] == "claims-manual"
    assert section["title"] == "Meals without receipts"
    assert "$35 per traveler" in section["text"]
    assert "Customer data" not in section["text"]
    assert not section["text"].startswith("##")


def test_unknown_sections_and_documents(client):
    missing = client.get("/api/documents/claims-manual/sections/15")
    assert missing.status_code == 404
    assert client.get("/api/documents/evals/sections").status_code == 422
    assert client.get("/api/documents/evals/sections/1").status_code == 422


def test_the_whole_wording_is_no_longer_served(client):
    assert client.get("/api/policy-wording").status_code == 404
