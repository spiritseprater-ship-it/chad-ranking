"""
main.py - JARVIS Phase 1 entry point.

Wires together:

* ``config.json``          - validated before use
* ``brain.Brain``          - speech -> canonical command
* ``actions.ActionEngine`` - canonical command -> Windows action
* ``voice.VoiceEngine``    - two-stage standby/active listening
* ``ui.MainWindow``        - PySide6 panel + system tray

Run::

    python main.py            # normal launch
    python main.py --check    # environment/dependency report
    python main.py --config other.json

The PySide6 import is guarded so that configuration handling and ``--check``
work on machines without a GUI library (useful for CI).

Architecture notes
------------------
* one worker thread executes commands (never the GUI thread)
* the GUI drains three queues with a ``QTimer``: voice events, action results
  and confirmation/choice requests
* confirmations block the worker thread, not the GUI, until the user answers
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

# PySide6 is only needed for the GUI; keep the import guarded so the module can
# still be imported (config checks, unit tests, --check) without it.
try:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    HAVE_QT = True
except Exception:  # pragma: no cover - GUI library missing
    QTimer = None  # type: ignore[assignment]
    QApplication = None  # type: ignore[assignment]
    HAVE_QT = False

# allow "python main.py" from inside the JARVIS folder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from actions import (  # noqa: E402
    ActionEngine,
    ActionResult,
    GlobalHotkey,
    PermissionManager,
    ToolRegistry,
)
from brain import Brain, ParsedCommand, Router  # noqa: E402
from desktop import DesktopController, StartupManager  # noqa: E402
from diagnostics import run_diagnostics  # noqa: E402
from gemini import (  # noqa: E402
    DEFAULT_LIVE_MODEL,
    DEFAULT_MODEL,
    GeminiClient,
    GeminiError,
    extract_api_key,
    looks_like_placeholder,
)
from paths import (  # noqa: E402
    application_dir,
    default_config_path,
    ensure_user_config,
    find_dotenv,
    entry_path,
    log_dir,
    resource_dir,
    user_data_dir,
)
from planner import (  # noqa: E402
    TOOL_PREFIX,
    TaskHistory,
    TaskPlanner,
    TaskRunner,
)
from voice import (  # noqa: E402
    ERROR,
    LISTENING,
    PROCESSING,
    SPEAKING,
    STANDBY,
    MicStream,
    Speaker,
    SpeechRecognizer,
    VoiceEngine,
    VoiceEvent,
    Vad,
    WakeWordEngine,
)
log = logging.getLogger("jarvis.main")

# --- filesystem locations (see paths.py) ---------------------------------
# BASE_DIR is the folder the user sees: the onedir folder when packaged, the
# JARVIS folder when running from source.  RESOURCE_DIR holds the read-only
# bundled resources (default config.json, assets).
BASE_DIR = application_dir()
RESOURCE_DIR = resource_dir()
DEFAULT_CONFIG_PATH = default_config_path()

CONFIG_DEFAULTS: Dict[str, object] = {
    "wake_word": {
        "enabled": True, "primary": "hey_jarvis", "additional": [],
        "custom_models": {}, "threshold": 0.5, "refractory_seconds": 2.0,
        "activation_phrases": ["chalo kaam karte hain"],
        "activation_response": "JARVIS online. Ready for your command.",
    },
    "speech": {
        "backend": "google", "language": "en-IN", "fallback_language": "hi-IN",
        "google_api_key_env": "GOOGLE_SPEECH_API_KEY",
        "sample_rate": 16000, "frame_duration_ms": 80,
        "microphone": {"device": None, "name_contains": ""},
    },
    "voice": {"engine": "sapi5", "voice_name": "", "rate": 175, "volume": 0.9},
    "conversation": {"timeout_seconds": 30, "announce_timeout": False},
    "browser": {"default": "chrome", "search_url": "https://www.google.com/search?q={query}"},
    "permissions": {
        "require_confirmation": {}, "allowed_file_roots": [], "sensitive_paths": [],
    },
    "logging": {"level": "INFO", "max_bytes": 1048576, "backup_count": 3},
}

RESPONSES: Dict[str, str] = {
    "didnt_catch": "Sorry, I didn't catch that. Say it again.",
    "standby": "Back to standby.",
    "listening_stop": "Stopped listening.",
    "exit": "Goodbye. JARVIS is shutting down.",
    "emergency": "Emergency stop engaged.",
    "mic_missing": "I couldn't find a working microphone. Check Windows "
                   "Settings > Privacy > Microphone, and try again.",
}


# ---------------------------------------------------------------------------
# configuration
# ---------------------------------------------------------------------------

class ConfigError(RuntimeError):
    pass


def load_config(path: Optional[str] = None) -> Dict[str, object]:
    """Load, merge and validate ``config.json``."""
    if not path and not os.environ.get("JARVIS_CONFIG"):
        # First run from a packaged build: make sure a writable copy of the
        # default config exists in the user data dir rather than inside the
        # bundle (which may be read-only under Program Files).
        config_path = ensure_user_config()
    else:
        config_path = Path(path or os.environ.get("JARVIS_CONFIG") or DEFAULT_CONFIG_PATH)
    if not config_path.exists():
        log.warning("config file %s not found - using built-in defaults", config_path)
        raw: Dict[str, object] = {}
    else:
        try:
            with open(config_path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"{config_path} is not valid JSON: {exc}") from exc
        except OSError as exc:
            raise ConfigError(f"Could not read {config_path}: {exc}") from exc

    config = _deep_merge(json.loads(json.dumps(CONFIG_DEFAULTS)), raw)
    warnings = validate_config(config)
    for warning in warnings:
        log.warning("config: %s", warning)
    config["_warnings"] = warnings
    config["_path"] = str(config_path)
    return config


def _deep_merge(base: Dict[str, object], override: Dict[str, object]) -> Dict[str, object]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)  # type: ignore[arg-type]
        else:
            result[key] = value
    return result


def validate_config(config: Dict[str, object]) -> List[str]:
    """Return human-readable configuration problems (non-fatal warnings)."""
    problems: List[str] = []

    wake = config.get("wake_word") or {}
    if not wake.get("primary"):
        problems.append("wake_word.primary is empty - set it to 'hey_jarvis'")
    if not isinstance(wake.get("threshold", 0.5), (int, float)):
        problems.append("wake_word.threshold must be a number")
    for name, value in (wake.get("custom_models") or {}).items():
        if not isinstance(value, str):
            problems.append(f"wake_word.custom_models.{name} must be a file path")

    speech = config.get("speech") or {}
    backend = str(speech.get("backend", "google")).lower()
    if backend not in ("google", "whisper", "vosk", "auto"):
        problems.append(f"speech.backend '{backend}' is not one of google/whisper/vosk/auto")
    if not speech.get("language"):
        problems.append("speech.language is empty - defaulting to en-IN")
        speech["language"] = "en-IN"

    conversation = config.get("conversation") or {}
    timeout = conversation.get("timeout_seconds")
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        problems.append("conversation.timeout_seconds must be a positive number")
        conversation["timeout_seconds"] = 30

    voice = config.get("voice") or {}
    rate = voice.get("rate")
    if not isinstance(rate, int) or rate < 50 or rate > 400:
        problems.append("voice.rate must be an integer between 50 and 400")

    browser = config.get("browser") or {}
    if "{query}" not in str(browser.get("search_url", "")):
        problems.append("browser.search_url must contain the {query} placeholder")

    hotkey = str((config.get("hotkey") or {}).get("emergency_stop", "ctrl+alt+j")).lower()
    if hotkey != "ctrl+alt+j":
        problems.append(
            f"hotkey.emergency_stop '{hotkey}' is not supported yet; using Ctrl+Alt+J"
        )
        config.setdefault("hotkey", {})["emergency_stop"] = "ctrl+alt+j"  # type: ignore[index]

    return problems


# ---------------------------------------------------------------------------
# logging
# ---------------------------------------------------------------------------

def setup_logging(config: Dict[str, object]) -> None:
    level_name = os.environ.get("JARVIS_LOG_LEVEL") or str(
        (config.get("logging") or {}).get("level", "INFO")
    )
    level = getattr(logging, str(level_name).upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S"
    )
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    root.addHandler(stream)

    log_dir = log_dir()
    handler_config = config.get("logging") or {}
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            log_dir / "jarvis.log",
            maxBytes=int(handler_config.get("max_bytes", 1048576)),
            backupCount=int(handler_config.get("backup_count", 3)),
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError as exc:  # pragma: no cover - read-only install
        log.warning("could not create log file: %s", exc)


# ---------------------------------------------------------------------------
# voice engine construction
# ---------------------------------------------------------------------------

def build_voice_engine(config: Dict[str, object]) -> VoiceEngine:
    """Create the two-stage listening engine from the configuration."""
    speech_cfg = config.get("speech") or {}
    wake_cfg = config.get("wake_word") or {}
    vad_cfg = speech_cfg.get("vad") or {}
    voice_cfg = config.get("voice") or {}
    mic_cfg = speech_cfg.get("microphone") or {}

    # microphone selection: explicit index wins, then a name fragment
    device: Optional[int] = None
    name_contains = str(mic_cfg.get("name_contains") or "")
    if mic_cfg.get("device") is not None:
        try:
            device = int(mic_cfg["device"])
        except (TypeError, ValueError):
            device = None
    if device is None:
        device = MicStream.select_device(name_contains or None)

    mic = MicStream(
        device=device,
        sample_rate=int(speech_cfg.get("sample_rate", 16000)),
        frame_ms=int(speech_cfg.get("frame_duration_ms", 80)),
    )

    model_dir = os.environ.get("OPENWAKEWORD_MODEL_DIR") or None
    wake_names = [str(wake_cfg.get("primary") or "")]
    wake_names += [str(name) for name in (wake_cfg.get("additional") or [])]
    for name, path in (wake_cfg.get("custom_models") or {}).items():
        wake_names.append(str(name))
        if path and not model_dir:
            model_dir = os.path.dirname(str(path))

    wake = WakeWordEngine(
        model_names=wake_names,
        model_dir=model_dir,
        threshold=float(wake_cfg.get("threshold", 0.5)),
    )
    mode = wake.setup(refractory_seconds=float(wake_cfg.get("refractory_seconds", 2.0)))
    log.info("wake word engine mode: %s", mode)

    whisper_cfg = speech_cfg.get("whisper") or {}
    vosk_cfg = speech_cfg.get("vosk") or {}
    recognizer = SpeechRecognizer(
        backend=str(speech_cfg.get("backend", "google")),
        language=str(speech_cfg.get("language", "en-IN")),
        fallback_language=str(speech_cfg.get("fallback_language", "hi-IN")),
        google_key=os.environ.get(
            str(speech_cfg.get("google_api_key_env", "GOOGLE_SPEECH_API_KEY"))
        )
        or None,
        whisper_model_size=str(whisper_cfg.get("model_size", "tiny")),
        whisper_device=str(whisper_cfg.get("device", "cpu")),
        whisper_compute_type=str(whisper_cfg.get("compute_type", "int8")),
        whisper_language=whisper_cfg.get("language"),
        whisper_prompt=whisper_cfg.get("initial_prompt"),
        vosk_model_path=os.environ.get("VOSK_MODEL_PATH")
        or vosk_cfg.get("model_path")
        or None,
    )
    backend = recognizer.initialize()
    log.info("speech recognition backend: %s", backend)
    if recognizer.error:
        log.warning("speech backend note: %s", recognizer.error)

    speaker = Speaker(
        engine=str(voice_cfg.get("engine", "sapi5")),
        voice_name=str(voice_cfg.get("voice_name") or ""),
        rate=int(voice_cfg.get("rate", 175)),
        volume=float(voice_cfg.get("volume", 0.9)),
    )
    if not speaker.initialize():
        log.error("speech synthesis unavailable - responses will appear on screen only")

    vad = Vad(
        start_threshold=float(vad_cfg.get("start_threshold", 0.012)),
        end_threshold=float(vad_cfg.get("end_threshold", 0.008)),
        noise_floor_multiplier=float(vad_cfg.get("noise_floor_multiplier", 3.0)),
        silence_duration_ms=int(vad_cfg.get("silence_duration_ms", 900)),
        max_utterance_seconds=int(vad_cfg.get("max_utterance_seconds", 12)),
        calibration_frames=int(vad_cfg.get("calibration_frames", 6)),
    )

    conversation = config.get("conversation") or {}
    timeout = float(conversation.get("timeout_seconds", 30))
    engine = VoiceEngine(
        recognizer=recognizer,
        speaker=speaker,
        wake_word=wake,
        vad=vad,
        mic=mic,
        conversation_timeout=timeout,
        activation_phrases=wake_cfg.get("activation_phrases") or [],
        activation_response=str(wake_cfg.get("activation_response") or ""),
        self_echo_cooldown_ms=int(voice_cfg.get("self_echo_cooldown_ms", 700)),
    )
    return engine


# ---------------------------------------------------------------------------
# command worker
# ---------------------------------------------------------------------------

@dataclass
class _ConfirmationWait:
    event: threading.Event
    accepted: bool = False


class CommandWorker(threading.Thread):
    """Execute commands off the GUI thread; report back through queues."""

    def __init__(self, engine: ActionEngine) -> None:
        super().__init__(name="jarvis-commands", daemon=True)
        self._engine = engine
        self._commands: "queue.Queue[ParsedCommand]" = queue.Queue()
        self._specials: "queue.Queue[tuple]" = queue.Queue()
        self._choices: "queue.Queue[tuple]" = queue.Queue()
        self._confirmations: Dict[str, _ConfirmationWait] = {}
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._pending_choice = False
        self._pending_payload: Dict[str, object] = {}

        # consumed by the GUI thread
        self.results: "queue.Queue[ActionResult]" = queue.Queue()
        self.choice_requests: "queue.Queue[ActionResult]" = queue.Queue()
        self.confirmation_requests: "queue.Queue[tuple]" = queue.Queue()

    # -- submission ---------------------------------------------------------

    def submit(self, parsed: ParsedCommand) -> None:
        self._commands.put(parsed)

    def submit_special(self, kind: str, payload: Optional[Dict[str, object]] = None) -> None:
        """Queue a non-command job (AI turn, planner run, diagnostics, ...)."""
        self._specials.put((kind, payload or {}))

    def submit_choice(self, text: str, payload: Optional[Dict[str, object]] = None) -> bool:
        with self._lock:
            if not self._pending_choice:
                return False
            payload = payload or self._pending_payload
        self._choices.put((text, payload))
        return True

    def answer_confirmation(self, key: str, accepted: bool) -> bool:
        with self._lock:
            wait = self._confirmations.get(key)
            if wait is None:
                return False
            wait.accepted = accepted
            wait.event.set()
            return True

    @property
    def has_pending_choice(self) -> bool:
        with self._lock:
            return self._pending_choice

    @property
    def pending_choice_payload(self) -> Dict[str, object]:
        with self._lock:
            return dict(self._pending_payload)

    # -- thread -------------------------------------------------------------

    def stop(self, timeout: float = 3.0) -> None:
        self._stop.set()
        if self.is_alive():
            self.join(timeout)

    def _wait(self, event: threading.Event, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while not event.is_set() and not self._stop.is_set() and time.monotonic() < deadline:
            event.wait(timeout=0.2)
        return event.is_set() and not self._stop.is_set()

    def run(self) -> None:
        while not self._stop.is_set():
            if self._handle_special():
                continue
            try:
                parsed = self._commands.get(timeout=0.2)
            except queue.Empty:
                continue

            result = self._engine.execute(parsed)

            if result.needs_confirmation:
                self._handle_confirmation(result)
                continue
            if result.needs_choice:
                self._handle_choice(result)
                continue
            self.results.put(result)

    def _handle_special(self) -> bool:
        """Run one queued special job; True when something was handled."""
        try:
            kind, payload = self._specials.get_nowait()
        except queue.Empty:
            return False
        handler = getattr(self, "on_special", None)
        if handler is None:
            return False
        result = handler(kind, payload)
        if result is not None:
            self.results.put(result)
        return True

    def _handle_confirmation(self, result: ActionResult) -> None:
        key = uuid.uuid4().hex
        payload = dict(result.confirmation_payload)
        self.confirmation_requests.put((key, payload))
        wait = _ConfirmationWait()
        with self._lock:
            self._confirmations[key] = wait
        accepted = self._wait(wait.event, 180.0) and wait.accepted
        with self._lock:
            self._confirmations.pop(key, None)

        if accepted:
            reply = self._engine.confirm(payload)
        else:
            reply = ActionResult(
                success=False, status="info", command=result.command,
                message="No problem, I cancelled that.",
            )
        self.results.put(reply)

    def _handle_choice(self, result: ActionResult) -> None:
        payload = dict(result.choice_payload or {})
        with self._lock:
            self._pending_payload = payload
            self._pending_choice = True
        try:
            self.choice_requests.put(result)
            try:
                answer, answer_payload = self._choices.get(
                    timeout=180.0 if not self._stop.is_set() else 0.05
                )
            except queue.Empty:
                answer, answer_payload = "", {}
            if answer:
                reply = self._engine.execute_choice(answer, answer_payload or payload)
            else:
                reply = ActionResult(
                    success=False, status="info", command=result.command,
                    message="Let's forget that one.",
                )
            self.results.put(reply)
        finally:
            with self._lock:
                self._pending_choice = False
                self._pending_payload = {}


# ---------------------------------------------------------------------------
# application
# ---------------------------------------------------------------------------

class JarvisApp:
    def __init__(self, config: Dict[str, object]) -> None:
        self.config = config
        self.brain = Brain()
        permissions_cfg = config.get("permissions") or {}
        self.permissions = PermissionManager(
            rules=permissions_cfg.get("require_confirmation") or {},
            allowed_roots=permissions_cfg.get("allowed_file_roots") or [],
            sensitive_paths=permissions_cfg.get("sensitive_paths") or [],
        )
        self.engine = ActionEngine(config, self.permissions)
        self.voice = build_voice_engine(config)
        self.worker = CommandWorker(self.engine)
        self.worker.on_special = self._on_special
        self.tool_confirmations: Dict[str, _ConfirmationWait] = {}
        self.last_report = None
        # imported lazily: PySide6 is only needed when the GUI is created
        from ui import MainWindow

        self.window = MainWindow(config)
        self.window._app = self
        self.hotkey = GlobalHotkey(self._emergency_stop)
        self._speaking = False
        self._last_state = STANDBY
        self._drain_timer = None
        self._mic_error_count = 0

        self._wire()

    # -- wiring -------------------------------------------------------------

    def _wire(self) -> None:
        self.window.startRequested.connect(self.start_listening)
        self.window.stopRequested.connect(self.stop_listening)
        self.window.settingsRequested.connect(self.show_settings)
        self.window.exitRequested.connect(self.shutdown)
        self.window.choiceMade.connect(self.worker.submit_choice)

        self.voice.mic.on_error = self._on_mic_error
        self.engine.register_emergency_stop(self._on_emergency_stop_engine)

        if HAVE_QT:
            self._drain_timer = QTimer()
            self._drain_timer.setInterval(100)
            self._drain_timer.timeout.connect(self._drain_events)
            self._drain_timer.start()

        additional = (self.config.get("wake_word") or {}).get("additional") or []
        wake_text = "hey Jarvis"
        if additional:
            wake_text += " + " + ", ".join(str(w) for w in additional)
        self.window.set_wake_word(wake_text)

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        try:
            import pyautogui

            pyautogui.FAILSAFE = True
        except Exception as exc:  # pragma: no cover - pyautogui missing
            log.info("pyautogui not available yet (%s); automation commands will fail", exc)

        if not self.hotkey.start():
            self.window.append_log(
                "Global hotkey not registered - use the window's Stop button."
            )
        self.worker.start()
        self.voice.start()
        self.window.show()
        self.window.append_log("JARVIS started. Say 'Hey Jarvis'.")

    def shutdown(self) -> None:
        self.window.append_log("Shutting down JARVIS...")
        self.voice.stop()
        self.worker.stop()
        self.hotkey.stop()
        if self._drain_timer is not None:
            self._drain_timer.stop()
        self.window._allow_quit = True
        if HAVE_QT and QApplication.instance() is not None:
            QApplication.instance().quit()  # type: ignore[union-attr]

    # -- listening control --------------------------------------------------

    def start_listening(self) -> None:
        self.engine.reset_emergency_stop()
        self.voice.activate()
        self.window.append_log("Manual activation requested.")

    def stop_listening(self) -> None:
        self.voice.deactivate()
        self.window.append_log("Manual deactivation requested.")

    # -- settings -----------------------------------------------------------

    def show_settings(self) -> None:
        from ui import SettingsDialog

        dialog = SettingsDialog(self.config, self.window)
        dialog.configChanged.connect(self._on_config_saved)
        dialog.exec()

    def _on_config_saved(self, new_config: Dict[str, object]) -> None:
        self.config = new_config
        ui_cfg = new_config.get("ui") or {}
        if "low_resource" in ui_cfg:
            self.set_low_resource(bool(ui_cfg.get("low_resource")))
        if "compact" in ui_cfg:
            try:
                self.window.set_compact(bool(ui_cfg.get("compact")))
            except Exception:  # pragma: no cover - Qt widgets
                log.debug("compact mode not applied")
        startup = bool(ui_cfg.get("startup"))
        try:
            self.startup_manager.set_enabled(startup, self._executable_path())
        except Exception as exc:  # pragma: no cover - Windows registry
            log.warning("could not apply the startup setting: %s", exc)

        timeout = float((new_config.get("conversation") or {}).get("timeout_seconds", 30))
        self.voice.set_conversation_timeout(timeout)

        mic_cfg = ((new_config.get("speech") or {}).get("microphone") or {})
        if mic_cfg.get("device") is not None:
            try:
                self.voice.mic.set_device(int(mic_cfg["device"]))
            except (TypeError, ValueError):
                log.warning("invalid microphone index in config")

        self.window.append_log(
            "Settings saved. Wake-word and speech-backend changes need a restart."
        )
        log.info("settings applied (timeout=%ss)", timeout)

    # -- events -------------------------------------------------------------

    def _drain_events(self) -> None:
        while True:
            try:
                event = self.voice.events.get_nowait()
            except queue.Empty:
                break
            self._handle_event(event)

        self._drain_tool_confirmations()

        while True:
            try:
                result = self.worker.results.get_nowait()
            except queue.Empty:
                break
            self.on_action_result(result)

        while True:
            try:
                result = self.worker.choice_requests.get_nowait()
            except queue.Empty:
                break
            self.on_choice_requested(result)

        while True:
            try:
                key, payload = self.worker.confirmation_requests.get_nowait()
            except queue.Empty:
                break
            self.on_confirmation_requested(key, payload)

        speaking = self.voice.speaker.is_speaking
        if speaking and not self._speaking:
            self._speaking = True
            self._last_state = self.voice.state
            self.window.set_state(SPEAKING)
        elif not speaking and self._speaking:
            self._speaking = False
            state = self._last_state if self._last_state != SPEAKING else STANDBY
            self.window.set_state(state)

    def _handle_event(self, event: VoiceEvent) -> None:
        kind = event.kind
        payload = event.payload or {}

        if kind == "status":
            state = str(payload.get("state", STANDBY))
            self._last_state = state
            self.window.set_state(state)
            self.window.append_log(
                f"[{state}] {payload.get('reason', '')}".strip()
            )
        elif kind == "info":
            self.window.append_log(str(payload.get("message", "")))
        elif kind == "wakeword":
            self.window.append_log(f"Wake word detected: {payload.get('reason', '')}")
        elif kind == "error":
            message = str(payload.get("message", "Unknown error"))
            self.window.append_log(f"ERROR: {message}")
            self.window.set_state(ERROR)
        elif kind == "transcript":
            text = str(payload.get("text", ""))
            seconds = float(payload.get("seconds") or 0.0)
            log.info("heard: %s (%.2fs)", text, seconds)
            self.window.append_log(f"You said: {text}")
            if text:
                self._handle_transcript(text)

    def _handle_transcript(self, text: str) -> None:
        # a pending disambiguation answer wins over a brand new command
        if self.worker.has_pending_choice:
            if self.worker.submit_choice(text, self.worker.pending_choice_payload):
                self.window.append_log("Choice submitted.")
            return

        decision = self.router.route(text)
        self.window.set_command(f"{decision.label}  ({decision.kind})")

        if decision.kind == "cancel":
            self.worker.submit_special("cancel")
            return
        if decision.kind == "unknown":
            self.window.set_command("(unrecognized)")
            self.speak(RESPONSES["didnt_catch"])
            self.window.append_log(decision.reason)
            return
        if decision.kind == "ai":
            self.worker.submit_special("ai", {"text": decision.text})
            return

        parsed = decision.command
        if parsed.command in ("exit_jarvis", "stop_listening", "go_standby"):
            self._handle_lifecycle(parsed.command)
            return
        if parsed.command in ("task_history", "self_diagnostics", "low_resource_mode"):
            kind = {"task_history": "history", "self_diagnostics": "diagnostics",
                    "low_resource_mode": "low_resource"}[parsed.command]
            self.worker.submit_special(kind)
            return
        if parsed.is_ambiguous:
            self.speak(parsed.label)
            return

        self.worker.submit(parsed)

    def _handle_lifecycle(self, command: str) -> None:
        if command == "exit_jarvis":
            self.speak(RESPONSES["exit"])
            if HAVE_QT:
                timer = QTimer()
                timer.singleShot(400, self.shutdown)
                timer.start()
            else:
                self.shutdown()
        elif command == "stop_listening":
            self.speak(RESPONSES["listening_stop"])
            self.voice.deactivate()
        else:  # go_standby
            self.speak(RESPONSES["standby"])
            self.voice.deactivate()

    # -- results -----------------------------------------------------------

    def on_action_result(self, result: ActionResult) -> None:
        self.window.set_action(result.describe(), result.success)
        self.window.append_log(f"[action] {result.describe()}")
        if result.needs_choice:
            return  # the prompt is spoken by on_choice_requested
        if result.message:
            self.speak(result.message)

    def on_choice_requested(self, result: ActionResult) -> None:
        self.window.show_choices(result)
        self.speak(result.message)
        log.info("waiting for a disambiguation answer")

    def on_confirmation_requested(self, key: str, payload: Dict[str, object]) -> None:
        message = str(payload.get("message", "Allow this action?"))
        self.window.append_log(f"[confirm] {message}")
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox(self.window)
        box.setWindowTitle("JARVIS confirmation")
        box.setText(message)
        box.setInformativeText(
            "Your permission settings require confirmation. "
            "Press Yes or say 'yes'."
        )
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        answer = box.exec()
        accepted = answer == QMessageBox.Yes
        self.worker.answer_confirmation(key, accepted)
        self.window.append_log("Confirmation answered: " + ("yes" if accepted else "no"))

    # -- speech -------------------------------------------------------------

    def speak(self, text: str) -> None:
        if text:
            self.voice.speaker.say(text)

    def _on_mic_error(self, message: str) -> None:
        self._mic_error_count += 1
        self.window.set_mic_status("error", "#c0392b")
        self.window.append_log(f"Microphone problem: {message}")
        log.error("microphone error: %s", message)
        if self._mic_error_count == 1:
            self.speak(RESPONSES["mic_missing"])

    # -- emergency stop -----------------------------------------------------

    def _emergency_stop(self) -> None:
        self.engine.emergency_stop()
        self.voice.deactivate()
        self.window.append_log("EMERGENCY STOP pressed (Ctrl + Alt + J).")
        self.window.set_state(ERROR)
        self.window.set_action("Emergency stop engaged", False)
        self.speak(RESPONSES["emergency"])

    def _on_emergency_stop_engine(self) -> None:
        self.window.append_log("Automation interrupted by emergency stop.")


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

    # -- optional capabilities (Gemini, automation, planning) -------------

    #: verbs that suggest a multi-step task rather than a single chat turn
    PLANNER_HINTS = (
        "open", "search", "find", "create", "make", "draft", "write", "send",
        "book", "set", "change", "rename", "move", "copy", "delete", "install",
        "update", "check", "plan", "research", "summar", "type", "click",
        "scroll", "navigate", "launch", "run", "close", "minimize",
    )

    def _executable_path(self) -> str:
        return entry_path()

    def _build_runtime(self) -> None:
        """Build Gemini, desktop/browser/camera controllers, planner and history."""
        configured = str(self.config.get("user_data_dir") or "").strip()
        data_dir = Path(os.path.expandvars(configured)) if configured else user_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = data_dir

        # --- Gemini ------------------------------------------------------
        gemini_cfg = dict(self.config.get("gemini") or {})
        self.gemini_problem = ""
        api_key = str(gemini_cfg.get("api_key") or "").strip() or extract_api_key()
        self.gemini = None
        self.live_session = None
        if gemini_cfg.get("enabled") is False:
            self.gemini_problem = "Gemini is switched off in the settings."
        elif api_key and not looks_like_placeholder(api_key):
            try:
                self.gemini = GeminiClient(
                    api_key=api_key,
                    model=str(gemini_cfg.get("model") or DEFAULT_MODEL),
                    temperature=float(gemini_cfg.get("temperature", 0.3)),
                    timeout=float(gemini_cfg.get("timeout_seconds", 45.0)),
                    max_retries=int(gemini_cfg.get("max_retries", 2)),
                    history_path=data_dir / "conversation.json",
                    system_prompt=str(gemini_cfg.get("system_prompt") or ""),
                )
            except GeminiError as exc:
                self.gemini_problem = str(exc)
        elif not api_key:
            self.gemini_problem = "No Gemini API key found. Add one in Settings."
        else:
            self.gemini_problem = "The API key looks like a placeholder - add a real key in Settings."

        # --- desktop, browser, camera -----------------------------------
        desktop_cfg = dict(self.config.get("desktop") or {})
        self.desktop = DesktopController(
            allowed_roots=(
                desktop_cfg.get("allowed_roots")
                or (self.config.get("permissions") or {}).get("allowed_file_roots")
                or []
            ),
            sensitive_paths=(self.config.get("permissions") or {}).get("sensitive_paths") or [],
            screenshot_dir=Path(str(desktop_cfg.get("screenshot_dir") or (data_dir / "screenshots"))),
            camera_enabled=bool(desktop_cfg.get("camera_enabled", False)),
        )

        browser_cfg = dict(self.config.get("browser") or {})
        self.browser = None
        if browser_cfg.get("enabled"):
            try:
                from browser import BrowserController

                self.browser = BrowserController(
                    headless=bool(browser_cfg.get("headless", False)),
                    user_data_dir=browser_cfg.get("user_data_dir") or None,
                )
                self.browser.install_hint = self.browser.install_hint  # keep the helper
            except Exception as exc:  # noqa: BLE001 - optional capability
                log.warning("browser automation disabled: %s", exc)

        camera_cfg = dict(self.config.get("camera") or {})
        self.camera = None
        if camera_cfg.get("enabled"):
            try:
                from camera import CameraController

                self.camera = CameraController(
                    enabled=True,
                    save_dir=Path(str(camera_cfg.get("save_dir") or (data_dir / "photos"))),
                    permission_granted=bool(camera_cfg.get("permission_granted", False)),
                )
            except Exception as exc:  # noqa: BLE001 - optional capability
                log.warning("camera support disabled: %s", exc)

        # --- tool registry, router, planner, runner ----------------------
        tools_cfg = dict(self.config.get("tools") or {})
        enabled_tools = [str(t) for t in (tools_cfg.get("enabled") or [])]
        self.registry = ToolRegistry(
            desktop=self.desktop,
            browser=self.browser,
            camera=self.camera,
            permissions=self.permissions,
            gemini=self.gemini,
            local_executor=self._execute_local_command,
            allowed_tools=enabled_tools or None,
            confirm=self._confirm_tool,
        )

        wake_cfg = dict(self.config.get("wake_word") or {})
        self.router = Router(
            brain=self.brain,
            ai_enabled=gemini_cfg.get("enabled", True) is not False,
            ai_available=self.gemini is not None,
            wake_words=["jarvis"] + [str(w) for w in (wake_cfg.get("additional") or [])],
        )
        self.history = TaskHistory(data_dir / "task_history.json")
        self.planner = TaskPlanner(
            ai_client=self.gemini,
            allowed_tools=enabled_tools,
            brain=self.brain,
            router=self.router,
        )
        self.runner = TaskRunner(
            planner=self.planner,
            executor=self.registry.execute,
            history=self.history,
            on_step=self._on_step_progress,
            on_done=self._on_task_done,
        )
        self.startup_manager = StartupManager(self._executable_path())
        self.last_task = None

    # -- tool confirmation -------------------------------------------------

    def _drain_tool_confirmations(self) -> None:
        """GUI thread: answer a pending tool confirmation dialog."""
        while True:
            try:
                key, name, arguments = self.tool_confirmation_requests.get_nowait()
            except queue.Empty:
                break
            wait = self.tool_confirmations.pop(key, None)
            if wait is None:
                continue
            from PySide6.QtWidgets import QMessageBox

            box = QMessageBox(self.window)
            box.setWindowTitle("JARVIS confirmation")
            box.setText(f"Allow JARVIS to use {name}?")
            box.setInformativeText(
                "This action was requested by the AI. Press Yes to allow it, "
                "or No to cancel."
            )
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            box.setDefaultButton(QMessageBox.No)
            answer = box.exec()
            wait.accepted = answer == QMessageBox.Yes
            wait.event.set()
            self.window.append_log(f"Tool confirmation {name}: {'yes' if wait.accepted else 'no'}")

    def _confirm_tool(self, name: str, arguments: Dict[str, object]) -> bool:
        """Worker thread: ask the user before a sensitive tool runs."""
        key = uuid.uuid4().hex
        wait = _ConfirmationWait()
        self.tool_confirmations[key] = wait
        self.tool_confirmation_requests.put((key, name, arguments))
        return bool(self.worker._wait(wait.event, 180.0) and wait.accepted)

    def _execute_local_command(self, name: str, arguments: Dict[str, object]) -> Dict[str, object]:
        """Run a ``local:<command>`` tool through the Phase 1 action engine."""
        command_id = name[len(TOOL_PREFIX):] if name.startswith(TOOL_PREFIX) else name
        parsed = ParsedCommand(
            command=command_id,
            raw=str(arguments.get("text") or ""),
            normalized=str(arguments.get("text") or ""),
            confidence=1.0,
            slots=dict(arguments),
        )
        result = self.engine.execute(parsed)
        return {"ok": result.success, "result": result.message}

    # -- special job dispatch ----------------------------------------------

    def _on_special(self, kind: str, payload: Dict[str, object]):
        handlers = {
            "ai": self._run_ai_turn,
            "plan": self._run_planned_task,
            "cancel": self._run_cancel,
            "history": self._run_task_history,
            "diagnostics": self._run_diagnostics,
            "low_resource": self._run_low_resource,
        }
        handler = handlers.get(kind)
        if handler is None:  # pragma: no cover - defensive
            return None
        try:
            return handler(payload)
        except Exception as exc:  # noqa: BLE001 - a failed job must not kill the worker
            log.exception("special job '%s' failed", kind)
            return ActionResult(
                success=False, status="error",
                message=f"I could not finish that: {exc}", command=kind,
            )

    # -- AI conversation ---------------------------------------------------

    def _run_ai_turn(self, payload: Dict[str, object]) -> ActionResult:
        text = str(payload.get("text") or "")
        if not text.strip():
            return ActionResult(success=False, status="error", message="Nothing to send.")
        if self.gemini is None:
            return ActionResult(
                success=False, status="info",
                message=self.gemini_problem or "Gemini is not configured.",
                command="gemini",
            )
        outcome = self.gemini.run_agent(
            text, self.registry.execute,
            max_tool_rounds=int(payload.get("max_tool_rounds", 4)),
        )
        reply = str(outcome.get("reply", "")).strip()
        calls = outcome.get("tool_calls") or []
        if not reply:
            reply = "I could not produce an answer - please try again."
        if calls:
            reply = f"{reply} (I used {len(calls)} tool call(s).)"
        log.info("gemini reply (%d chars, %d tool calls)", len(reply), len(calls))
        return ActionResult(success=True, status="info", message=reply, command="gemini")

    # -- task planning -----------------------------------------------------

    def _wants_planner(self, text: str) -> bool:
        low = text.lower()
        return any(hint in low for hint in self.PLANNER_HINTS)

    def _run_planned_task(self, payload: Dict[str, object]) -> ActionResult:
        goal = str(payload.get("text") or "")
        if not goal.strip():
            return ActionResult(success=False, status="error", message="Nothing to plan.")
        if self.gemini is None:
            return ActionResult(
                success=False, status="info",
                message="I need a Gemini API key before I can plan and run tasks.",
                command="plan",
            )
        record = self.runner.run(goal, confirm=self._confirm_tool)
        ok = record.status == "completed"
        message = (
            f"Task complete: {record.summary}"
            if ok else
            f"Task stopped: {record.summary or record.status}"
        )
        return ActionResult(
            success=ok, status="info" if ok else "error",
            message=message, command="plan", detail=record.id,
        )

    def _on_step_progress(self, step) -> None:
        """Called from the worker thread: surface failures, stay quiet on success."""
        if step.status == "done":
            return
        self.worker.results.put(
            ActionResult(
                success=False, status="info",
                message=f"Step {step.index} ({step.text}) -> {step.status}: {step.result}",
                command="plan",
            )
        )

    def _on_task_done(self, record) -> None:
        self.last_task = record

    def _run_cancel(self, payload: Dict[str, object]) -> ActionResult:
        cancelled = self.runner.cancel()
        if cancelled:
            return ActionResult(
                success=True, status="info",
                message="I cancelled the running task.", command="cancel",
            )
        return ActionResult(
            success=False, status="info",
            message="There is nothing running to cancel.", command="cancel",
        )

    def _run_task_history(self, payload: Dict[str, object]) -> ActionResult:
        summary = self.history.format_summary(int(payload.get("limit", 10)))
        return ActionResult(
            success=True, status="info", message=summary or "No tasks recorded yet.",
            command="task_history",
        )

    def _run_diagnostics(self, payload: Dict[str, object]) -> ActionResult:
        report = run_diagnostics(
            self.config,
            voice=self.voice,
            gemini=self.gemini,
            browser=self.browser,
            camera=self.camera,
            registry=self.registry,
            planner=self.planner,
            history=self.history,
            startup_manager=self.startup_manager,
            engine=self.engine,
            executable=bool(getattr(sys, "frozen", False)),
            executable_path=self._executable_path(),
            test_connection=bool(payload.get("test_connection", False)),
        )
        self.last_report = report
        log.info("diagnostics\n%s", "\n".join(report.lines()))
        return ActionResult(
            success=report.ok, status="info" if report.ok else "error",
            message=report.speakable(), command="self_diagnostics",
            detail="\n".join(report.lines()),
        )

    # -- resource mode -----------------------------------------------------

    def _run_low_resource(self, payload: Dict[str, object]) -> ActionResult:
        current = bool((self.config.get("ui") or {}).get("low_resource", False))
        enabled = not current
        ui_cfg = dict(self.config.get("ui") or {})
        ui_cfg["low_resource"] = enabled
        self.config["ui"] = ui_cfg
        self.set_low_resource(enabled)
        return ActionResult(
            success=True, status="info",
            message="Low resource mode is on - the orb uses fewer particles."
            if enabled else "Back to standard mode.",
            command="low_resource_mode",
        )

    def set_low_resource(self, enabled: bool) -> None:
        self.config.setdefault("ui", {})["low_resource"] = bool(enabled)
        try:
            self.window.set_low_resource(bool(enabled))
        except Exception:  # pragma: no cover - GUI may not have the orb
            log.debug("low resource mode not applied to the UI")

    # -- UI actions (called from the GUI thread) --------------------------

    def show_task_history(self) -> None:
        self.window.show_task_history(self.history.format_summary(25))

    def show_diagnostics(self, test_connection: bool = False) -> None:
        report = run_diagnostics(
            self.config,
            voice=self.voice,
            gemini=self.gemini,
            browser=self.browser,
            camera=self.camera,
            registry=self.registry,
            planner=self.planner,
            history=self.history,
            startup_manager=self.startup_manager,
            engine=self.engine,
            executable=bool(getattr(sys, "frozen", False)),
            executable_path=self._executable_path(),
            test_connection=test_connection,
        )
        self.last_report = report
        self.window.show_diagnostics(report)

    def maybe_first_run(self) -> None:
        """Show the first-run wizard once, unless the user already finished it."""
        if bool((self.config.get("ui") or {}).get("first_run_complete")):
            return
        try:
            self.window.run_first_run_wizard(self)
        except Exception:  # pragma: no cover - wizard must never block startup
            log.warning("first-run wizard could not be shown", exc_info=True)

    def toggle_startup(self, enabled: bool) -> bool:
        return self.startup_manager.set_enabled(bool(enabled), self._executable_path())


def run_check() -> int:
    """Print an environment report (used by `python main.py --check`)."""
    print("JARVIS environment check")
    print(f"  Python      : {sys.version.split()[0]} ({sys.executable})")
    print(f"  Platform    : {sys.platform}")
    print()

    modules = [
        ("PySide6", "PySide6 GUI"),
        ("sounddevice", "microphone capture"),
        ("numpy", "audio processing"),
        ("openwakeword", "local wake word"),
        ("onnxruntime", "wake-word inference"),
        ("speech_recognition", "Google Web Speech"),
        ("faster_whisper", "local Whisper"),
        ("vosk", "local Vosk"),
        ("pyttsx3", "speech synthesis"),
        ("pyautogui", "keyboard/mouse automation"),
        ("PIL", "screenshots"),
        ("pycaw", "system volume"),
        ("dotenv", ".env loading"),
        ("google.genai", "Gemini SDK"),
        ("playwright", "browser automation (optional)"),
        ("cv2", "camera capture (optional)"),
        ("pywinauto", "UI automation (optional)"),
        ("winreg", "Windows startup setting"),
    ]
    for module, purpose in modules:
        if module == "winreg" and sys.platform != "win32":
            print(f"  [SKIP] {module:<20} {purpose}  (Windows only)")
            continue
        try:
            __import__(module)
            print(f"  [OK]   {module:<20} {purpose}")
        except Exception as exc:
            print(f"  [MISS] {module:<20} {purpose}  ({exc})")

    print()
    api_key = extract_api_key()
    if api_key:
        print(f"  Gemini API key: found ({GeminiClient.mask_secret(api_key)})")
    else:
        print("  Gemini API key: none - set GEMINI_API_KEY or add it in Settings")

    try:
        from actions import ToolRegistry  # noqa: F401
        from desktop import DesktopController  # noqa: F401

        print(f"  Automation tools: {len(ToolRegistry(DesktopController()).names())} available")
    except Exception as exc:
        print(f"  Automation tools: unavailable ({exc})")

    print()
    mics = MicStream.list_devices()
    if mics:
        print("  Microphones:")
        for device in mics[:5]:
            print(f"    - {device['name']}  (index {device['index']})")
    else:
        print("  Microphones: none detected")

    if sys.platform != "win32":
        print("\n  Note: JARVIS targets Windows 11. Automation actions need Windows.")
    return 0


def load_dotenv_file() -> None:
    """Load .env from the user data dir or next to the application."""
    env_path = find_dotenv()
    if env_path is None:
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except Exception:  # pragma: no cover - dotenv missing or no .env file
        pass


def run_diagnostics_cli() -> int:
    """Print a full self-diagnostic report (``python main.py --diagnostics``)."""
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Could not load config: {exc}")
        return 2

    report = run_diagnostics(
        config, executable=bool(getattr(sys, "frozen", False)),
        executable_path=entry_path(),
    )
    for line in report.lines():
        print("  " + line)
    print()
    print("  " + report.summary())
    return 0 if report.ok else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="jarvis", description="JARVIS voice assistant")
    parser.add_argument("--check", action="store_true", help="print environment report and exit")
    parser.add_argument("--config", default=None, help="path to config.json")
    parser.add_argument("--diagnostics", action="store_true",
                        help="run the full JARVIS self-diagnostic report")
    args = parser.parse_args(argv)

    if args.diagnostics:
        return run_diagnostics_cli()

    if args.check:
        return run_check()

    if not HAVE_QT:
        print(
            "PySide6 is not installed. Run:\n"
            "  pip install -r requirements.txt\n"
            "or use 'python main.py --check' to see what is missing.",
            file=sys.stderr,
        )
        return 3

    load_dotenv_file()

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    setup_logging(config)
    log.info("JARVIS starting")

    app = QApplication(sys.argv)  # type: ignore[misc]
    app.setApplicationName("JARVIS")
    app.setQuitOnLastWindowClosed(False)

    jarvis = JarvisApp(config)
    jarvis.start()
    jarvis.maybe_first_run()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
