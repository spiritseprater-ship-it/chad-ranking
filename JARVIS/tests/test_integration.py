"""End-to-end orchestration tests (no Qt, no Windows, no network).

These wire the real components together the way ``main.JarvisApp`` does:
Router -> planner/agent -> ToolRegistry -> desktop controller -> history.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest

from actions import ActionEngine, PermissionManager, ToolRegistry
from brain import Brain, ParsedCommand, Router
from desktop import DesktopController
from gemini import GeminiClient
from main import load_config
from planner import TaskHistory, TaskPlanner, TaskRunner

FAKE_KEY = "AIzaSyFakeKeyForTesting0123456789"

TOOL_LIST = [
    "search_files", "open_file", "read_document", "take_screenshot",
    "browser_search", "browser_open_result", "get_system_status",
]


class _Response:
    def __init__(self, text: str = "", calls: List[Any] | None = None) -> None:
        self.text = text
        self.function_calls = calls or []


class _Call:
    def __init__(self, name: str, args: Dict[str, Any]) -> None:
        self.name = name
        self.args = args


class _SDK:
    def __init__(self, responses: List[_Response]) -> None:
        self.models = self
        self._responses = list(responses)

    def generate_content(self, **kwargs: Any) -> _Response:
        return self._responses.pop(0)


class FakeGemini:
    """Stands in for gemini.GeminiClient (planning + agent loop)."""

    def __init__(
        self,
        plan: List[Dict[str, Any]] | None = None,
        reply: str = "Here is what I found.",
        tool_calls: List[tuple] | None = None,
        raises: bool = False,
    ) -> None:
        self.plan = plan or []
        self.reply = reply
        self.tool_calls = tool_calls or []
        self.raises = raises
        self.planned: List[str] = []
        self._client: Any = None

    @property
    def configured(self) -> bool:
        return True

    def run_agent(self, text: str, executor, max_tool_rounds: int = 4) -> Dict[str, Any]:
        responses: List[_Response] = []
        if self.tool_calls:
            responses.append(_Response("", [_Call(name, args) for name, args in self.tool_calls]))
        responses.append(_Response(self.reply))
        self._client = _SDK(responses)
        client = GeminiClient(api_key=FAKE_KEY, model="gemini-3.8-flash", max_retries=0)
        client._client = self._client
        return client.run_agent(text, executor, max_tool_rounds=max_tool_rounds)

    def plan_tasks(self, goal: str, allowed_tools: List[str], max_steps: int) -> List[Dict[str, Any]]:
        if self.raises:
            raise RuntimeError("planner offline")
        self.planned.append(goal)
        return self.plan[:max_steps]


@pytest.fixture()
def action_engine(tmp_path: Path) -> ActionEngine:
    """The real Phase 1 engine, driven by the real config.json."""
    docs = tmp_path / "Documents"
    docs.mkdir(parents=True, exist_ok=True)
    config = load_config()
    config["permissions"] = dict(config.get("permissions") or {})
    config["permissions"]["allowed_file_roots"] = [str(docs)]
    return ActionEngine(config, PermissionManager(
        rules=config["permissions"].get("require_confirmation") or {},
        allowed_roots=config["permissions"].get("allowed_file_roots") or [],
        sensitive_paths=config["permissions"].get("sensitive_paths") or [],
    ))


def make_local_executor(engine: ActionEngine):
    """Run ``local:<command>`` tools through the Phase 1 action engine."""

    def _execute(name: str, arguments: Dict[str, object]) -> Dict[str, object]:
        command_id = name.split("local:", 1)[1] if name.startswith("local:") else name
        parsed = ParsedCommand(
            command=command_id,
            raw=str(arguments.get("text") or ""),
            normalized=str(arguments.get("text") or ""),
            confidence=1.0,
            slots=dict(arguments),
        )
        result = engine.execute(parsed)
        return {"ok": result.success, "result": result.message}

    return _execute


@pytest.fixture()
def workspace(tmp_path: Path, action_engine: ActionEngine) -> Dict[str, Any]:
    docs = tmp_path / "Documents"
    docs.mkdir(exist_ok=True)
    (docs / "flights to mumbai.pdf").write_text("x", encoding="utf-8")
    (docs / "flights hotels.pdf").write_text("x", encoding="utf-8")
    (docs / "trip notes.txt").write_text("boarding pass inside", encoding="utf-8")

    desktop = DesktopController(allowed_roots=[docs], screenshot_dir=docs)
    registry = ToolRegistry(
        desktop=desktop,
        browser=None,
        camera=None,
        allowed_tools=TOOL_LIST,
        local_executor=make_local_executor(action_engine),
        confirm=lambda name, args: True,
    )
    router = Router(Brain(), ai_enabled=True, ai_available=True)
    history = TaskHistory(tmp_path / "history.json")
    return {
        "docs": docs,
        "desktop": desktop,
        "registry": registry,
        "router": router,
        "history": history,
    }


def build_runner(workspace: Dict[str, Any], ai: FakeGemini) -> TaskRunner:
    planner = TaskPlanner(
        ai_client=ai,
        allowed_tools=TOOL_LIST,
        brain=Brain(),
        router=workspace["router"],
    )
    return TaskRunner(
        planner=planner,
        executor=workspace["registry"].execute,
        history=workspace["history"],
    )


# -- scenarios --------------------------------------------------------------


def test_local_command_is_routed_and_dispatched(workspace: Dict[str, Any]) -> None:
    decision = workspace["router"].route("find my flights files")
    assert decision.kind == "local"
    assert decision.command_id == "search_file"
    outcome = workspace["registry"].execute(f"local:{decision.command_id}", decision.command.slots)
    # the Phase 1 engine found several matches and asks which one to open
    assert "2 files" in outcome["result"]
    assert "Which one" in outcome["result"]


def test_ai_turn_calls_tools_and_replies(workspace: Dict[str, Any]) -> None:
    ai = FakeGemini(tool_calls=[("search_files", {"query": "flights"})],
                    reply="I found your flight document.")
    outcome = ai.run_agent("find my flight document", workspace["registry"].execute)
    assert outcome["reply"] == "I found your flight document."
    assert outcome["tool_calls"][0]["name"] == "search_files"


def test_multi_step_task_is_planned_executed_and_recorded(workspace: Dict[str, Any]) -> None:
    ai = FakeGemini(plan=[
        {"tool": "search_files", "text": "Find the file", "arguments": {"query": "trip"}},
        {"tool": "read_document", "text": "Read it", "arguments": {"path": "trip notes.txt"}},
    ])
    runner = build_runner(workspace, ai)
    record = runner.run("find my trip notes and read them")
    assert record.status == "completed"
    assert ai.planned == ["find my trip notes and read them"]
    assert len(workspace["history"].entries()) == 1
    assert "completed" in workspace["history"].format_summary()


def test_cancel_stops_the_task_and_records_it(workspace: Dict[str, Any]) -> None:
    ai = FakeGemini(plan=[
        {"tool": "search_files", "text": "Find", "arguments": {"query": "trip"}},
        {"tool": "get_system_status", "text": "Status", "requires_confirmation": True},
        {"tool": "read_document", "text": "Read", "arguments": {"path": "trip notes.txt"}},
    ])
    runner = build_runner(workspace, ai)
    confirmed: List[str] = []

    def confirm(step):
        confirmed.append(step.tool)
        return step.tool != "get_system_status"

    record = runner.run("do three things", confirm=confirm)
    assert record.status == "cancelled"
    assert confirmed == ["get_system_status"]
    assert len(workspace["history"].entries()) == 1


def test_unconfirmed_tool_cancels_the_step(workspace: Dict[str, Any]) -> None:
    registry = ToolRegistry(
        desktop=workspace["desktop"],
        browser=None,
        camera=None,
        allowed_tools=["take_screenshot"],
        confirm=lambda name, args: False,
    )
    outcome = registry.execute("take_screenshot", {})
    assert outcome["ok"] is False
    assert "cancelled" in outcome["result"]


def test_ai_planning_failure_falls_back_to_local_rules(workspace: Dict[str, Any]) -> None:
    ai = FakeGemini(raises=True)
    planner = TaskPlanner(
        ai_client=ai, allowed_tools=TOOL_LIST, brain=Brain(), router=workspace["router"]
    )
    plan = planner.plan("mute the system and then scroll down")
    assert plan.source == "local"
    assert [step.tool for step in plan.steps] == ["local:mute", "local:scroll_down"]
    assert any("local rules" in warning for warning in plan.warnings)


def test_missing_confirmation_callback_refuses_the_tool(workspace: Dict[str, Any]) -> None:
    registry = ToolRegistry(desktop=workspace["desktop"], browser=None, camera=None,
                            allowed_tools=["take_screenshot"])
    outcome = registry.execute("take_screenshot", {})
    assert outcome["ok"] is False
    assert "confirmation" in outcome["result"]


def test_local_only_planning_survives_without_gemini(workspace: Dict[str, Any]) -> None:
    runner = build_runner(workspace, FakeGemini(raises=True))
    record = runner.run("mute the system")
    assert record.status == "completed"
    assert record.steps[0]["tool"] == "local:mute"
