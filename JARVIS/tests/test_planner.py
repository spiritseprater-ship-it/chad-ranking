"""Task planning tests: chaining, validation, execution, cancellation, history."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest

from brain import Brain, Router
from planner import TOOL_PREFIX, TaskHistory, TaskPlan, TaskPlanner, TaskRunner


class FakeAI:
    """Stand-in Gemini client used by the planner."""

    def __init__(self, steps: List[Dict[str, Any]] | None = None, fail: bool = False) -> None:
        self.steps = steps or []
        self.fail = fail
        self.calls: List[str] = []

    def plan_tasks(self, goal: str, allowed_tools: List[str], max_steps: int) -> List[Dict[str, Any]]:
        self.calls.append(goal)
        if self.fail:
            raise RuntimeError("network down")
        return self.steps[:max_steps]


def make_planner(ai: Any = None, allowed: List[str] | None = None) -> TaskPlanner:
    router = Router(Brain(), ai_enabled=ai is not None, ai_available=ai is not None)
    return TaskPlanner(ai_client=ai, allowed_tools=allowed or [], brain=Brain(), router=router)


# -- local decomposition ---------------------------------------------------


def test_chained_commands_become_two_steps() -> None:
    planner = make_planner()
    plan = planner.plan("open chrome and then search the web")
    assert len(plan.steps) == 2
    assert plan.steps[0].tool == f"{TOOL_PREFIX}open_chrome"
    assert plan.steps[1].tool == f"{TOOL_PREFIX}google_search"


def test_single_command_is_one_step() -> None:
    planner = make_planner()
    plan = planner.plan("mute the system")
    assert len(plan.steps) == 1
    assert plan.steps[0].tool == f"{TOOL_PREFIX}mute"


def test_unplannable_request_becomes_a_chat_step() -> None:
    planner = make_planner()
    plan = planner.plan("tell me a joke about trains")
    assert plan.steps
    assert plan.steps[0].tool == "chat"


def test_steps_are_numbered_from_one() -> None:
    planner = make_planner()
    plan = planner.plan("open chrome and then mute and then scroll down")
    assert [step.index for step in plan.steps] == [1, 2, 3]


# -- validation ------------------------------------------------------------


def test_validation_rejects_unknown_tools() -> None:
    planner = make_planner(allowed=["search_web"])
    from planner import TaskStep

    plan = TaskPlan(
        goal="clean up",
        steps=[TaskStep(index=1, tool="delete_everything", text="delete")],
    )
    problems = planner.validate_plan(plan)
    assert any("not allowed" in problem for problem in problems)


def test_validation_rejects_unknown_local_commands() -> None:
    planner = make_planner()
    plan = TaskPlan(goal="x", steps=[])
    from planner import TaskStep

    plan.steps.append(TaskStep(index=1, tool=f"{TOOL_PREFIX}no_such_command", text="nope"))
    problems = planner.validate_plan(plan)
    assert any("Unknown local command" in problem for problem in problems)


def test_validation_caps_step_count() -> None:
    planner = make_planner(allowed=["search_web"])
    from planner import TaskStep

    plan = TaskPlan(
        goal="do many things",
        steps=[TaskStep(index=i + 1, tool="search_web", text=f"s{i}") for i in range(8)],
    )
    problems = planner.validate_plan(plan)
    assert any("Too many steps" in problem for problem in problems)


def test_planner_caps_steps_before_validation() -> None:
    ai = FakeAI([{"tool": "search_web", "text": f"s{i}"} for i in range(9)])
    planner = make_planner(ai=ai, allowed=["search_web"])
    plan = planner.plan("do many things")
    assert len(plan.steps) <= planner.max_steps


def test_empty_plan_is_invalid() -> None:
    planner = make_planner()
    assert planner.validate_plan(TaskPlan(goal="", steps=[]))


# -- AI planning -----------------------------------------------------------


def test_planner_uses_the_ai_when_available() -> None:
    ai = FakeAI([{"tool": "search_web", "text": "Search", "arguments": {"query": "x"}}])
    planner = make_planner(ai=ai, allowed=["search_web"])
    plan = planner.plan("research something")
    assert plan.source == "gemini"
    assert plan.steps[0].tool == "search_web"
    assert ai.calls == ["research something"]


def test_planner_falls_back_to_local_rules_when_ai_fails() -> None:
    ai = FakeAI(fail=True)
    planner = make_planner(ai=ai, allowed=[])
    plan = planner.plan("open chrome and then search the web")
    assert plan.source == "local"
    assert len(plan.steps) == 2
    assert any("local rules" in warning for warning in plan.warnings)


def test_planner_drops_unsupported_ai_steps() -> None:
    ai = FakeAI([{"tool": "search_web", "text": "ok"}, {"tool": "evil_tool", "text": "bad"}])
    planner = make_planner(ai=ai, allowed=["search_web"])
    plan = planner.plan("do two things")
    assert [step.tool for step in plan.steps] == ["search_web"]
    assert any("unsupported" in warning.lower() for warning in plan.warnings)


def test_planner_keeps_confirmation_flags() -> None:
    ai = FakeAI([{"tool": "take_screenshot", "text": "Shot", "requires_confirmation": True}])
    planner = make_planner(ai=ai, allowed=["take_screenshot"])
    plan = planner.plan("take a screenshot")
    assert plan.steps[0].requires_confirmation is True


# -- execution ------------------------------------------------------------


def test_runner_executes_every_step() -> None:
    planner = make_planner(ai=FakeAI([
        {"tool": "search_web", "text": "Search"},
        {"tool": "browser_extract_text", "text": "Read"},
    ]), allowed=["search_web", "browser_extract_text"])
    history = TaskHistory(Path("/tmp/jarvis-planner-test-history.json"))
    history.path = None
    calls: List[str] = []
    runner = TaskRunner(planner, executor=lambda tool, args: calls.append(tool) or {"ok": True, "result": "done"})
    record = runner.run("research it")
    assert record.status == "completed"
    assert calls == ["search_web", "browser_extract_text"]


def test_runner_stops_when_a_step_fails() -> None:
    planner = make_planner(ai=FakeAI([
        {"tool": "search_web", "text": "Search"},
        {"tool": "browser_extract_text", "text": "Read"},
    ]), allowed=["search_web", "browser_extract_text"])
    calls: List[str] = []
    runner = TaskRunner(planner, executor=lambda tool, args: (calls.append(tool), {"ok": tool == "search_web", "result": ""})[1])
    record = runner.run("research it")
    assert record.status == "cancelled"
    assert calls == ["search_web", "browser_extract_text"]


def test_runner_can_be_cancelled_between_steps() -> None:
    planner = make_planner(ai=FakeAI([
        {"tool": "search_web", "text": "Search", "requires_confirmation": True},
        {"tool": "browser_extract_text", "text": "Read", "requires_confirmation": True},
        {"tool": "browser_scroll", "text": "Scroll", "requires_confirmation": True},
    ]), allowed=["search_web", "browser_extract_text", "browser_scroll"])
    calls: List[str] = []
    runner = TaskRunner(
        planner,
        executor=lambda tool, args: calls.append(tool) or {"ok": True, "result": "ok"},
    )

    def confirm(step):
        calls.append("confirm")
        runner.cancel()
        return False

    record = runner.run("research it", confirm=confirm)
    assert record.status == "cancelled"
    assert calls.count("confirm") == 1
    assert calls.count("search_web") == 0


def test_cancel_when_idle_reports_nothing_to_do() -> None:
    planner = make_planner(ai=FakeAI([{"tool": "search_web", "text": "Search"}]), allowed=["search_web"])
    runner = TaskRunner(planner, executor=lambda tool, args: {"ok": True, "result": "ok"})
    assert runner.cancel() is False
    assert runner.is_running() is False


def test_runner_reports_invalid_plans_without_executing() -> None:
    planner = make_planner()
    calls: List[str] = []
    runner = TaskRunner(planner, executor=lambda tool, args: calls.append(tool) or {"ok": True, "result": "ok"})
    record = runner.run("")
    assert record.status == "failed"
    assert calls == []


def test_runner_survives_executor_exceptions() -> None:
    planner = make_planner(ai=FakeAI([{"tool": "search_web", "text": "Search"}]), allowed=["search_web"])

    def boom(tool, args):
        raise RuntimeError("kaboom")

    runner = TaskRunner(planner, executor=boom)
    record = runner.run("research it")
    assert record.status == "cancelled"


# -- history --------------------------------------------------------------


def test_history_persists_and_reloads(tmp_path: Path) -> None:
    path = tmp_path / "history.json"
    planner = make_planner(ai=FakeAI([{"tool": "search_web", "text": "Search"}]), allowed=["search_web"])
    TaskRunner(planner, executor=lambda t, a: {"ok": True, "result": "ok"},
               history=TaskHistory(path)).run("research it")
    reloaded = TaskHistory(path)
    assert len(reloaded.entries()) == 1
    assert "research it" in reloaded.format_summary()


def test_history_is_bounded(tmp_path: Path) -> None:
    path = tmp_path / "history.json"
    history = TaskHistory(path, max_entries=3)
    for index in range(6):
        planner = make_planner()
        plan = TaskPlan(goal=f"task {index}", steps=[])
        history.record(plan, "completed")
    assert len(history.entries()) == 3


def test_history_clear(tmp_path: Path) -> None:
    history = TaskHistory(tmp_path / "history.json")
    planner = make_planner()
    history.record(TaskPlan(goal="one", steps=[]), "completed")
    assert history.clear() == 1
    assert history.entries() == []


def test_history_loads_corrupt_file_without_crashing(tmp_path: Path) -> None:
    path = tmp_path / "history.json"
    path.write_text("{ not json", encoding="utf-8")
    history = TaskHistory(path)
    assert history.entries() == []
