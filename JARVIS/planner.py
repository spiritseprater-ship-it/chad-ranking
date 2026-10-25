"""
planner.py - multi-step task planning, command chaining and history.

A request like "search the web for the best flights, then open the third result
and tell me the price" is decomposed into ordered, tool-backed steps.  Decomposition
uses Gemini when it is available and falls back to a local rule-based splitter, so
planning still works offline for the common "do X and then Y" phrasing.

Every step is validated against the allowed tool list before it runs, and the
runner can be cancelled from any point - cancellation never depends on the AI.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

log = logging.getLogger("jarvis.planner")

MAX_STEPS = 6

#: conjunctions that separate two commands inside one utterance
CHAIN_SEPARATORS = re.compile(
    r"\s*,\s*|\s+\b(?:and\s+then|then|after\s+that|next|after|also|aur|phir|baad\s+me|aage)\b\s*",
    re.IGNORECASE,
)

TOOL_PREFIX = "local:"


@dataclass
class TaskStep:
    index: int
    tool: str
    text: str
    arguments: Dict[str, object] = field(default_factory=dict)
    requires_confirmation: bool = False
    status: str = "pending"  # pending | running | done | failed | cancelled
    result: str = ""

    @property
    def description(self) -> str:
        if self.arguments:
            args = ", ".join(f"{key}={value}" for key, value in sorted(self.arguments.items()))
            return f"{self.text} ({args})"
        return self.text

    @property
    def is_local(self) -> bool:
        return self.tool.startswith(TOOL_PREFIX)


@dataclass
class TaskPlan:
    goal: str
    steps: List[TaskStep]
    source: str = "local"
    warnings: List[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.steps

    def first_pending(self) -> Optional[TaskStep]:
        for step in self.steps:
            if step.status == "pending":
                return step
        return None


@dataclass
class TaskRecord:
    id: str
    goal: str
    steps: List[Dict[str, object]]
    status: str  # completed | cancelled | failed | failed_after_confirmation
    created: str
    source: str
    summary: str = ""


class TaskHistory:
    """Bounded, persisted history of completed and cancelled tasks."""

    def __init__(self, path: Optional[Path] = None, max_entries: int = 50) -> None:
        self.path = Path(path) if path else None
        self.max_entries = int(max_entries)
        self._entries: List[TaskRecord] = []
        self._lock = threading.Lock()
        if self.path and self.path.exists():
            self.load()

    def record(self, plan: TaskPlan, status: str, summary: str = "") -> TaskRecord:
        with self._lock:
            record = TaskRecord(
                id=uuid.uuid4().hex[:8],
                goal=plan.goal,
                steps=[asdict(step) for step in plan.steps],
                status=status,
                created=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                source=plan.source,
                summary=summary,
            )
            self._entries.insert(0, record)
            del self._entries[self.max_entries:]
            self.save()
            return record

    def entries(self) -> List[TaskRecord]:
        with self._lock:
            return list(self._entries)

    def recent(self, limit: int = 10) -> List[TaskRecord]:
        with self._lock:
            return list(self._entries[:max(1, int(limit))])

    def clear(self) -> int:
        with self._lock:
            removed = len(self._entries)
            self._entries = []
            self.save()
            return removed

    def save(self) -> None:
        if not self.path:
            return
        try:
            payload = [asdict(entry) for entry in self._entries]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            log.warning("could not save task history: %s", exc)

    def load(self) -> None:
        if not self.path or not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self._entries = [TaskRecord(**entry) for entry in payload]
        except (OSError, ValueError, TypeError) as exc:
            log.warning("could not load task history: %s", exc)

    def format_summary(self, limit: int = 10) -> str:
        entries = self.recent(limit)
        if not entries:
            return "No tasks yet."
        lines = []
        for entry in entries:
            summary = entry.summary or ", ".join(
                str(step.get("text", "")) for step in entry.steps if step.get("text")
            )
            lines.append(f"{entry.created}  [{entry.status}] {entry.goal}")
            if summary:
                lines.append(f"    -> {summary[:140]}")
        return "\n".join(lines)


class TaskPlanner:
    """Decompose a goal into validated, ordered steps."""

    def __init__(
        self,
        ai_client=None,
        allowed_tools: Sequence[str] = (),
        brain=None,
        router=None,
        max_steps: int = MAX_STEPS,
    ) -> None:
        self.ai_client = ai_client
        self.allowed_tools = set(allowed_tools)
        self.brain = brain
        self.router = router
        self.max_steps = int(max_steps)

    # -- public API ---------------------------------------------------------

    def plan(self, goal: str) -> TaskPlan:
        """Produce a plan for ``goal``, preferring the AI when available."""
        goal = (goal or "").strip()
        if not goal:
            return TaskPlan(goal="", steps=[], source="local", warnings=["Empty goal."])

        if self.ai_client is not None:
            try:
                plan = self._plan_with_ai(goal)
                if plan is not None and not plan.is_empty():
                    return plan
            except Exception as exc:  # noqa: BLE001 - planning must never crash the app
                log.warning("AI planning failed, falling back to local rules: %s", exc)
            plan = self._plan_locally(goal)
            plan.warnings.append("Planned with local rules (AI unavailable).")
            return plan

        plan = self._plan_locally(goal)
        if plan.is_empty():
            plan.warnings.append("No tool could plan this - I will answer as a conversation.")
        return plan

    def validate_plan(self, plan: TaskPlan) -> List[str]:
        """Return a list of human-readable problems with a plan."""
        problems: List[str] = []
        if not plan.steps:
            problems.append("The plan is empty.")
            return problems
        if len(plan.steps) > self.max_steps:
            problems.append(f"Too many steps ({len(plan.steps)} > {self.max_steps}).")
        for step in plan.steps:
            if step.is_local:
                command_id = step.tool[len(TOOL_PREFIX):]
                if self.brain is not None and command_id not in self._local_ids():
                    problems.append(f"Unknown local command: {command_id}.")
            elif step.tool not in self.allowed_tools:
                problems.append(f"Tool not allowed: {step.tool}.")
        return problems

    def _local_ids(self) -> set:
        return {spec.id for spec in getattr(self.brain, "commands", [])}

    # -- AI planning --------------------------------------------------------

    def _plan_with_ai(self, goal: str) -> Optional[TaskPlan]:
        steps = self.ai_client.plan_tasks(goal, allowed_tools=sorted(self.allowed_tools),
                                         max_steps=self.max_steps)
        plan = TaskPlan(goal=goal, steps=[], source="gemini")
        for raw in steps:
            if not isinstance(raw, dict):
                continue
            tool = str(raw.get("tool", "")).strip()
            text = str(raw.get("text") or raw.get("description") or "").strip()
            if not tool:
                continue
            if tool.startswith(TOOL_PREFIX):
                pass
            elif tool not in self.allowed_tools:
                plan.warnings.append(f"Dropped unsupported step '{text or tool}'.")
                continue
            step = TaskStep(
                index=len(plan.steps) + 1,
                tool=tool,
                text=text or tool,
                arguments=raw.get("arguments") or {},
                requires_confirmation=bool(raw.get("requires_confirmation", False)),
            )
            plan.steps.append(step)
            if len(plan.steps) >= self.max_steps:
                break
        return plan

    # -- local planning (offline fallback) ----------------------------------

    def _plan_locally(self, goal: str) -> TaskPlan:
        parts = [part.strip() for part in CHAIN_SEPARATORS.split(goal) if part.strip()]
        steps: List[TaskStep] = []
        warnings: List[str] = []

        for part in parts[: self.max_steps]:
            parsed = None
            if self.router is not None:
                parsed = self.router.route(part).command
            elif self.brain is not None:
                parsed = self.brain.parse(part)

            if parsed is not None:
                steps.append(
                    TaskStep(
                        index=len(steps) + 1,
                        tool=f"{TOOL_PREFIX}{parsed.command}",
                        text=parsed.label,
                        arguments=dict(parsed.slots),
                    )
                )
                continue

            if self.ai_client is None:
                # Nothing local can do this: keep it as one conversational step so
                # the caller can still answer with a normal chat reply.
                steps.append(
                    TaskStep(
                        index=len(steps) + 1,
                        tool="chat",
                        text=part[:120],
                        arguments={"text": part},
                    )
                )
                continue
            warnings.append(f"Could not plan locally: '{part[:40]}'.")

        plan = TaskPlan(goal=goal, steps=steps, source="local", warnings=warnings)
        return plan


class TaskRunner:
    """Executes a plan step by step with cancellation support."""

    def __init__(
        self,
        planner: TaskPlanner,
        executor: Callable[[str, Dict[str, object]], Dict[str, object]],
        history: Optional[TaskHistory] = None,
        on_step: Optional[Callable[[TaskStep], None]] = None,
        on_done: Optional[Callable[[TaskRecord], None]] = None,
    ) -> None:
        self.planner = planner
        self.executor = executor
        self.history = history
        self.on_step = on_step
        self.on_done = on_done
        self._cancel = threading.Event()
        self._current: Optional[TaskPlan] = None
        self._lock = threading.Lock()

    def cancel(self) -> bool:
        """Cancel the running task.  Returns True when something was cancelled."""
        with self._lock:
            if self._current is None:
                return False
            self._cancel.set()
            return True

    def is_running(self) -> bool:
        return self._current is not None

    def current_plan(self) -> Optional[TaskPlan]:
        return self._current

    def run(self, goal: str, confirm: Optional[Callable[[TaskStep], bool]] = None) -> TaskRecord:
        """Plan and execute ``goal``, returning the recorded result."""
        with self._lock:
            self._cancel.clear()
        plan = self.planner.plan(goal)
        self._current = plan

        if self.planner.validate_plan(plan):
            problems = "; ".join(self.planner.validate_plan(plan))
            record = self._finish(plan, "failed", summary=f"Rejected: {problems}")
            return record

        cancelled = False
        for step in plan.steps:
            if self._cancel.is_set():
                cancelled = True
                break
            if step.requires_confirmation and confirm is not None:
                if not confirm(step):
                    step.status = "cancelled"
                    cancelled = True
                    break
            step.status = "running"
            self._notify(step)
            try:
                outcome = self.executor(step.tool, dict(step.arguments))
            except Exception as exc:  # noqa: BLE001 - a failed step must not kill the app
                step.status = "failed"
                step.result = str(exc)
                log.warning("step %s failed: %s", step.tool, exc)
                self._notify(step)
                cancelled = True
                break
            ok = bool(outcome.get("ok", False))
            step.status = "done" if ok else "failed"
            step.result = str(outcome.get("result", ""))
            if not ok:
                cancelled = True
                break
            self._notify(step)

        status = "cancelled" if cancelled else "completed"
        summary = ", ".join(
            f"{step.description} -> {step.status}" for step in plan.steps
        )[:300]
        return self._finish(plan, status, summary)

    # -- internals ----------------------------------------------------------

    def _notify(self, step: TaskStep) -> None:
        if self.on_step is not None:
            try:
                self.on_step(step)
            except Exception:  # pragma: no cover - UI callbacks must not break execution
                log.debug("on_step callback failed", exc_info=True)

    def _finish(self, plan: TaskPlan, status: str, summary: str = "") -> TaskRecord:
        with self._lock:
            self._current = None
            self._cancel.clear()
        if self.history is not None:
            record = self.history.record(plan, status, summary)
        else:
            record = TaskRecord(
                id=uuid.uuid4().hex[:8], goal=plan.goal,
                steps=[asdict(s) for s in plan.steps], status=status,
                created=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                source=plan.source, summary=summary,
            )
        if self.on_done is not None:
            try:
                self.on_done(record)
            except Exception:  # pragma: no cover
                log.debug("on_done callback failed", exc_info=True)
        return record


__all__ = [
    "TaskStep",
    "TaskPlan",
    "TaskRecord",
    "TaskHistory",
    "TaskPlanner",
    "TaskRunner",
    "TOOL_PREFIX",
    "MAX_STEPS",
    "CHAIN_SEPARATORS",
]
