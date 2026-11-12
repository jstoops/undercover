"""The backend keeps to docs/CODE_STANDARDS.md: one way to do each thing."""

import re
from pathlib import Path

SOURCE = {
    path.name: path.read_text(encoding="utf-8")
    for path in Path(__file__).parent.parent.glob("*.py")
}


def test_a_claims_status_changes_in_one_place():
    found = [
        name for name, text in SOURCE.items() if "UPDATE claims SET status" in text
    ]
    assert found == ["claims.py"]
    assert SOURCE["claims.py"].count("UPDATE claims SET status") == 1


def test_every_insert_names_its_columns():
    for name, text in SOURCE.items():
        assert not re.search(r"INSERT INTO \w+ VALUES", text), name
