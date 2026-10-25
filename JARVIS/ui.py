"""
ui.py - minimal PySide6 desktop interface for JARVIS Phase 1.

Shows:
* the JARVIS title and the current state (STANDBY / LISTENING / PROCESSING /
  SPEAKING / ERROR)
* microphone status (ready, not connected, permission denied)
* the last recognized command and the last executed action
* Start listening / Stop listening / Settings / Exit buttons
* disambiguation buttons when a file-search returns several candidates
* a system tray icon; closing the window minimizes to the tray unless the user
  explicitly chooses Exit

The window never blocks: a ``QTimer`` drains the engine's event queue, and all
buttons simply push work onto the command worker thread owned by ``main.py``.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPixmap,
)
from paths import resource_path, user_data_dir
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

log = logging.getLogger("jarvis.ui")

#: one-line description of each automation tool (also used by the settings dialog)
TOOL_DESCRIPTIONS: Dict[str, str] = {
    "open_application": "launch an installed app by name",
    "search_files": "find files on this PC",
    "open_file": "open a file or folder",
    "search_web": "search the web in the browser",
    "browser_open_url": "open a web address",
    "browser_search": "search the web",
    "browser_open_result": "open a search result by number",
    "browser_extract_text": "read the text of the open page",
    "browser_navigate": "go to a web address",
    "browser_scroll": "scroll the open page",
    "browser_tabs": "list browser tabs",
    "browser_activate_tab": "focus a browser tab",
    "take_screenshot": "capture the screen (needs confirmation)",
    "get_system_status": "list windows and the active window",
    "window_list": "list visible windows",
    "window_focus": "bring a window to the front",
    "window_minimize": "minimize a window",
    "window_maximize": "maximize a window",
    "window_close": "close a window (needs confirmation)",
    "mouse_click": "click on screen (needs confirmation)",
    "mouse_drag": "drag on screen (needs confirmation)",
    "keyboard_type": "type text (needs confirmation)",
    "keyboard_shortcut": "press a key combination (needs confirmation)",
    "file_create_folder": "create a folder",
    "file_rename": "rename a file (needs confirmation)",
    "file_copy": "copy a file",
    "file_move": "move a file (needs confirmation)",
    "file_delete": "delete a file (needs confirmation)",
    "read_document": "read a text document",
    "camera_photo": "take a webcam photo (needs confirmation)",
    "summarize_page": "summarise the open page with Gemini",
}

#: the safe default set for a standard install
RECOMMENDED_TOOLS = frozenset({
    "open_application", "search_files", "open_file", "search_web",
    "browser_open_url", "browser_search", "browser_extract_text", "browser_navigate",
    "browser_scroll", "browser_tabs", "take_screenshot", "get_system_status",
    "window_list", "window_focus", "window_minimize", "window_maximize",
    "file_create_folder", "file_copy", "read_document", "summarize_page",
})

STATE_COLORS: Dict[str, str] = {
    "STANDBY": "#8a8f98",
    "LISTENING": "#2f7fd4",
    "PROCESSING": "#e08a1e",
    "SPEAKING": "#2e9e5b",
    "ERROR": "#c0392b",
}

# bundled read-only assets, and the writable folder for generated icons
ASSETS_DIR = str(resource_path("assets"))
GENERATED_DIR = str(user_data_dir() / "assets" / "generated")
ICON_PATH = os.path.join(GENERATED_DIR, "jarvis_icon.png")


# ---------------------------------------------------------------------------
# icon
# ---------------------------------------------------------------------------

def build_icon(path: str = ICON_PATH) -> QIcon:
    """Create (or reuse) a simple JARVIS tray/window icon.

    No binary asset is committed: the icon is drawn with QPainter at runtime and
    cached under ``assets/generated`` (git-ignored).
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor("#2f7fd4")))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(6, 6, 52, 52)
        painter.setBrush(QBrush(QColor("#eaf3ff")))
        painter.drawEllipse(18, 18, 28, 28)
        painter.setBrush(QBrush(QColor("#2f7fd4")))
        painter.drawEllipse(25, 24, 5, 6)
        painter.drawEllipse(34, 24, 5, 6)
        painter.setPen(Qt.white)
        font = QFont("Segoe UI", 9, QFont.Bold)
        painter.setFont(font)
        painter.drawText(QPoint(12, 62), "J")
        painter.end()
        pixmap.save(path, "PNG")
    return QIcon(path)


