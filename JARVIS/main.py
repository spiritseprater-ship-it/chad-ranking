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
)
from brain import Brain, ParsedCommand  # noqa: E402
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

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config.json"

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

    log_dir = BASE_DIR / "logs"
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
        # imported lazily: PySide6 is only needed when the GUI is created
        from ui import MainWindow

        self.window = MainWindow(config)
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

        parsed = self.brain.parse(text)
        if parsed is None:
            self.window.set_command("(unrecognized)")
            self.speak(RESPONSES["didnt_catch"])
            return

        self.window.set_command(f"{parsed.label}  ({parsed.confidence:.2f})")

        if parsed.command in ("exit_jarvis", "stop_listening", "go_standby"):
            self._handle_lifecycle(parsed.command)
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
    ]
    for module, purpose in modules:
        try:
            __import__(module)
            print(f"  [OK]   {module:<20} {purpose}")
        except Exception as exc:
            print(f"  [MISS] {module:<20} {purpose}  ({exc})")

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
    try:
        from dotenv import load_dotenv

        load_dotenv(BASE_DIR / ".env")
    except Exception:  # pragma: no cover - dotenv missing or no .env file
        pass


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="jarvis", description="JARVIS voice assistant")
    parser.add_argument("--check", action="store_true", help="print environment report and exit")
    parser.add_argument("--config", default=None, help="path to config.json")
    args = parser.parse_args(argv)

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
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
