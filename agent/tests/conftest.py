import pytest
from fastapi.testclient import TestClient

from agent import api, harness
from backend.main import app


@pytest.fixture(autouse=True)
def no_retry_waits(monkeypatch):
    monkeypatch.setattr(harness, "RETRY_DELAY", 0)


@pytest.fixture
def backend(client, monkeypatch):
    """The backend the agent reaches, on the test's own database."""
    monkeypatch.setattr(api, "client", TestClient(app, base_url=api.BASE_URL))
    return client