# ---------------------------------------------------------------------------
# settings dialog
# ---------------------------------------------------------------------------

class SettingsDialog(QDialog):
    """Edit and save ``config.json``."""

    configChanged = Signal(dict)

    def __init__(self, config: dict, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("JARVIS settings")
        self.setMinimumWidth(460)
        self._config = config

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        wake = config.get("wake_word", {}) or {}
        speech = config.get("speech", {}) or {}
        voice = config.get("voice", {}) or {}
        conversation = config.get("conversation", {}) or {}
        browser = config.get("browser", {}) or {}
        gemini = config.get("gemini", {}) or {}
        tools = config.get("tools", {}) or {}
        mic_cfg = speech.get("microphone", {}) or {}

        self.wake_primary = QLineEdit(str(wake.get("primary", "hey_jarvis")))
        self.wake_additional = QLineEdit(", ".join(wake.get("additional", []) or []))
        self.wake_threshold = QDoubleSpinBox()
        self.wake_threshold.setRange(0.05, 1.0)
        self.wake_threshold.setSingleStep(0.05)
        self.wake_threshold.setValue(float(wake.get("threshold", 0.5)))

        self.timeout = QSpinBox()
        self.timeout.setRange(5, 600)
        self.timeout.setValue(int(conversation.get("timeout_seconds", 30)))

        self.language = QLineEdit(str(speech.get("language", "en-IN")))
        self.backend = QComboBox()
        self.backend.addItems(["google", "whisper", "vosk", "auto"])
        self.backend.setCurrentText(str(speech.get("backend", "google")))

        self.voice_name = QLineEdit(str(voice.get("voice_name", "")))
        self.rate = QSpinBox()
        self.rate.setRange(50, 400)
        self.rate.setValue(int(voice.get("rate", 175)))
        self.volume = QDoubleSpinBox()
        self.volume.setRange(0.0, 1.0)
        self.volume.setSingleStep(0.05)
        self.volume.setValue(float(voice.get("volume", 0.9)))

        voices_button = QPushButton("List available voices")
        voices_button.clicked.connect(self._list_voices)

        self.browser = QComboBox()
        self.browser.addItems(["chrome", "edge", "firefox"])
        self.browser.setCurrentText(str(browser.get("default", "chrome")))
        self.search_url = QLineEdit(str(browser.get("search_url", "")))

        # --- Gemini -------------------------------------------------------
        self.gemini_enabled = QCheckBox("Use Gemini for conversation and tasks")
        self.gemini_enabled.setChecked(bool(gemini.get("enabled", True)))
        self.gemini_key = QLineEdit()
        self.gemini_key.setEchoMode(QLineEdit.Password)
        self.gemini_key.setPlaceholderText("leave empty to use the stored key")
        if gemini.get("api_key"):
            self.gemini_key.setText(str(gemini["api_key"]))
        self.gemini_model = QLineEdit(str(gemini.get("model") or "gemini-3.8-flash"))
        self.gemini_model.setPlaceholderText("gemini-3.8-flash (see the README for the current list)")
        key_button = QPushButton("Store key in your profile")
        key_button.clicked.connect(self._store_key)

        # --- tools --------------------------------------------------------
        self.tool_boxes: Dict[str, QCheckBox] = {}
        tools_layout = QVBoxLayout()
        self.tool_layout = tools_layout
        enabled_tools = set(tools.get("enabled") or [])
        for tool_name, description in sorted(TOOL_DESCRIPTIONS.items()):
            box = QCheckBox(f"{tool_name} - {description}")
            box.setChecked(tool_name in enabled_tools)
            self.tool_boxes[tool_name] = box
            tools_layout.addWidget(box)
        self.all_tools_button = QPushButton("Enable every tool")
        self.all_tools_button.clicked.connect(
            lambda: [box.setChecked(True) for box in self.tool_boxes.values()]
        )
        self.recommended_button = QPushButton("Recommended set only")
        self.recommended_button.clicked.connect(
            lambda: [
                box.setChecked(tool_name in RECOMMENDED_TOOLS)
                for tool_name, box in self.tool_boxes.items()
            ]
        )

        # --- interface ---------------------------------------------------
        self.startup_box = QCheckBox("Launch JARVIS when Windows starts")
        self.startup_box.setChecked(bool((config.get("ui") or {}).get("startup", False)))
        self.low_resource_box = QCheckBox("Low resource mode (fewer orb particles)")
        self.low_resource_box.setChecked(bool((config.get("ui") or {}).get("low_resource", False)))
        self.compact_box = QCheckBox("Compact window")
        self.compact_box.setChecked(bool((config.get("ui") or {}).get("compact", False)))

        self.mic = QComboBox()
        self.mic.addItem("(system default)", None)
        for device in self._devices():
            self.mic.addItem(str(device["name"]), device["index"])
        preferred = mic_cfg.get("device")
        if preferred is not None:
            for index in range(self.mic.count()):
                if self.mic.itemData(index) == preferred:
                    self.mic.setCurrentIndex(index)
                    break
        name_contains = str(mic_cfg.get("name_contains", "") or "")
        if name_contains:
            for index in range(self.mic.count()):
                if name_contains.lower() in str(self.mic.itemText(index)).lower():
                    self.mic.setCurrentIndex(index)
                    break

        form.addRow("Wake word", self.wake_primary)
        form.addRow("Extra wake words", self.wake_additional)
        form.addRow("Wake threshold", self.wake_threshold)
        form.addRow("Conversation timeout (s)", self.timeout)
        form.addRow("Speech language", self.language)
        form.addRow("Speech backend", self.backend)
        form.addRow("Voice name", self.voice_name)
        form.addRow("Voice rate", self.rate)
        form.addRow("Voice volume", self.volume)
        form.addRow("Voice options", voices_button)
        form.addRow("Default browser", self.browser)
        form.addRow("Search URL", self.search_url)
        form.addRow("Microphone", self.mic)

        form.addRow("Gemini", self.gemini_enabled)
        form.addRow("Gemini key", self.gemini_key)
        form.addRow("", key_button)
        form.addRow("Gemini model", self.gemini_model)
        tools_box = QGroupBox("Automation tools")
        tools_inner = QVBoxLayout(tools_box)
        tools_inner.addLayout(tools_layout)
        tools_inner.addWidget(self.all_tools_button)
        tools_inner.addWidget(self.recommended_button)
        form.addRow("Tools", tools_box)
        form.addRow("Startup", self.startup_box)
        form.addRow("Interface", self.low_resource_box)
        form.addRow("", self.compact_box)

        layout = QVBoxLayout(self)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _devices() -> List[Dict[str, object]]:
        try:
            from voice import MicStream

            return MicStream.list_devices()
        except Exception as exc:  # pragma: no cover - audio lib missing
            log.warning("could not list microphones: %s", exc)
            return []

    def _store_key(self) -> None:
        key = self.gemini_key.text().strip()
        if not key:
            QMessageBox.information(
                self, "JARVIS",
                "Paste a Google AI Studio API key first. It is stored in "
                "%USERPROFILE%\\.jarvis\\gemini_key.txt and never written to config.json."
            )
            return
        try:
            path = Path.home() / ".jarvis" / "gemini_key.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(key, encoding="utf-8")
            os.chmod(str(path), 0o600)
            self.gemini_key.clear()
            self.append_log_status("Gemini key stored in your profile.")
            QMessageBox.information(
                self, "JARVIS", f"Key stored at {path}. It is never logged or shared."
            )
        except OSError as exc:
            QMessageBox.critical(self, "JARVIS", f"Could not store the key: {exc}")

    def append_log_status(self, message: str) -> None:
        log.info(message)

    def _list_voices(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Available voices")
        layout = QVBoxLayout(dialog)
        lister = QListWidget()
        try:
            from voice import Speaker

            for voice in Speaker.list_voices():
                lister.addItem(f"{voice['name']}  ({voice['language']})")
        except Exception as exc:
            lister.addItem(f"Could not list voices: {exc}")
        layout.addWidget(lister)
        dialog.resize(420, 320)
        dialog.exec()

    def _save(self) -> None:
        config = dict(self._config)

        wake = dict(config.get("wake_word", {}) or {})
        wake["primary"] = self.wake_primary.text().strip() or "hey_jarvis"
        wake["additional"] = [
            w.strip() for w in self.wake_additional.text().split(",") if w.strip()
        ]
        wake["threshold"] = self.wake_threshold.value()
        config["wake_word"] = wake

        conversation = dict(config.get("conversation", {}) or {})
        conversation["timeout_seconds"] = self.timeout.value()
        config["conversation"] = conversation

        speech = dict(config.get("speech", {}) or {})
        speech["language"] = self.language.text().strip() or "en-IN"
        speech["backend"] = self.backend.currentText()
        mic_cfg = dict(speech.get("microphone", {}) or {})
        device = self.mic.currentData()
        mic_cfg["device"] = device
        mic_cfg["name_contains"] = self.mic.currentText().strip()
        speech["microphone"] = mic_cfg
        config["speech"] = speech

        voice = dict(config.get("voice", {}) or {})
        voice["voice_name"] = self.voice_name.text().strip()
        voice["rate"] = self.rate.value()
        voice["volume"] = self.volume.value()
        config["voice"] = voice

        gemini = dict(config.get("gemini", {}) or {})
        gemini["enabled"] = self.gemini_enabled.isChecked()
        gemini["model"] = self.gemini_model.text().strip() or "gemini-3.8-flash"
        if self.gemini_key.text().strip():
            gemini["api_key"] = self.gemini_key.text().strip()
        config["gemini"] = gemini

        tools = dict(config.get("tools", {}) or {})
        tools["enabled"] = sorted(
            name for name, box in self.tool_boxes.items() if box.isChecked()
        )
        config["tools"] = tools

        ui_cfg = dict(config.get("ui", {}) or {})
        ui_cfg["startup"] = self.startup_box.isChecked()
        ui_cfg["low_resource"] = self.low_resource_box.isChecked()
        ui_cfg["compact"] = self.compact_box.isChecked()
        config["ui"] = ui_cfg

        browser = dict(config.get("browser", {}) or {})
        browser["default"] = self.browser.currentText()
        browser["search_url"] = self.search_url.text().strip() or browser.get(
            "search_url", "https://www.google.com/search?q={query}"
        )
        config["browser"] = browser

        config_path = Path(str(config.get("_path") or (os.path.dirname(os.path.abspath(__file__)) / "config.json")))
        try:
            with open(config_path, "w", encoding="utf-8") as handle:
                json.dump(config, handle, indent=2, ensure_ascii=False)
        except OSError as exc:
            QMessageBox.critical(self, "JARVIS", f"Could not save config.json: {exc}")
            return
        self.configChanged.emit(config)
        self.accept()


# ---------------------------------------------------------------------------
# main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    """The Phase 1 JARVIS panel."""

    startRequested = Signal()
    stopRequested = Signal()
    settingsRequested = Signal()
    exitRequested = Signal()
    choiceMade = Signal(str, object)      # text, payload
    confirmationAnswered = Signal(str, bool)  # payload key, accepted

    def __init__(self, config: dict) -> None:
        super().__init__()
        self.config = config
        self._app = None
        self.setWindowTitle("JARVIS")
        self.resize(520, 560)
        self._tray: Optional[QSystemTrayIcon] = None
        self._allow_quit = False

        self._build_ui()
        self._build_tray()
        self.set_state("STANDBY")

    # -- construction -------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel("JARVIS")
        font = QFont("Segoe UI", 26, QFont.Bold)
        title.setFont(font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # premium particle orb (falls back to a label if OpenGL/Qt painting fails)
        self.orb = None
        try:
            from orb import create_orb_widget

            self.orb = create_orb_widget(low_resource=bool((config.get("ui") or {}).get("low_resource")))
            self.orb.setFixedHeight(300)
            self.orb.clicked = lambda _widget: self.startRequested.emit()
            layout.addWidget(self.orb)
        except Exception as exc:  # pragma: no cover - Qt/painting unavailable
            log.warning("orb widget unavailable (%s); using the text panel only", exc)
            self.orb_label = QLabel("JARVIS")
            self.orb_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(self.orb_label)

        self.state_label = QLabel("STANDBY")
        self.state_label.setAlignment(Qt.AlignCenter)
        self.state_label.setStyleSheet(
            "font-size: 20px; font-weight: bold; padding: 6px; border-radius: 6px;"
        )
        layout.addWidget(self.state_label)

        self.wake_label = QLabel("Wake word: -")
        self.wake_label.setStyleSheet("color: #5b6270;")
        layout.addWidget(self.wake_label)

        group = QGroupBox("Status")
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(14, 12, 14, 12)

        self.mic_label = QLabel("Microphone: checking...")
        self.command_label = QLabel("Last command: -")
        self.action_label = QLabel("Last action: -")
        for label in (self.mic_label, self.command_label, self.action_label):
            label.setStyleSheet("color: #333a45;")
            label.setWordWrap(True)
            group_layout.addWidget(label)
        layout.addWidget(group)

        buttons = QHBoxLayout()
        self.start_button = QPushButton("Start listening")
        self.stop_button = QPushButton("Stop listening")
        self.stop_button.setEnabled(False)
        settings_button = QPushButton("Settings")
        exit_button = QPushButton("Exit")
        self.start_button.clicked.connect(self.startRequested)
        self.stop_button.clicked.connect(self.stopRequested)
        settings_button.clicked.connect(self.settingsRequested)
        exit_button.clicked.connect(self._on_exit)
        for button in (self.start_button, self.stop_button, settings_button, exit_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)

        self.choices_label = QLabel("")
        self.choices_label.setWordWrap(True)
        self.choices_label.setStyleSheet("color: #8a5a00;")
        layout.addWidget(self.choices_label)

        self.choice_buttons = QHBoxLayout()
        layout.addLayout(self.choice_buttons)
        self._choice_buttons: List[QPushButton] = []

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(400)
        self.log_view.setFixedHeight(140)
        layout.addWidget(self.log_view)

    def _build_tray(self) -> None:
        icon = build_icon()
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip("JARVIS - voice assistant")

        show_action = QAction("Show JARVIS", self)
        show_action.triggered.connect(self.showNormal)
        hide_action = QAction("Hide to tray", self)
        hide_action.triggered.connect(self.hide)
        start_action = QAction("Start listening", self)
        start_action.triggered.connect(self.startRequested)
        stop_action = QAction("Stop listening", self)
        stop_action.triggered.connect(self.stopRequested)
        exit_action = QAction("Exit JARVIS", self)
        exit_action.triggered.connect(self._on_exit)

        history_action = QAction("Task history", self)
        history_action.triggered.connect(self._on_show_history)
        diagnostics_action = QAction("Check my JARVIS", self)
        diagnostics_action.triggered.connect(self._on_show_diagnostics)
        resource_action = QAction("Low resource mode", self)
        resource_action.triggered.connect(self._on_toggle_resource)
        startup_action = QAction("Launch at Windows Startup", self)
        startup_action.setCheckable(True)
        startup_action.setChecked(bool((self.config.get("ui") or {}).get("startup", False)))
        startup_action.triggered.connect(self._on_toggle_startup)

        menu = self._build_menu(
            show_action, hide_action, start_action, stop_action,
            history_action, diagnostics_action, resource_action, startup_action, exit_action,
        )
        self._startup_action = startup_action
        self._resource_action = resource_action
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        try:
            self._tray.show()
        except Exception as exc:  # pragma: no cover - tray unsupported
            log.warning("system tray unavailable: %s", exc)

    def _build_menu(self, *actions: QAction) -> object:
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        for action in actions:
            menu.addAction(action)
        return menu

    def _on_show_history(self) -> None:
        if self._app is None:
            return
        self._app.show_task_history()

    def _on_show_diagnostics(self) -> None:
        if self._app is None:
            return
        self._app.show_diagnostics()

    def _on_toggle_resource(self) -> None:
        if self._app is None:
            return
        enabled = not bool((self.config.get("ui") or {}).get("low_resource", False))
        self._app.set_low_resource(enabled)
        if self._resource_action is not None:
            self._resource_action.setChecked(enabled)
        self.append_log("Low resource mode " + ("on" if enabled else "off"))

    def _on_toggle_startup(self) -> None:
        if self._app is None:
            return
        enabled = bool(self._startup_action.isChecked())
        try:
            self._app.toggle_startup(enabled)
        except Exception as exc:  # pragma: no cover - Windows registry
            self.append_log(f"Could not change the startup setting: {exc}")
        self.append_log("Startup setting " + ("enabled" if enabled else "disabled"))

    def _on_tray_activated(self, reason: int) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.showNormal()
            self.raise_()

    # -- state -------------------------------------------------------------

    def set_state(self, state: str, **extra: object) -> None:
        color = STATE_COLORS.get(state, "#8a8f98")
        self.state_label.setText(state)
        self.state_label.setStyleSheet(
            f"font-size: 20px; font-weight: bold; padding: 6px; "
            f"border-radius: 6px; background: {color}; color: white;"
        )
        self.start_button.setEnabled(state == "STANDBY")
        self.stop_button.setEnabled(state != "STANDBY")
        self.set_orb_state(state)

    def set_mic_status(self, text: str, color: str = "#2e9e5b") -> None:
        self.mic_label.setText(f"Microphone: {text}")
        self.mic_label.setStyleSheet(f"color: {color};")

    def set_command(self, text: str) -> None:
        self.command_label.setText(f"Last command: {text}")

    def set_action(self, text: str, ok: bool = True) -> None:
        self.action_label.setText(f"Last action: {text}")
        self.action_label.setStyleSheet("color: #2e9e5b;" if ok else "color: #c0392b;")

    def append_log(self, message: str) -> None:
        self.log_view.append(message)

    def set_wake_word(self, text: str) -> None:
        self.wake_label.setText(f"Wake word: {text}")

    def show_choices(self, result: object) -> None:
        """Render disambiguation buttons for a multi-match result."""
        self._clear_choice_buttons()
        choices = getattr(result, "choices", []) or []
        payload = getattr(result, "choice_payload", {}) or {}
        if not choices:
            self.choices_label.setText("")
            return
        self.choices_label.setText(
            "Several matches found. Choose one (button or voice):"
        )
        for index, label in enumerate(choices):
            button = QPushButton(label)
            button.clicked.connect(
                lambda _checked=False, i=index: self.choiceMade.emit(
                    str(i + 1), payload
                )
            )
            self._choice_buttons.append(button)
            self.choice_buttons.addWidget(button)

    def _clear_choice_buttons(self) -> None:
        for button in self._choice_buttons:
            self.choice_buttons.removeWidget(button)
            button.deleteLater()
        self._choice_buttons.clear()
        self.choices_label.setText("")

    # -- window behaviour ---------------------------------------------------

    def _on_exit(self) -> None:
        self._allow_quit = True
        self.exitRequested.emit()

    # -- orb ---------------------------------------------------------------

    def set_orb_state(self, state: str) -> None:
        """Map a voice state onto the orb state, degrading gracefully."""
        if self.orb is None:
            return
        mapping = {
            "STANDBY": "standby", "LISTENING": "listening", "PROCESSING": "processing",
            "SPEAKING": "speaking", "ERROR": "error",
        }
        try:
            from orb import OrbState

            self.orb.set_state(OrbState(mapping.get(state, "standby")))
        except Exception as exc:  # pragma: no cover - Qt state mapping
            log.debug("orb state update skipped: %s", exc)

    def set_low_resource(self, enabled: bool) -> None:
        if self.orb is not None:
            try:
                self.orb.set_low_resource(bool(enabled))
            except Exception as exc:  # pragma: no cover
                log.debug("low resource mode not applied: %s", exc)

    def set_compact(self, enabled: bool) -> None:
        if self.orb is not None:
            try:
                self.orb.set_compact(bool(enabled))
                self.resize(420 if enabled else 520, 560)
            except Exception as exc:  # pragma: no cover
                log.debug("compact mode not applied: %s", exc)

    # -- dialogs -----------------------------------------------------------

    def show_task_history(self, summary: str) -> None:
        from PySide6.QtWidgets import QDialog, QPlainTextEdit

        dialog = QDialog(self)
        dialog.setWindowTitle("Task history")
        dialog.resize(520, 420)
        view = QPlainTextEdit(summary or "No tasks recorded yet.")
        view.setReadOnly(True)
        layout = QVBoxLayout(dialog)
        layout.addWidget(view)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def show_diagnostics(self, report) -> None:
        from PySide6.QtWidgets import QDialog, QPlainTextEdit

        dialog = QDialog(self)
        dialog.setWindowTitle("JARVIS self-diagnostics")
        dialog.resize(620, 480)
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setPlainText("\n".join(report.lines()) + "\n\n" + report.summary())
        layout = QVBoxLayout(dialog)
        layout.addWidget(view)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def run_first_run_wizard(self, app) -> None:
        """Ask for the microphone, the Gemini key and the permissions."""
        from PySide6.QtWidgets import (
            QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
            QMessageBox, QVBoxLayout, QLabel,
        )

        if bool((self.config.get("ui") or {}).get("first_run_complete")):
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Welcome to JARVIS")
        dialog.resize(560, 420)
        form = QFormLayout(dialog)

        intro = QLabel(
            "Let's set up JARVIS. Your Gemini key stays on this PC and is never "
            "shared - it is stored in your user profile, outside the app folder."
        )
        intro.setWordWrap(True)
        form.addRow(intro)

        mic_box = QCheckBox("I tested my microphone (say 'Hey JARVIS')")
        mic_box.setChecked(bool((self.config.get("speech") or {}).get("microphone", {}).get("tested", False)))
        form.addRow("Microphone", mic_box)

        key_edit = QLineEdit()
        key_edit.setEchoMode(QLineEdit.Password)
        key_edit.setPlaceholderText("AIza...")
        form.addRow("Gemini API key", key_edit)

        startup_box = QCheckBox("Launch JARVIS when Windows starts")
        form.addRow("Startup", startup_box)

        low_box = QCheckBox("Start in low resource mode")
        low_box.setChecked(bool((self.config.get("ui") or {}).get("low_resource", False)))
        form.addRow("Performance", low_box)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() != QDialog.Accepted:
            self.append_log("First-run setup skipped. Use Settings later.")
            return

        if key_edit.text().strip():
            key_path = Path.home() / ".jarvis" / "gemini_key.txt"
            try:
                key_path.parent.mkdir(parents=True, exist_ok=True)
                key_path.write_text(key_edit.text().strip(), encoding="utf-8")
                os.chmod(str(key_path), 0o600)
                self.append_log(f"Gemini key stored at {key_path}")
            except OSError as exc:
                QMessageBox.warning(self, "JARVIS", f"Could not store the API key: {exc}")

        ui_cfg = dict(self.config.get("ui") or {})
        ui_cfg["first_run_complete"] = True
        ui_cfg["low_resource"] = low_box.isChecked()
        self.config["ui"] = ui_cfg
        speech_cfg = dict(self.config.get("speech") or {})
        microphone = dict(speech_cfg.get("microphone") or {})
        microphone["tested"] = mic_box.isChecked()
        speech_cfg["microphone"] = microphone
        self.config["speech"] = speech_cfg

        self.append_log("First-run setup saved.")
        if startup_box.isChecked():
            try:
                app.toggle_startup(True)
                self.append_log("JARVIS will launch at Windows startup.")
            except Exception as exc:  # pragma: no cover - Windows registry
                self.append_log(f"Startup setting could not be saved: {exc}")

        try:
            self.settings_requested_flag = True
            self.settingsRequested.emit()
        except Exception:  # pragma: no cover - signal wiring
            pass

    def closeEvent(self, event: object) -> None:  # type: ignore[override]
        if self._allow_quit or not self._tray or not QSystemTrayIcon.isSystemTrayAvailable():
            super().closeEvent(event)  # type: ignore[misc]
            return
        event.ignore()  # type: ignore[attr-defined]
        self.hide()
        if self._tray:
            self._tray.showMessage(
                "JARVIS is still running",
                "Use the tray menu to show JARVIS or to exit.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )


__all__ = ["MainWindow", "SettingsDialog", "build_icon", "STATE_COLORS"]
