"""
diagnostics.py - "Check my JARVIS" self-diagnostics.

Every check is defensive: a missing optional capability is reported as a
warning, never as a crash.  The report is plain data so it can be spoken, shown
in the UI or written to the log file.
"""

from __future__ import annotations

import logging
import platform
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

log = logging.getLogger("jarvis.diagnostics")


@dataclass
class CheckResult:
    name: str
    status: str  # "ok" | "warning" | "error" | "skipped"
    detail: str
    hint: str = ""

    @property
    def is_problem(self) -> bool:
        return self.status in ("warning", "error")


@dataclass
class DiagnosticReport:
    results: List[CheckResult] = field(default_factory=list)
    duration_ms: float = 0.0

    def add(self, result: CheckResult) -> CheckResult:
        self.results.append(result)
        return result

    @property
    def ok(self) -> bool:
        return not any(result.is_problem for result in self.results)

    @property
    def problems(self) -> List[CheckResult]:
        return [result for result in self.results if result.is_problem]

    def lines(self) -> List[str]:
        mark = {"ok": "[ ok ]", "warning": "[warn]", "error": "[FAIL]", "skipped": "[skip]"}
        return [
            f"{mark.get(result.status, result.status)} {result.name}: {result.detail}"
            + (f"  ({result.hint})" if result.hint else "")
            for result in self.results
        ]

    def summary(self) -> str:
        counts = {status: 0 for status in ("ok", "warning", "error", "skipped")}
        for result in self.results:
            counts[result.status] = counts.get(result.status, 0) + 1
        if self.ok:
            verdict = "All systems healthy."
        else:
            verdict = f"{len(self.problems)} issue(s) need attention."
        return (
            f"{verdict} {counts['ok']} ok, {counts['warning']} warning(s), "
            f"{counts['error']} error(s), {counts['skipped']} skipped."
        )

    def speakable(self) -> str:
        """A short spoken summary for the user."""
        if self.ok:
            return "JARVIS self-check passed. Everything is healthy."
        lines = ["JARVIS self-check found these issues:"]
        for result in self.problems[:4]:
            lines.append(f"{result.name}: {result.detail}")
        return " ".join(lines)


def _check_runtime(report: DiagnosticReport, executable: bool) -> None:
    version = ".".join(str(part) for part in sys.version_info[:3])
    if executable:
        detail = f"Python {version} running as a packaged application on {platform.system()}"
    else:
        detail = f"Python {version} running from source on {platform.system()} {platform.release()}"
    report.add(CheckResult("Runtime", "ok", detail))


def _check_config(report: DiagnosticReport, config: Dict[str, object]) -> None:
    problems = config.get("problems") or []
    if problems:
        report.add(CheckResult("Configuration", "error", "; ".join(str(p) for p in problems)))
        return
    report.add(CheckResult("Configuration", "ok", "loaded and valid"))


def _check_wake_word(report: DiagnosticReport, config: Dict[str, object]) -> None:
    wake = config.get("wake_word") or {}
    enabled = bool(wake.get("enabled", True))
    words = (wake.get("words") or ["jarvis"]) if enabled else []
    if enabled and words:
        report.add(CheckResult("Wake word", "ok", ", ".join(str(w) for w in words)))
    elif enabled:
        report.add(
            CheckResult("Wake word", "warning", "enabled but no wake word configured",
                        "Add a wake word in Settings.")
        )
    else:
        report.add(CheckResult("Wake word", "skipped", "disabled (manual activation only)"))


def _check_microphone(report: DiagnosticReport, voice) -> None:
    mic = getattr(voice, "mic", None)
    if mic is None:
        report.add(CheckResult("Microphone", "skipped", "not built"))
        return
    try:
        devices = mic.list_devices()
    except Exception as exc:
        report.add(CheckResult("Microphone", "warning", f"could not list devices: {exc}"))
        return
    if not devices:
        report.add(
            CheckResult("Microphone", "error", "no microphone was found",
                        "Plug in a microphone or check Windows Sound settings.")
        )
        return
    report.add(CheckResult("Microphone", "ok", f"{len(devices)} device(s) available"))


def _check_speech_backends(report: DiagnosticReport, voice) -> None:
    recognizer = getattr(voice, "recognizer", None)
    if recognizer is None:
        report.add(CheckResult("Speech recognition", "skipped", "not built"))
        return
    try:
        backend = recognizer.active_backend()
        if backend == "none":
            report.add(
                CheckResult("Speech recognition", "error", "no backend available",
                            "Install speech-to-text, or use a faster/API backend.")
            )
        else:
            report.add(CheckResult("Speech recognition", "ok", backend))
    except Exception as exc:  # pragma: no cover - defensive
        report.add(CheckResult("Speech recognition", "warning", str(exc)))

    wake_engine = getattr(voice, "wake", None)
    if wake_engine is None:
        return
    if not getattr(wake_engine, "ready", False):
        report.add(
            CheckResult("Wake-word engine", "warning", getattr(wake_engine, "mode", "unavailable"),
                        "Install the wake-word dependencies for always-on detection.")
        )
    else:
        report.add(CheckResult("Wake-word engine", "ok", getattr(wake_engine, "mode", "ready")))


