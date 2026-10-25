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

STATE_COLORS: Dict[str, str] = {
    "STANDBY": "#8a8f98",
    "LISTENING": "#2f7fd4",
    "PROCESSING": "#e08a1e",
    "SPEAKING": "#2e9e5b",
    "ERROR": "#c0392b",
}

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
GENERATED_DIR = os.path.join(ASSETS_DIR, "generated")
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

        browser = dict(config.get("browser", {}) or {})
        browser["default"] = self.browser.currentText()
        browser["search_url"] = self.search_url.text().strip() or browser.get(
            "search_url", "https://www.google.com/search?q={query}"
        )
        config["browser"] = browser

        try:
            with open("config.json", "w", encoding="utf-8") as handle:
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

        self._tray.setContextMenu(
            self._build_menu(show_action, hide_action, start_action, stop_action, exit_action)
        )
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
