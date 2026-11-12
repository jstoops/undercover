import pytest
from fastapi.testclient import TestClient

from agent import main
from backend.main import app


@pytest.fixture(autouse=True)
def no_retry_waits(monkeypatch):
    monkeypatch.setattr(main, "RETRY_DELAY", 0)


@pytest.fixture
def backend(client, monkeypatch):
    """The backend the agent reaches, on the test's own database."""
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    return client
