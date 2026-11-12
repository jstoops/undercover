import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agent import main


def payload(monkeypatch, **env):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    for name in ("MODEL_NAME", "OPENROUTER_IGNORE"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return main.model()._get_request_payload([HumanMessage(content="Hi")])


def test_the_default_model(monkeypatch):
    request = payload(monkeypatch)
    assert request["model"] == "z-ai/glm-5.3-flash"
    assert request["reasoning_effort"] == "low"
    assert request["extra_body"] == {"provider": {"ignore": ["wafer"]}}


def test_model_name(monkeypatch):
    request = payload(monkeypatch, MODEL_NAME="openrouter/free")
    assert request["model"] == "openrouter/free"
    assert "reasoning_effort" not in request
    assert request["extra_body"] == {"provider": {"ignore": ["wafer"]}}


@pytest.mark.parametrize("model_name", ["", "openrouter/free"])
def test_providers_to_skip(monkeypatch, model_name):
    env = {"MODEL_NAME": model_name} if model_name else {}
    request = payload(monkeypatch, OPENROUTER_IGNORE="wafer, deepinfra", **env)
    assert request["extra_body"] == {"provider": {"ignore": ["wafer", "deepinfra"]}}
    request = payload(monkeypatch, OPENROUTER_IGNORE="", **env)
    assert "extra_body" not in request


def test_messages_in_an_update():
    first, second = AIMessage(content="One"), AIMessage(content="Two")
    update = {
        "model": {"messages": [first]},
        "tools": [{"messages": [second]}, {"todos": []}],
        "Check.after_model": None,
    }
    assert main.messages_in(update) == [first, second]