def _check_gemini(report: DiagnosticReport, gemini, test_connection: bool) -> None:
    if gemini is None:
        report.add(CheckResult("Gemini AI", "skipped", "not enabled"))
        return
    if not getattr(gemini, "configured", False):
        report.add(
            CheckResult("Gemini AI", "error", "no API key found",
                        "Open Settings and paste a Google AI Studio API key.")
        )
        return
    report.add(CheckResult("Gemini AI", "ok", f"configured with model {getattr(gemini, 'model', '?')}"))
    if test_connection:
        try:
            outcome = gemini.test_connection()
            if outcome.get("ok"):
                report.add(CheckResult("Gemini connection", "ok", str(outcome.get("reply", "reachable"))))
            else:
                report.add(
                    CheckResult("Gemini connection", "error", str(outcome.get("error", "failed")))
                )
        except Exception as exc:  # pragma: no cover - defensive
            report.add(CheckResult("Gemini connection", "warning", f"test failed: {exc}"))
    else:
        report.add(CheckResult("Gemini connection", "skipped", "network check not requested"))


def _check_browser(report: DiagnosticReport, browser) -> None:
    if browser is None:
        report.add(CheckResult("Browser automation", "skipped", "not enabled in settings"))
        return
    if not getattr(browser, "available", False):
        report.add(
            CheckResult("Browser automation", "warning", "Playwright is not installed",
                        "Run: pip install playwright && playwright install chromium")
        )
        return
    report.add(CheckResult("Browser automation", "ok", "Playwright is available"))


def _check_camera(report: DiagnosticReport, camera) -> None:
    if camera is None:
        report.add(CheckResult("Camera", "skipped", "not enabled in settings"))
        return
    status = camera.status_text()
    if camera.enabled and camera.permission_granted:
        report.add(CheckResult("Camera", "ok" if camera.is_available() else "warning", status))
    else:
        report.add(CheckResult("Camera", "skipped", status))


def _check_tools(report: DiagnosticReport, registry, planner) -> None:
    if registry is None:
        report.add(CheckResult("Automation tools", "skipped", "not built"))
        return
    enabled = getattr(registry, "allowed_tools", None)
    total = len(getattr(registry, "names", lambda: [])())
    if enabled:
        report.add(CheckResult("Automation tools", "ok", f"{len(enabled)} of {total} enabled"))
    else:
        report.add(CheckResult("Automation tools", "ok", f"all {total} available"))


def _check_history(report: DiagnosticReport, history) -> None:
    if history is None:
        return
    entries = len(history.entries())
    path = getattr(history, "path", None)
    report.add(
        CheckResult("Task history", "ok", f"{entries} recorded",
                    f"saved at {path}" if path else "")
    )


def _check_startup(report: DiagnosticReport, manager, executable_path: str) -> None:
    if manager is None:
        return
    if sys.platform.startswith("win"):
        enabled = manager.is_enabled()
        report.add(
            CheckResult("Windows startup", "ok" if enabled else "skipped",
                        "registered" if enabled else "not registered")
        )
    else:
        report.add(CheckResult("Windows startup", "skipped", "not applicable on this platform"))


def _check_emergency_stop(report: DiagnosticReport, engine) -> None:
    stopped = bool(getattr(engine, "emergency_stopped", False))
    report.add(
        CheckResult("Emergency stop", "error" if stopped else "ok",
                    "engaged" if stopped else "Ctrl+Alt+J is armed")
    )


def run_diagnostics(
    config: Dict[str, object],
    voice=None,
    gemini=None,
    browser=None,
    camera=None,
    registry=None,
    planner=None,
    history=None,
    startup_manager=None,
    engine=None,
    executable: bool = False,
    executable_path: str = "",
    test_connection: bool = False,
) -> DiagnosticReport:
    """Run every self-check and return a report. Never raises."""
    import time

    started = time.monotonic()
    report = DiagnosticReport()
    checks: List[Callable[[DiagnosticReport], None]] = [
        lambda r: _check_runtime(r, executable),
        lambda r: _check_config(r, config),
        lambda r: _check_wake_word(r, config),
    ]
    for check in checks:
        try:
            check(report)
        except Exception as exc:  # pragma: no cover - a broken check must not hide the rest
            log.debug("diagnostic check failed", exc_info=True)
            report.add(CheckResult("Diagnostics", "warning", str(exc)))

    if voice is not None:
        _check_microphone(report, voice)
        _check_speech_backends(report, voice)
    _check_gemini(report, gemini, test_connection)
    _check_browser(report, browser)
    _check_camera(report, camera)
    _check_tools(report, registry, planner)
    _check_history(report, history)
    _check_startup(report, startup_manager, executable_path)
    if engine is not None:
        _check_emergency_stop(report, engine)

    report.duration_ms = (time.monotonic() - started) * 1000.0
    log.info("diagnostics: %s", report.summary())
    return report


__all__ = ["DiagnosticReport", "CheckResult", "run_diagnostics"]
