"""Gemini client tests: key handling, model validation, planning and the tool loop."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from gemini import (
    DEFAULT_LIVE_MODEL,
    DEFAULT_MODEL,
    DEPRECATED_MODELS,
    GeminiAuthError,
    GeminiClient,
    GeminiConfigError,
    GeminiModelError,
    GeminiRateLimitError,
    SUPPORTED_MODELS,
    TOOL_SCHEMAS,
    extract_api_key,
    looks_like_placeholder,
)

FAKE_KEY = "AIzaSyTestKeyForFake0123456789"


class _Response:
    def __init__(self, text: str = "", calls: List[Any] | None = None) -> None:
        self.text = text
        self.function_calls = calls or []


class _Call:
    def __init__(self, name: str, args: Dict[str, Any]) -> None:
        self.name = name
        self.args = args


class _FakeSDK:
    """Minimal stand-in for the google-genai client."""

    def __init__(self) -> None:
        self.models = self
        self.responses: List[_Response] = []
        self.requests: List[Dict[str, Any]] = []

    def set(self, responses: List[_Response]) -> None:
        self.responses = list(responses)

    def generate_content(self, **kwargs: Any) -> _Response:
        self.requests.append(kwargs)
        if not self.responses:
            raise AssertionError("no fake response queued")
        return self.responses.pop(0)


@pytest.fixture()
def client() -> GeminiClient:
    instance = GeminiClient(api_key=FAKE_KEY, model=DEFAULT_MODEL, max_retries=0)
    instance._client = _FakeSDK()
    return instance


# -- configuration ---------------------------------------------------------


def test_default_models_are_current() -> None:
    assert DEFAULT_MODEL in SUPPORTED_MODELS
    assert DEFAULT_LIVE_MODEL in SUPPORTED_MODELS
    assert "gemini-2.0-flash" in DEPRECATED_MODELS


def test_deprecated_model_is_rejected() -> None:
    with pytest.raises(GeminiModelError):
        GeminiClient(api_key=FAKE_KEY, model="gemini-2.0-flash")


def test_unknown_but_well_formed_model_is_allowed() -> None:
    # future model ids may appear before this list is updated
    client = GeminiClient(api_key=FAKE_KEY, model="gemini-9.9-imaginary")
    assert client.model == "gemini-9.9-imaginary"


def test_malformed_model_is_rejected() -> None:
    with pytest.raises(GeminiModelError):
        GeminiClient(api_key=FAKE_KEY, model="not-a-model")


def test_placeholder_key_detection() -> None:
    for value in ("", "your_api_key", "sk-test", "xxx", "replace_with_your_own_key"):
        assert looks_like_placeholder(value)
    assert not looks_like_placeholder(FAKE_KEY)


def test_api_key_from_environment(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)
    monkeypatch.delenv("JARVIS_CONFIG", raising=False)
    assert extract_api_key(tmp_path / "missing.env") == FAKE_KEY


def test_api_key_from_dotenv_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(f"GEMINI_API_KEY={FAKE_KEY}\n", encoding="utf-8")
    assert extract_api_key(env_file) == FAKE_KEY


def test_missing_key_is_reported_not_raised(client: GeminiClient, monkeypatch) -> None:
    # extract_api_key() may have loaded a .env file into the environment
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    empty = GeminiClient(api_key="", model=DEFAULT_MODEL)
    assert empty.configured is False
    client._client = None
    client._init_error = "no sdk"
    outcome = client.test_connection()
    assert outcome["ok"] is False


def test_mask_hides_the_key(client: GeminiClient) -> None:
    masked = client.mask_secret(FAKE_KEY)
    assert FAKE_KEY not in masked
    assert masked


def test_api_key_fingerprint_is_not_reversible(client: GeminiClient) -> None:
    fingerprint = client.api_key_fingerprint
    assert FAKE_KEY not in fingerprint
    assert len(fingerprint) < len(FAKE_KEY)


# -- planning and the tool loop --------------------------------------------


def test_plan_tasks_parses_json_response(client: GeminiClient) -> None:
    payload = {
        "steps": [
            {"tool": "search_web", "text": "Search", "arguments": {"query": "flights"},
             "requires_confirmation": False},
            {"tool": "browser_open_result", "text": "Open", "arguments": {"index": 3}},
        ]
    }
    client._client.set([_Response(json.dumps(payload))])
    steps = client.plan_tasks("find flights and open the third result",
                              allowed_tools=["search_web", "browser_open_result"])
    assert [step["tool"] for step in steps] == ["search_web", "browser_open_result"]
    assert steps[1]["arguments"]["index"] == 3


def test_plan_tasks_handles_fenced_json(client: GeminiClient) -> None:
    fenced = '```json\n{"steps": [{"tool": "take_screenshot", "text": "Shot"}]}\n```'
    client._client.set([_Response(fenced)])
    steps = client.plan_tasks("take a screenshot", allowed_tools=["take_screenshot"])
    assert steps[0]["tool"] == "take_screenshot"


def test_plan_tasks_rejects_unparseable_response(client: GeminiClient) -> None:
    client._client.set([_Response("I cannot help with that")])
    with pytest.raises(GeminiModelError):
        client.plan_tasks("do something")


def test_plan_tasks_enforces_max_steps(client: GeminiClient) -> None:
    payload = {"steps": [{"tool": "get_system_status", "text": f"step{i}"} for i in range(10)]}
    client._client.set([_Response(json.dumps(payload))])
    steps = client.plan_tasks("long task", allowed_tools=["get_system_status"], max_steps=4)
    assert len(steps) == 4


def test_run_agent_executes_tools(client: GeminiClient) -> None:
    calls = [_Call("search_web", {"query": "react jobs"})]
    client._client.set([_Response("", calls=calls), _Response("Found 3 results")])
    seen: List[Dict[str, Any]] = []

    def executor(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        seen.append({"name": name, "args": arguments})
        return {"ok": True, "result": "3 results"}

    outcome = client.run_agent("search the web for react jobs", executor=executor)
    assert outcome["reply"] == "Found 3 results"
    assert seen == [{"name": "search_web", "args": {"query": "react jobs"}}]


def test_run_agent_reports_failures_back_to_the_model(client: GeminiClient) -> None:
    calls = [_Call("nope_tool", {})]
    client._client.set([_Response("", calls=calls), _Response("Sorry, I could not do that")])
    outcome = client.run_agent("do the thing", executor=lambda n, a: {"ok": False, "result": "nope"})
    assert outcome["reply"] == "Sorry, I could not do that"
    assert outcome["tool_calls"][0]["name"] == "nope_tool"


def test_run_agent_survives_executor_crash(client: GeminiClient) -> None:
    calls = [_Call("search_web", {})]

    def boom(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        raise RuntimeError("kaboom")

    client._client.set([_Response("", calls=calls), _Response("Alright")])
    outcome = client.run_agent("go", executor=boom)
    assert outcome["reply"] == "Alright"


def test_run_agent_stops_after_tool_budget(client: GeminiClient) -> None:
    calls = [_Call("get_system_status", {})]
    client._client.set([_Response("", calls=calls)] * 6)
    outcome = client.run_agent("loop forever", executor=lambda n, a: {"ok": True, "result": "ok"})
    assert "tool budget" in outcome["reply"]


def test_history_is_bounded_and_persisted(tmp_path: Path) -> None:
    history_path = tmp_path / "conversation.json"
    client = GeminiClient(api_key=FAKE_KEY, model=DEFAULT_MODEL, history_path=history_path)
    client.history.add("user", "first")
    client.history.add("assistant", "answer")
    client.history.add("user", "second")
    assert history_path.exists()
    reloaded = GeminiClient(api_key=FAKE_KEY, model=DEFAULT_MODEL, history_path=history_path)
    assert len(reloaded.history) == len(client.history)


def test_history_is_trimmed(tmp_path: Path) -> None:
    client = GeminiClient(api_key=FAKE_KEY, model=DEFAULT_MODEL,
                          history_path=tmp_path / "c.json")
    client.history.max_messages = 10
    for index in range(30):
        client.history.add("user", f"message {index}")
    assert len(client.history) <= 10


# -- error taxonomy ---------------------------------------------------------


@pytest.mark.parametrize(
    "message,expected",
    [
        ("401 invalid API key", GeminiAuthError),
        ("403 permission denied", GeminiAuthError),
        ("429 rate limit exceeded", GeminiRateLimitError),
        ("503 service unavailable", Exception),
        ("something odd", Exception),
    ],
)
def test_error_classification(message: str, expected: type) -> None:
    from gemini import _classify

    error = _classify(Exception(message), message)
    assert isinstance(error, expected)


def test_no_sdk_raises_config_error() -> None:
    client = GeminiClient(api_key=FAKE_KEY, model=DEFAULT_MODEL, max_retries=0)
    client._client = None
    client._init_error = "google-genai is not installed"
    with pytest.raises(GeminiConfigError):
        client.chat("hello")


# -- tool schema / registry agreement --------------------------------------


def test_every_declared_tool_has_a_registry_handler() -> None:
    from actions import ToolRegistry
    from desktop import DesktopController

    registry = ToolRegistry(desktop=DesktopController())
    declared = set(TOOL_SCHEMAS)
    assert declared == set(registry.names())


def test_tool_schemas_are_well_formed() -> None:
    for name, spec in TOOL_SCHEMAS.items():
        assert spec["description"], f"{name} has no description"
        parameters = spec["parameters"]
        assert isinstance(parameters, dict)
        assert "type" in parameters
        assert "properties" in parameters
