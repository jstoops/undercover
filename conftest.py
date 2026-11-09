import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.seed import seed


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    """A client for the backend on a freshly seeded database of its own."""
    path = tmp_path / "undercover.db"
    monkeypatch.setenv("UNDERCOVER_DB", str(path))
    seed(path)
    return TestClient(app)
