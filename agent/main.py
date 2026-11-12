"""What the UnderCover Agent's queue agent and claim agent share."""

import os
from typing import Any

import httpx
from dotenv import load_dotenv
from langchain.agents.middleware import ModelRetryMiddleware
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

BACKEND_URL = "http://127.0.0.1:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "z-ai/glm-5.3-flash"
DEFAULT_IGNORED_PROVIDERS = "wafer"
MODEL_TIMEOUT = 120
MODEL_RETRIES = 3
RETRY_DELAY = 1.0


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


def call(method: str, path: str, body: dict[str, Any] | None = None) -> str:
    """Call the backend and return its reply as text, refusals included."""
    with backend() as client:
        return client.request(method, path, json=body).text


def ignored_providers() -> list[str]:
    """Return the OpenRouter providers to skip: OPENROUTER_IGNORE, or Wafer."""
    names = os.getenv("OPENROUTER_IGNORE", DEFAULT_IGNORED_PROVIDERS).split(",")
    return [name.strip() for name in names if name.strip()]


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GLM 5.3 Flash by default."""
    name = os.getenv("MODEL_NAME")
    ignore = ignored_providers()
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
        timeout=MODEL_TIMEOUT,
        extra_body={"provider": {"ignore": ignore}} if ignore else None,
    )


def model_retries() -> ModelRetryMiddleware:
    """Try a failed model call again, such as a provider error or a timeout."""
    return ModelRetryMiddleware(
        max_retries=MODEL_RETRIES, initial_delay=RETRY_DELAY, on_failure="error"
    )


def updates_in(update: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the state updates in one streamed update from an agent."""
    updates: list[dict[str, Any]] = []
    for node in update.values():
        updates.extend(node if isinstance(node, list) else [node or {}])
    return updates


def messages_in(update: dict[str, Any]) -> list[BaseMessage]:
    """Return the new messages in one streamed update from an agent."""
    return [m for node in updates_in(update) for m in node.get("messages", [])]
