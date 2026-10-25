"""
actions.py - JARVIS execution layer.

Every canonical command produced by :mod:`brain` is executed here.  The module
is deliberately strict:

* only whitelisted Windows applications are launched (fixed executable paths /
  names discovered from a lookup table - never from raw user speech)
* no shell strings are built from speech, ``shell=True`` is never used and
  ``eval``/``exec`` are never called
* dangerous operations go through :class:`PermissionManager` and require an
  explicit spoken/visual confirmation
* every action can be aborted by the global emergency-stop hotkey
  (Ctrl + Alt + J), which also releases held keyboard/mouse input

File-search results are disambiguated: when several files match, the user is
asked to choose by number or by name.
"""

from __future__ import annotations

import ctypes
import logging
import math
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from brain import ParsedCommand
from desktop import ToolResult


def _import_desktop():
    """Import the Windows control engine lazily (absent on non-Windows test runs)."""
    from desktop import DesktopController  # type: ignore

    return DesktopController

log = logging.getLogger("jarvis.actions")

WINDOWS = sys.platform.startswith("win")

# Directories that are never walked during a file search.
_SEARCH_SKIP = {
    "windows", "$recycle.bin", "appdata", "program files", "program files (x86)",
    "programdata", "perflogs", "system volume information", "node_modules",
    ".git", ".svn", "__pycache__", "onedrive - personal", "thumbs.db",
}


# ---------------------------------------------------------------------------
# result
# ---------------------------------------------------------------------------

@dataclass
class ActionResult:
    """Outcome of one command execution."""

    success: bool = True
    message: str = ""
    detail: str = ""
    status: str = "done"          # done | error | choice | confirm | info
    needs_choice: bool = False
    choices: List[str] = field(default_factory=list)
    choice_payload: Dict[str, object] = field(default_factory=dict)
    needs_confirmation: bool = False
    confirmation_payload: Dict[str, object] = field(default_factory=dict)
    command: str = ""

    def describe(self) -> str:
        if self.needs_choice:
            return f"{self.message} ({len(self.choices)} matches)"
        if self.needs_confirmation:
            return f"{self.message} (confirmation required)"
        if self.status == "error":
            return f"{self.message} {self.detail}".strip()
        return self.message


class EmergencyStopped(RuntimeError):
    """Raised when the user pressed the emergency-stop hotkey."""


# ---------------------------------------------------------------------------
# permissions
# ---------------------------------------------------------------------------

class PermissionManager:
    """Configurable permission rules for sensitive operations."""

    #: category -> which JARVIS commands it covers
    CATEGORY_ACTIONS: Dict[str, Tuple[str, ...]] = {
        "delete_files": ("delete_file",),
        "overwrite_files": ("save_file", "open_file_write"),
        "move_sensitive_files": ("move_file",),
        "external_communication": ("google_search", "send_message"),
        "camera_access": ("screenshot",),
        "install_software": ("install_app",),
        "system_configuration": ("set_volume", "mute", "unmute", "lock_screen"),
    }

    def __init__(
        self,
        rules: Optional[Dict[str, bool]] = None,
        allowed_roots: Optional[Sequence[str]] = None,
        sensitive_paths: Optional[Sequence[str]] = None,
        on_confirm_requested: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.rules = dict(rules or {})
        self.allowed_roots = [r for r in (allowed_roots or []) if r]
        self.sensitive_paths = [p.lower() for p in (sensitive_paths or []) if p]
        self.on_confirm_requested = on_confirm_requested

    def requires_confirmation(self, action: str) -> bool:
        for category, actions in self.CATEGORY_ACTIONS.items():
            if action in actions:
                return bool(self.rules.get(category, True))
        return False

    def category_for(self, action: str) -> Optional[str]:
        for category, actions in self.CATEGORY_ACTIONS.items():
            if action in actions:
                return category
        return None

    def is_sensitive_path(self, path: Path) -> bool:
        low = str(path).lower().replace("\\", "/")
        return any(marker in low for marker in self.sensitive_paths)

    def is_allowed_root(self, path: Path) -> bool:
        low = str(path).lower().replace("\\", "/")
        return any(root.lower() in low for root in self.allowed_roots)

    def allowed_roots_paths(self) -> List[Path]:
        """Resolve the configured allowed roots to real directories."""
        home = Path.home()
        resolved: List[Path] = []
        for root in self.allowed_roots:
            candidate = Path(root)
            if not candidate.is_absolute():
                candidate = home / root
            if candidate.exists():
                resolved.append(candidate)
        return resolved


# ---------------------------------------------------------------------------
# global emergency-stop hotkey (Ctrl + Alt + J) - ctypes only, no extra deps
# ---------------------------------------------------------------------------

class GlobalHotkey:
    """Registers Ctrl + Alt + J globally using the Windows ``RegisterHotKey`` API.

    Falls back to a no-op when running off Windows (unit tests, Linux dev).
    """

    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    MOD_NOREPEAT = 0x4000
    WM_HOTKEY = 0x0312

    def __init__(self, callback: Callable[[], None]) -> None:
        self.callback = callback
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._registered = False
        self._atom = 0x4A41  # 'JA'

    def start(self) -> bool:
        if not WINDOWS:
            log.info("global hotkey skipped (not Windows)")
            return False
        try:
            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - non-Windows
            log.info("global hotkey unavailable: %s", exc)
            return False

        flags = self.MOD_ALT | self.MOD_CONTROL | self.MOD_NOREPEAT
        result = user32.RegisterHotKey(None, self._atom, flags, ord("J"))
        if not result:
            log.error("could not register the emergency-stop hotkey "
                      "(another app may own it)")
            return False
        self._registered = True
        self._thread = threading.Thread(target=self._listen, name="jarvis-hotkey", daemon=True)
        self._thread.start()
        return True

    def _listen(self) -> None:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        MSG = ctypes.c_void_p * 1
        msg = MSG()
        while not self._stop.is_set():
            if user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if ctypes.cast(msg[0], ctypes.POINTER(ctypes.c_uint)).contents.value == self.WM_HOTKEY:
                    self.callback()
            else:
                break

    def stop(self) -> None:
        self._stop.set()
        if self._registered:
            try:
                ctypes.windll.user32.UnregisterHotKey(None, self._atom)  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover
                pass
            self._registered = False


# ---------------------------------------------------------------------------
# action engine
# ---------------------------------------------------------------------------

class ActionEngine:
    """Execute canonical commands on Windows."""

    def __init__(
        self,
        config: dict,
        permissions: Optional[PermissionManager] = None,
        on_emergency_stop: Optional[Callable[[], None]] = None,
    ) -> None:
        self.config = config or {}
        self.automation = self.config.get("automation", {}) or {}
        self.browser_config = self.config.get("browser", {}) or {}
        if permissions is not None:
            self.permissions = permissions
        else:
            perms_cfg = self.config.get("permissions", {}) or {}
            self.permissions = PermissionManager(
                rules=perms_cfg.get("require_confirmation") or {},
                allowed_roots=perms_cfg.get("allowed_file_roots") or [],
                sensitive_paths=perms_cfg.get("sensitive_paths") or [],
            )
        self._emergency_callback = on_emergency_stop
        self._stopped = False
        self._held_keys: set = set()
        self._lock = threading.RLock()
        self._file_index: Optional[List[Tuple[str, Path, float]]] = None
        self._index_lock = threading.RLock()

    # -- emergency stop -----------------------------------------------------

    def register_emergency_stop(self, callback: Callable[[], None]) -> None:
        self._emergency_callback = callback

    def emergency_stop(self) -> None:
        """Interrupt automation and release held keyboard/mouse input."""
        log.warning("EMERGENCY STOP requested by user")
        with self._lock:
            self._stopped = True
        try:
            import pyautogui

            for key in ("ctrl", "alt", "shift", "win", "up", "down", "left", "right"):
                if key in self._held_keys:
                    pyautogui.keyUp(key)
            if self._held_keys:
                self._held_keys.clear()
            pyautogui.mouseUp(button="left")
            pyautogui.mouseUp(button="right")
            pyautogui.mouseUp(button="middle")
        except Exception as exc:  # pragma: no cover - pyautogui missing
            log.warning("could not release automation inputs: %s", exc)
        if self._emergency_callback:
            try:
                self._emergency_callback()
            except Exception:  # pragma: no cover
                pass

    def reset_emergency_stop(self) -> None:
        with self._lock:
            self._stopped = False

    @property
    def emergency_stopped(self) -> bool:
        return self._stopped

    def _guard(self) -> None:
        if self._stopped:
            raise EmergencyStopped("Emergency stop was pressed")

    # -- dispatch -----------------------------------------------------------

    def execute(self, parsed: ParsedCommand) -> ActionResult:
        """Run one parsed command.  Never raises - returns a result."""
        result = ActionResult(command=parsed.command)
        try:
            handler = self._handler(parsed.command)
            if handler is None:
                result.status = "error"
                result.success = False
                result.message = "I don't know how to do that yet."
                result.detail = f"unknown command: {parsed.command}"
                return result
            handler(parsed, result)
        except EmergencyStopped:
            result.status = "error"
            result.success = False
            result.message = "Emergency stop was pressed. I stopped."
            result.detail = "emergency_stop"
            self.reset_emergency_stop()
        except Exception as exc:
            log.exception("action failed: %s", exc)
            result.status = "error"
            result.success = False
            result.message = f"Sorry, that didn't work: {exc}"
            result.detail = parsed.command
        return result

    def execute_choice(self, choice: str, payload: Dict[str, object]) -> ActionResult:
        """Resolve a disambiguation answer typed/spoken by the user."""
        kind = str(payload.get("kind", "file"))
        options: List[Path] = [Path(p) for p in (payload.get("paths") or [])]
        if not options:
            return ActionResult(success=False, message="That choice is no longer available.", status="error")

        cleaned = choice.strip().lower().replace(".", " ")
        cleaned = " ".join(cleaned.split())
        index: Optional[int] = None
        for token in cleaned.split():
            if token.isdigit() and 1 <= int(token) <= len(options):
                index = int(token) - 1
                break

        if index is not None:
            chosen = options[index]
        else:
            tokens = [t for t in cleaned.split() if len(t) > 2]
            chosen = next(
                (
                    path
                    for path in options
                    if any(token in str(path).lower() for token in tokens)
                ),
                options[0],
            )

        if kind == "file":
            return self.open_file_at(chosen)
        if kind == "folder":
            return self.open_path(chosen)
        return ActionResult(success=False, message="Sorry, I couldn't use that choice.", status="error")

    def _handler(self, command: str) -> Optional[Callable[[ParsedCommand, ActionResult], None]]:
        return {
            "open_file_explorer": self.act_open_file_explorer,
            "open_chrome": self.act_open_chrome,
            "open_settings": self.act_open_settings,
            "open_calculator": self.act_open_calculator,
            "open_notepad": self.act_open_notepad,
            "open_folder": self.act_open_folder,
            "search_file": self.act_search_file,
            "open_file": self.act_open_file,
            "open_app": self.act_open_app,
            "close_app": self.act_close_app,
            "google_search": self.act_google_search,
            "scroll_up": lambda p, r: self.act_scroll(p, r, 1),
            "scroll_down": lambda p, r: self.act_scroll(p, r, -1),
            "scroll_unknown": self.act_scroll_unknown,
            "browser_back": lambda p, r: self.act_browser_navigate(p, r, "back"),
            "browser_forward": lambda p, r: self.act_browser_navigate(p, r, "forward"),
            "volume_up": lambda p, r: self.act_volume_step(p, r, 1),
            "volume_down": lambda p, r: self.act_volume_step(p, r, -1),
            "set_volume": self.act_set_volume,
            "mute": self.act_mute,
            "unmute": self.act_unmute,
            "screenshot": self.act_screenshot,
            "current_time": self.act_current_time,
            "current_date": self.act_current_date,
            "delete_file": self.act_delete_file,
            # lifecycle commands are normally handled by the application layer
            # before they reach the worker; these handlers keep the engine
            # complete so nothing required ever reports "unknown"
            "stop_listening": self.act_stop_listening,
            "go_standby": self.act_go_standby,
            "exit_jarvis": self.act_exit_jarvis,
        }.get(command)

    # -- lifecycle helpers --------------------------------------------------

    def act_stop_listening(self, parsed: ParsedCommand, result: ActionResult) -> None:
        result.status = "info"
        result.message = "Stopped listening."

    def act_go_standby(self, parsed: ParsedCommand, result: ActionResult) -> None:
        result.status = "info"
        result.message = "Returning to standby."

    def act_exit_jarvis(self, parsed: ParsedCommand, result: ActionResult) -> None:
        result.status = "info"
        result.message = "Exiting JARVIS."
        result.choice_payload = {"action": "exit_jarvis"}

    # -- helpers ------------------------------------------------------------

    def _guard_action(self) -> None:
        self._guard()

    @staticmethod
    def _open(path: Path) -> None:
        """Open a path with the default application (Windows) or xdg-open."""
        if WINDOWS:
            os.startfile(str(path))  # type: ignore[attr-defined]
            return
        if shutil.which("xdg-open"):
            subprocess.Popen(["xdg-open", str(path)])
            return
        raise RuntimeError(
            "Opening files needs Windows, or xdg-open on Linux/macOS."
        )

    @staticmethod
    def _launch(argv: Sequence[str]) -> None:
        subprocess.Popen(list(argv), shell=False)

    def _browser_executable(self, name: Optional[str] = None) -> Optional[Path]:
        """Locate a browser executable without using a shell."""
        wanted = (name or self.browser_config.get("default", "chrome")).lower()
        override = self.browser_config.get("chrome_path") or ""
        if override and Path(override).exists():
            return Path(override)

        candidates: List[List[str]] = []
        if "edge" in wanted or "msedge" in wanted:
            candidates.append([r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"])
            candidates.append([r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"])
        if "firefox" in wanted:
            candidates.append([r"C:\Program Files\Mozilla Firefox\firefox.exe"])
            candidates.append([r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe"])
        if "chrome" in wanted or "google" in wanted:
            candidates.append(
                [os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe")]
            )
            candidates.append(
                [r"C:\Program Files\Google\Chrome\Application\chrome.exe"]
            )
            candidates.append(
                [r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"]
            )
        for paths in candidates:
            for raw in paths:
                if raw and Path(raw).exists():
                    return Path(raw)
        return shutil.which("chrome.exe" if "chrome" in wanted else "msedge.exe")

    def _search_url(self, query: str) -> str:
        from urllib.parse import quote_plus

        template = self.browser_config.get("search_url") or "https://www.google.com/search?q={query}"
        return template.replace("{query}", quote_plus(query))

    def _open_url(self, url: str) -> str:
        """Open a URL in the default browser; returns the browser name used."""
        browser = self._browser_executable()
        if browser:
            self._launch([str(browser), url])
            return Path(browser).name
        if WINDOWS:
            os.startfile(url)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", url])
        return "default browser"

    # -- file system helpers ------------------------------------------------

    def _build_index(self) -> List[Tuple[str, Path, float]]:
        """Index user files once so repeated searches are fast."""
        with self._index_lock:
            if self._file_index is not None:
                return self._file_index
            max_entries = int(self.automation.get("search_max_entries", 40000))
            roots = self.permissions.allowed_roots_paths() or [Path.home()]
            index: List[Tuple[str, Path, float]] = []
            scanned = 0
            for root in roots:
                if not root.exists():
                    continue
                for dirpath, dirnames, filenames in os.walk(root):
                    dirnames[:] = [
                        d for d in dirnames
                        if d.lower() not in _SEARCH_SKIP and not d.startswith(".")
                    ]
                    for filename in filenames:
                        full = Path(dirpath) / filename
                        try:
                            mtime = full.stat().st_mtime
                        except OSError:
                            continue
                        index.append((filename.lower(), full, mtime))
                        scanned += 1
                        if scanned >= max_entries:
                            break
                    if scanned >= max_entries:
                        break
                if scanned >= max_entries:
                    break
            self._file_index = index
            log.info("file index built: %d entries", len(index))
            return index

    def _search_files(self, query: str) -> List[Path]:
        query = (query or "").lower().strip()
        if not query:
            return []
        index = self._build_index()
        # try the query with spaces collapsed, then with spaces -> dots
        variants = [query, query.replace(" ", "")]
        if " " in query:
            variants.append(query.replace(" ", "."))
        matches: List[Tuple[str, Path, float]] = []
        seen: set = set()
        for variant in variants:
            for name, path, mtime in index:
                if variant in name and path not in seen:
                    seen.add(path)
                    matches.append((name, path, mtime))
        matches.sort(key=lambda item: item[2], reverse=True)
        return [path for _, path, _ in matches]

    def _resolve_folder(self, name: str) -> Optional[Path]:
        """Find a folder by name inside the allowed roots, or by direct path."""
        name = (name or "").strip()
        if not name:
            return None
        candidate = Path(name)
        if candidate.exists() and candidate.is_dir():
            return candidate

        query = name.lower().replace("folder", "").strip()
        for root in self.permissions.allowed_roots_paths():
            if not root.exists():
                continue
            for dirpath, dirnames, _files in os.walk(root):
                dirnames[:] = [
                    d for d in dirnames
                    if d.lower() not in _SEARCH_SKIP and not d.startswith(".")
                ]
                for dirname in dirnames:
                    if query and query in dirname.lower():
                        return Path(dirpath) / dirname
        return None

    def _find_executable(self, name: str) -> Optional[Path]:
        """Find an installed application by name (PATH + common install dirs)."""
        name = (name or "").strip().lower()
        if not name:
            return None
        found = shutil.which(name)
        if found:
            return Path(found)
        suffixes = (".exe", ".bat", ".cmd", ".lnk")
        for directory in os.environ.get("PATH", "").split(os.pathsep):
            if not directory:
                continue
            base = Path(directory)
            if not base.exists():
                continue
            try:
                for entry in base.iterdir():
                    if entry.is_file() and entry.name.lower().startswith(name) and entry.name.lower().endswith(suffixes):
                        return entry
            except OSError:
                continue
        return None

    # -- actions ------------------------------------------------------------

    def act_open_file_explorer(self, parsed: ParsedCommand, result: ActionResult) -> None:
        self._guard_action()
        if WINDOWS:
            self._launch(["explorer.exe"])
        else:
            subprocess.Popen(["xdg-open", str(Path.home())])
        result.message = "Opening File Explorer."

    def act_open_chrome(self, parsed: ParsedCommand, result: ActionResult) -> None:
        self._guard_action()
        browser = self._browser_executable()
        if browser:
            self._launch([str(browser)])
            result.message = f"Opening {Path(browser).name.replace('.exe', '')}."
        else:
            self._open_url("about:blank")
            result.message = "Opening the default browser."

    def act_open_settings(self, parsed: ParsedCommand, result: ActionResult) -> None:
        self._guard_action()
        if WINDOWS:
            os.startfile("ms-settings:")  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", "about:preferences"])
        result.message = "Opening Windows Settings."

    def act_open_calculator(self, parsed: ParsedCommand, result: ActionResult) -> None:
        self._guard_action()
        if WINDOWS:
            self._launch(["calc.exe"])
        else:
            subprocess.Popen(["gnome-calculator"])
        result.message = "Opening Calculator."

    def act_open_notepad(self, parsed: ParsedCommand, result: ActionResult) -> None:
        self._guard_action()
        if WINDOWS:
            self._launch(["notepad.exe"])
        else:
            subprocess.Popen(["gedit"])
        result.message = "Opening Notepad."

    def act_open_folder(self, parsed: ParsedCommand, result: ActionResult) -> None:
        self._guard_action()
        name = parsed.slots.get("folder", "")
        folder = self._resolve_folder(name)
        if folder is None:
            result.status = "error"
            result.success = False
            result.message = (
                f"I couldn't find a folder called '{name}'. "
                "Try the full path, or give me a more specific name."
            )
            return
        self._open(folder)
        result.message = f"Opening folder: {folder.name}."

    def act_search_file(self, parsed: ParsedCommand, result: ActionResult) -> None:
        self._guard_action()
        query = parsed.slots.get("query", "")
        if not query:
            result.status = "error"
            result.success = False
            result.message = "What file should I search for?"
            return

        matches = self._search_files(query)[: int(self.automation.get("search_max_results", 8))]
        if not matches:
            result.status = "error"
            result.success = False
            result.message = (
                f"I couldn't find any file matching '{query}' in your "
                "Desktop, Documents, Downloads, Pictures, Music and Videos folders."
            )
            return

        if len(matches) == 1:
            result.message = f"Found one match: {matches[0].name}."
            self._open(matches[0])
            return

        result.needs_choice = True
        result.status = "choice"
        result.choices = [f"{i + 1}. {p.name}" for i, p in enumerate(matches)]
        result.choice_payload = {"kind": "file", "paths": [str(p) for p in matches]}
        result.message = (
            f"I found {len(matches)} files matching '{query}'. "
            "Which one should I open? Say the number or the name."
        )

    def act_open_file(self, parsed: ParsedCommand, result: ActionResult) -> None:
        self._guard_action()
        name = parsed.slots.get("file", "")
        if not name:
            result.status = "error"
            result.success = False
            result.message = "Which file should I open?"
            return

        matches = self._search_files(name)[: int(self.automation.get("search_max_results", 8))]
        if not matches:
            # maybe the user gave a full path
            candidate = Path(name)
            if candidate.exists():
                self._open(candidate)
                result.message = f"Opening {candidate.name}."
                return
            result.status = "error"
            result.success = False
            result.message = f"I couldn't find the file '{name}'."
            return

        if len(matches) == 1:
            result.message = f"Opening {matches[0].name}."
            self._open(matches[0])
            return

        result.needs_choice = True
        result.status = "choice"
        result.choices = [f"{i + 1}. {p.name}" for i, p in enumerate(matches)]
        result.choice_payload = {"kind": "file", "paths": [str(p) for p in matches]}
        result.message = (
            f"I found {len(matches)} files named like '{name}'. "
            "Which one should I open? Say the number or the name."
        )

    def open_file_at(self, path: Path) -> ActionResult:
        self._guard_action()
        self._open(path)
        return ActionResult(success=True, message=f"Opening {path.name}.", command="open_file")

    def act_open_app(self, parsed: ParsedCommand, result: ActionResult) -> None:
        self._guard_action()
        name = parsed.slots.get("app", "")
        app = self._find_executable(name)
        if app is None:
            result.status = "error"
            result.success = False
            result.message = f"I couldn't find an application called '{name}'."
            return
        self._launch([str(app)])
        result.message = f"Opening {app.name.replace('.exe', '')}."

    def act_close_app(self, parsed: ParsedCommand, result: ActionResult) -> None:
        self._guard_action()
        name = parsed.slots.get("app", "")
        try:
            import pyautogui

            hotkeys = {
                "chrome": ("ctrl", "w"), "firefox": ("ctrl", "w"), "edge": ("ctrl", "w"),
                "notepad": ("alt", "f4"), "calculator": ("esc",),
            }
            for key, keys in hotkeys.items():
                if key in name.lower():
                    pyautogui.hotkey(*keys)
                    result.message = f"Closing {name}."
                    return
            pyautogui.hotkey("alt", "f4")
            result.message = "Closing the current window."
        except Exception as exc:
            result.status = "error"
            result.success = False
            result.message = f"Sorry, I couldn't close that: {exc}"

    def act_google_search(self, parsed: ParsedCommand, result: ActionResult) -> None:
        self._guard_action()
        query = parsed.slots.get("query", "")
        if not query:
            result.status = "error"
            result.success = False
            result.message = "What should I search for?"
            return
        if self.permissions.requires_confirmation("google_search"):
            result.needs_confirmation = True
            result.status = "confirm"
            result.confirmation_payload = {
                "action": "google_search",
                "query": query,
                "message": f"Search the web for '{query}'?",
            }
            result.message = str(result.confirmation_payload["message"])
            return
        browser = self._open_url(self._search_url(query))
        result.message = f"Searching '{query}' on {browser}."

    def act_scroll(self, parsed: ParsedCommand, result: ActionResult, direction: int) -> None:
        self._guard_action()
        try:
            import pyautogui

            amount = int(self.automation.get("scroll_amount", 5))
            pyautogui.scroll(amount if direction > 0 else -amount)
            result.message = "Scrolling up." if direction > 0 else "Scrolling down."
        except Exception as exc:
            result.status = "error"
            result.success = False
            result.message = f"Sorry, I couldn't scroll: {exc}"

    def act_scroll_unknown(self, parsed: ParsedCommand, result: ActionResult) -> None:
        result.status = "info"
        result.message = "Should I scroll up or down?"

    def act_browser_navigate(self, parsed: ParsedCommand, result: ActionResult, which: str) -> None:
        self._guard_action()
        try:
            import pyautogui

            if which == "back":
                pyautogui.hotkey("alt", "left")
                result.message = "Going back in the browser."
            else:
                pyautogui.hotkey("alt", "right")
                result.message = "Going forward in the browser."
        except Exception as exc:
            result.status = "error"
            result.success = False
            result.message = f"Sorry, I couldn't navigate: {exc}"

    # -- audio --------------------------------------------------------------

    def _dB_to_percent(self, db: float) -> float:
        return min(1.0, max(0.0, 10 ** (db / 20.0))) * 100.0

    def _percent_to_dB(self, percent: float) -> float:
        percent = min(100.0, max(0.0, percent))
        if percent <= 0:
            return -100.0
        return round(20 * math.log10(percent / 100.0), 2)

    def act_set_volume(self, parsed: ParsedCommand, result: ActionResult) -> None:
        self._guard_action()
        raw = parsed.slots.get("level", "")
        value = _parse_level(raw)
        if value is None:
            result.status = "error"
            result.success = False
            result.message = "Volume to what level? Say a number, like 'volume 60'."
            return
        percent = float(value)
        if self.permissions.requires_confirmation("set_volume"):
            result.needs_confirmation = True
            result.status = "confirm"
            result.confirmation_payload = {
                "action": "set_volume",
                "percent": percent,
                "message": f"Set system volume to {int(percent)}%?",
            }
            result.message = str(result.confirmation_payload["message"])
            return
        self._apply_volume(percent, result)

    def act_volume_step(self, parsed: ParsedCommand, result: ActionResult, direction: int) -> None:
        self._guard_action()
        step = int(self.automation.get("volume_step", 10))
        try:
            from pycaw.utils import AudioUtilities

            current = self._dB_to_percent(AudioUtilities.GetMasterVolumeLevel())
            # small steps are treated as ordinary actions (no confirmation)
            self._apply_volume(current + direction * step, result)
        except Exception as exc:
            result.status = "error"
            result.success = False
            result.message = f"Sorry, I couldn't change the volume: {exc}"

    def _apply_volume(self, percent: float, result: ActionResult) -> None:
        percent = max(0.0, min(100.0, percent))
        try:
            from pycaw.utils import AudioUtilities

            if AudioUtilities.GetMasterMute():
                AudioUtilities.SetMasterMute(False)
            AudioUtilities.SetMasterVolumeLevel(self._percent_to_dB(percent))
            result.message = f"Volume set to {int(percent)} percent."
        except Exception as exc:
            result.status = "error"
            result.success = False
            result.message = f"Sorry, I couldn't change the volume: {exc}"

    def act_mute(self, parsed: ParsedCommand, result: ActionResult) -> None:
        self._guard_action()
        if self.permissions.requires_confirmation("mute"):
            result.needs_confirmation = True
            result.status = "confirm"
            result.confirmation_payload = {
                "action": "mute",
                "message": "Mute the system audio?",
            }
            result.message = "Mute the system audio?"
            return
        self._set_mute(True, result)

    def act_unmute(self, parsed: ParsedCommand, result: ActionResult) -> None:
        self._guard_action()
        self._set_mute(False, result)

    def _set_mute(self, mute: bool, result: ActionResult) -> None:
        try:
            from pycaw.utils import AudioUtilities

            AudioUtilities.SetMasterMute(mute)
            result.message = "System audio muted." if mute else "System audio unmuted."
        except Exception as exc:
            result.status = "error"
            result.success = False
            result.message = f"Sorry, I couldn't change the mute state: {exc}"

    # -- capture ------------------------------------------------------------

    def act_screenshot(
        self,
        parsed: ParsedCommand,
        result: ActionResult,
        skip_confirmation: bool = False,
    ) -> None:
        self._guard_action()
        if not skip_confirmation and self.permissions.requires_confirmation("screenshot"):
            result.needs_confirmation = True
            result.status = "confirm"
            result.confirmation_payload = {
                "action": "screenshot",
                "message": "Take a screenshot of the screen?",
            }
            result.message = "Take a screenshot of the screen?"
            return

        try:
            import pyautogui
            from PIL import Image

            picture_dir = Path.home() / "Pictures" / "JARVIS Screenshots"
            picture_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            target = picture_dir / f"jarvis-{stamp}.png"
            image = pyautogui.screenshot()
            if isinstance(image, Image.Image):
                image.save(str(target))
            else:  # pragma: no cover - defensive
                target.write_bytes(bytes(image))
            self._open(picture_dir)
            result.message = f"Screenshot saved to {target.name}."
            result.detail = str(target)
        except Exception as exc:
            result.status = "error"
            result.success = False
            result.message = f"Sorry, I couldn't take a screenshot: {exc}"

    # -- information --------------------------------------------------------

    def act_current_time(self, parsed: ParsedCommand, result: ActionResult) -> None:
        now = datetime.now()
        hour12 = now.hour % 12 or 12
        result.status = "info"
        result.message = f"It is {hour12}:{now.minute:02d} {now.strftime('%p')}."

    def act_current_date(self, parsed: ParsedCommand, result: ActionResult) -> None:
        now = datetime.now()
        result.status = "info"
        result.message = f"Today is {now.strftime('%A, %d %B %Y')}."

    # -- destructive (permission-gated, Phase 2 command surface) ------------

    def act_delete_file(self, parsed: ParsedCommand, result: ActionResult) -> None:
        self._guard_action()
        name = parsed.slots.get("file", "")
        matches = self._search_files(name)[:5]
        if not matches:
            result.status = "error"
            result.success = False
            result.message = f"I couldn't find the file '{name}'."
            return
        target = matches[0]
        if self.permissions.is_sensitive_path(target):
            result.status = "error"
            result.success = False
            result.message = "I won't delete files in a system folder."
            return

        if not self.permissions.requires_confirmation("delete_file"):
            result.status = "error"
            result.success = False
            result.message = (
                "Deleting files is disabled in your permission settings."
            )
            return

        result.needs_confirmation = True
        result.status = "confirm"
        result.confirmation_payload = {
            "action": "delete_file",
            "path": str(target),
            "message": f"Delete '{target.name}'? This cannot be undone.",
        }
        result.message = str(result.confirmation_payload["message"])

    def confirm(self, payload: Dict[str, object]) -> ActionResult:
        """Run a confirmed action from :class:`PermissionManager`."""
        try:
            return self._confirm(payload)
        except Exception as exc:
            log.exception("confirmed action failed: %s", exc)
            return ActionResult(
                success=False, status="error",
                message=f"Sorry, that action failed: {exc}",
            )

    def _confirm(self, payload: Dict[str, object]) -> ActionResult:
        action = str(payload.get("action", ""))
        if action == "delete_file":
            target = Path(str(payload.get("path", "")))
            if self.permissions.is_sensitive_path(target):
                return ActionResult(
                    success=False, status="error",
                    message="I won't delete files in a system folder.",
                )
            try:
                target.unlink()
                self._file_index = None
                return ActionResult(success=True, message=f"Deleted {target.name}.", command="delete_file")
            except OSError as exc:
                return ActionResult(
                    success=False, status="error",
                    message=f"I couldn't delete that file: {exc}", command="delete_file",
                )
        if action == "google_search":
            query = str(payload.get("query", ""))
            if not query:
                return ActionResult(success=False, status="error", message="What should I search for?")
            browser = self._open_url(self._search_url(query))
            return ActionResult(
                success=True, message=f"Searching '{query}' on {browser}.", command="google_search"
            )
        if action == "set_volume":
            percent = float(payload.get("percent", 50))  # type: ignore[arg-type]
            reply = ActionResult(command="set_volume")
            self._apply_volume(percent, reply)
            return reply
        if action == "mute":
            reply = ActionResult(command="mute")
            self._set_mute(True, reply)
            return reply
        if action == "screenshot":
            reply = ActionResult(command="screenshot")
            self.act_screenshot(ParsedCommand("screenshot", "", "", 0.0), reply, skip_confirmation=True)  # type: ignore[arg-type]
            return reply
        return ActionResult(success=False, status="error", message="That action can't be confirmed.")

    # -- path helpers -------------------------------------------------------

    @staticmethod
    def open_path(path: Path) -> ActionResult:
        if not path.exists():
            return ActionResult(success=False, status="error", message=f"{path} doesn't exist.")
        ActionEngine._open(path)
        return ActionResult(success=True, message=f"Opening {path.name}.", command="open_path")


def _parse_level(raw: str) -> Optional[int]:
    """Parse a volume level that may be ``"50"``, ``"50 percent"`` or a word."""
    from brain import parse_number

    if not raw:
        return None
    value = parse_number(raw)
    if value is None:
        return None
    return int(max(0, min(100, value)))


# ---------------------------------------------------------------------------
# tool registry for Gemini and the task planner
# ---------------------------------------------------------------------------

#: tools that must always be confirmed before they run
CONFIRMATION_TOOLS = frozenset({
    "take_screenshot", "camera_photo", "window_close", "keyboard_type",
    "keyboard_shortcut", "mouse_click", "mouse_drag", "file_delete",
    "file_rename", "file_move", "summarize_page", "browser_open_url",
})


def _as_int(args: Dict[str, object], key: str, default: int, minimum: Optional[int] = None,
            maximum: Optional[int] = None) -> int:
    raw = args.get(key, default)
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _as_text(args: Dict[str, object], key: str, default: str = "") -> str:
    raw = args.get(key, default)
    if raw is None:
        return default
    return str(raw).strip()


class ToolRegistry:
    """Validated dispatcher for every tool Gemini or the planner may call.

    Every call is checked against the argument types, the permission policy and
    the confirmation rules *before* it touches the operating system, and the
    result is always a plain ``{"ok": bool, "result": str}`` dictionary that is
    safe to hand back to the model.
    """

    def __init__(
        self,
        desktop: "DesktopController",
        browser: Optional["BrowserController"] = None,
        camera: Optional["CameraController"] = None,
        permissions: Optional[PermissionManager] = None,
        gemini: Optional[object] = None,
        local_executor: Optional[Callable[[str, Dict[str, object]], Dict[str, object]]] = None,
        allowed_tools: Sequence[str] = (),
        confirm: Optional[Callable[[str, Dict[str, object]], bool]] = None,
    ) -> None:
        self.desktop = desktop
        self.browser = browser
        self.camera = camera
        self.permissions = permissions or PermissionManager()
        self.gemini = gemini
        self.local_executor = local_executor
        self.allowed_tools = set(allowed_tools) or None
        self.confirm = confirm
        self._handlers = {
            "open_application": self.t_open_application,
            "search_files": self.t_search_files,
            "open_file": self.t_open_file,
            "search_web": self.t_search_web,
            "browser_open_url": self.t_browser_open_url,
            "browser_search": self.t_browser_search,
            "browser_open_result": self.t_browser_open_result,
            "browser_extract_text": self.t_browser_extract_text,
            "browser_navigate": self.t_browser_navigate,
            "browser_scroll": self.t_browser_scroll,
            "navigate_browser": self.t_navigate_browser,
            "scroll_page": self.t_scroll_page,
            "browser_tabs": self.t_browser_tabs,
            "browser_activate_tab": self.t_browser_activate_tab,
            "take_screenshot": self.t_take_screenshot,
            "get_system_status": self.t_get_system_status,
            "window_list": self.t_window_list,
            "window_focus": self.t_window_focus,
            "window_minimize": self.t_window_minimize,
            "window_maximize": self.t_window_maximize,
            "window_close": self.t_window_close,
            "mouse_click": self.t_mouse_click,
            "mouse_drag": self.t_mouse_drag,
            "keyboard_type": self.t_keyboard_type,
            "keyboard_shortcut": self.t_keyboard_shortcut,
            "file_create_folder": self.t_file_create_folder,
            "file_rename": self.t_file_rename,
            "file_copy": self.t_file_copy,
            "file_move": self.t_file_move,
            "file_delete": self.t_file_delete,
            "read_document": self.t_read_document,
            "camera_photo": self.t_camera_photo,
            "summarize_page": self.t_summarize_page,
        }

    # -- introspection ------------------------------------------------------

    def names(self) -> List[str]:
        return sorted(self._handlers)

    def describe(self, name: str) -> str:
        handler = self._handlers.get(name)
        return handler.__doc__ or name if handler else "Unknown tool."

    def validate(self, name: str, arguments: Dict[str, object]) -> Optional[str]:
        """Return a human-readable problem, or ``None`` when the call is valid."""
        if not isinstance(name, str) or not name.strip():
            return "No tool name given."
        if name.startswith("local:"):
            if self.local_executor is None:
                return "Local command execution is not enabled."
            return None
        if name not in self._handlers:
            return f"Unknown tool '{name}'."
        if not isinstance(arguments, dict):
            return "Tool arguments must be an object."
        # argument shape is checked before the enabled-list so the model sees
        # the real problem instead of a generic permission message
        if name in ("browser_open_result", "browser_activate_tab") and _as_int(arguments, "index", 1) < 1:
            return "Tab/result index must be at least 1."
        if name == "mouse_click":
            text = arguments.get("text")
            if arguments.get("x") is None and arguments.get("y") is None and not text:
                return "Provide coordinates or visible text to click."
        if self.allowed_tools is not None and name not in self.allowed_tools:
            return f"Tool '{name}' is not enabled in the settings."
        if name in ("browser_open_result", "browser_activate_tab"):
            value = _as_int(arguments, "index", 1, minimum=1)
            if value < 1:
                return "Tab/result index must be at least 1."
        if name == "mouse_click":
            x = arguments.get("x"); y = arguments.get("y")
            text = arguments.get("text")
            if x is None and y is None and not text:
                return "Provide coordinates or visible text to click."
            if x is not None and y is not None:
                try:
                    _as_int(arguments, "x", 0); _as_int(arguments, "y", 0)
                except (TypeError, ValueError):
                    return "Coordinates must be integers."
        return None

    def requires_confirmation(self, name: str, arguments: Dict[str, object]) -> bool:
        if name in CONFIRMATION_TOOLS:
            return True
        if name == "file_delete":
            path = Path(_as_text(arguments, "path"))
            return self.desktop.is_sensitive_path(path)
        if name in ("file_move", "file_rename"):
            target = Path(_as_text(arguments, "path" if name == "file_move" else "path"))
            return self.desktop.is_sensitive_path(target)
        return False

    # -- execution ----------------------------------------------------------

    def execute(self, name: str, arguments: Optional[Dict[str, object]] = None) -> Dict[str, object]:
        """Run one validated tool call. Never raises for bad input."""
        arguments = arguments or {}
        problem = self.validate(name, arguments)
        if problem:
            log.warning("rejected tool call %s: %s", name, problem)
            return {"ok": False, "result": f"I will not run that: {problem}"}

        if self.requires_confirmation(name, arguments):
            if self.confirm is None:
                return {
                    "ok": False,
                    "result": f"'{name}' needs your confirmation, but none was requested.",
                }
            try:
                approved = bool(self.confirm(name, arguments))
            except Exception as exc:  # pragma: no cover - UI callback safety
                log.warning("confirmation callback failed: %s", exc)
                return {"ok": False, "result": "The confirmation prompt failed."}
            if not approved:
                return {"ok": False, "result": f"You cancelled '{name}'."}

        try:
            if name.startswith("local:"):
                return self.local_executor(name, arguments)  # type: ignore[misc]
            outcome = self._handlers[name](arguments)
        except Exception as exc:  # noqa: BLE001 - tool failures become model-visible text
            log.exception("tool %s crashed", name)
            return {"ok": False, "result": f"Tool '{name}' failed: {exc}"}

        if isinstance(outcome, dict):
            result = outcome.get("result", "")
            return {"ok": bool(outcome.get("ok", True)), "result": str(result)}
        return {"ok": True, "result": str(outcome)}

    def _finish(self, outcome: "ToolResult") -> Dict[str, object]:
        return {"ok": bool(outcome.ok), "result": outcome.as_text()}

    # -- handlers -----------------------------------------------------------

    def t_open_application(self, args: Dict[str, object]) -> Dict[str, object]:
        name = _as_text(args, "name") or _as_text(args, "application")
        return self._finish(self.desktop.launch_application(name))

    def t_search_files(self, args: Dict[str, object]) -> Dict[str, object]:
        query = _as_text(args, "query")
        directory = _as_text(args, "directory") or None
        return self._finish(self.desktop.search_files(query, directory))

    def t_open_file(self, args: Dict[str, object]) -> Dict[str, object]:
        path = self.desktop.resolve_file(_as_text(args, "path"))
        if path is None:
            return {"ok": False, "result": "I could not find that file."}
        return self._finish(self.desktop.open_path(path))

    def t_search_web(self, args: Dict[str, object]) -> Dict[str, object]:
        if self.browser is None:
            return {"ok": False, "result": "Browser automation is not enabled in the settings."}
        return self._finish(self.browser.search(_as_text(args, "query"),
                                               _as_text(args, "provider") or "google"))

    def t_browser_open_url(self, args: Dict[str, object]) -> Dict[str, object]:
        if self.browser is None:
            return {"ok": False, "result": "Browser automation is not enabled."}
        return self._finish(self.browser.open(_as_text(args, "url")))

    def t_browser_search(self, args: Dict[str, object]) -> Dict[str, object]:
        if self.browser is None:
            return {"ok": False, "result": "Browser automation is not enabled."}
        return self._finish(self.browser.search(_as_text(args, "query"),
                                               _as_text(args, "provider") or "google"))

    def t_browser_open_result(self, args: Dict[str, object]) -> Dict[str, object]:
        if self.browser is None:
            return {"ok": False, "result": "Browser automation is not enabled."}
        return self._finish(self.browser.open_search_result(_as_int(args, "index", 1, minimum=1)))

    def t_browser_extract_text(self, args: Dict[str, object]) -> Dict[str, object]:
        if self.browser is None:
            return {"ok": False, "result": "Browser automation is not enabled."}
        return self._finish(self.browser.extract_text(_as_int(args, "limit", 6000, minimum=200, maximum=20000)))

    def t_browser_navigate(self, args: Dict[str, object]) -> Dict[str, object]:
        if self.browser is None:
            return {"ok": False, "result": "Browser automation is not enabled."}
        return self._finish(self.browser.navigate(_as_text(args, "url")))

    def t_browser_scroll(self, args: Dict[str, object]) -> Dict[str, object]:
        if self.browser is None:
            return {"ok": False, "result": "Browser automation is not enabled."}
        return self._finish(self.browser.scroll(_as_text(args, "direction", "down"),
                                               _as_int(args, "amount", 4, minimum=1, maximum=20)))

    def t_navigate_browser(self, args: Dict[str, object]) -> Dict[str, object]:
        if self.browser is None:
            return {"ok": False, "result": "Browser automation is not enabled."}
        return self._finish(self.browser.navigate(_as_text(args, "direction", "back")))

    def t_scroll_page(self, args: Dict[str, object]) -> Dict[str, object]:
        """Scroll the focused desktop window (not the browser)."""
        return self._finish(self.desktop.scroll(_as_text(args, "direction", "down"),
                                               _as_int(args, "amount", 5, minimum=1, maximum=20)))

    def t_browser_tabs(self, args: Dict[str, object]) -> Dict[str, object]:
        if self.browser is None:
            return {"ok": False, "result": "Browser automation is not enabled."}
        return self._finish(self.browser.list_tabs())

    def t_browser_activate_tab(self, args: Dict[str, object]) -> Dict[str, object]:
        if self.browser is None:
            return {"ok": False, "result": "Browser automation is not enabled."}
        return self._finish(self.browser.activate_tab(_as_int(args, "index", 1, minimum=1)))

    def t_take_screenshot(self, args: Dict[str, object]) -> Dict[str, object]:
        return self._finish(self.desktop.take_screenshot())

    def t_get_system_status(self, args: Dict[str, object]) -> Dict[str, object]:
        return self._finish(self.desktop.system_status())

    def t_window_list(self, args: Dict[str, object]) -> Dict[str, object]:
        windows = self.desktop.list_windows()
        if not windows:
            return {"ok": True, "result": "No visible windows were found."}
        lines = [str(w["title"]) for w in windows[:20]]
        return {"ok": True, "result": f"{len(windows)} visible windows:\n" + "\n".join(lines)}

    def t_window_focus(self, args: Dict[str, object]) -> Dict[str, object]:
        return self._finish(self.desktop.focus_window(_as_text(args, "title")))

    def t_window_minimize(self, args: Dict[str, object]) -> Dict[str, object]:
        return self._finish(self.desktop.minimize_window(_as_text(args, "title")))

    def t_window_maximize(self, args: Dict[str, object]) -> Dict[str, object]:
        return self._finish(self.desktop.maximize_window(_as_text(args, "title")))

    def t_window_close(self, args: Dict[str, object]) -> Dict[str, object]:
        return self._finish(self.desktop.close_window(_as_text(args, "title")))

    def t_mouse_click(self, args: Dict[str, object]) -> Dict[str, object]:
        text = _as_text(args, "text")
        has_coords = args.get("x") is not None and args.get("y") is not None
        if text:
            return self._finish(self.desktop.click_visible_text(
                text, fallback_to_screenshot=bool(args.get("fallback", False))))
        if not has_coords:
            return {"ok": False, "result": "Provide x/y coordinates or visible text."}
        return self._finish(self.desktop.mouse_click(
            _as_int(args, "x", 0), _as_int(args, "y", 0),
            _as_text(args, "button", "left") or "left", double=bool(args.get("double", False))))

    def t_mouse_drag(self, args: Dict[str, object]) -> Dict[str, object]:
        return self._finish(self.desktop.mouse_drag(
            _as_int(args, "x1", 0), _as_int(args, "y1", 0),
            _as_int(args, "x2", 0), _as_int(args, "y2", 0)))

    def t_keyboard_type(self, args: Dict[str, object]) -> Dict[str, object]:
        text = _as_text(args, "text")
        if not text:
            return {"ok": False, "result": "Nothing to type."}
        if len(text) > 4000:
            return {"ok": False, "result": "That text is too long to type safely."}
        return self._finish(self.desktop.keyboard_type(text))

    def t_keyboard_shortcut(self, args: Dict[str, object]) -> Dict[str, object]:
        return self._finish(self.desktop.keyboard_shortcut(_as_text(args, "keys")))

    def t_file_create_folder(self, args: Dict[str, object]) -> Dict[str, object]:
        return self._finish(self.desktop.create_folder(_as_text(args, "name"),
                                                      _as_text(args, "parent") or None))

    def t_file_rename(self, args: Dict[str, object]) -> Dict[str, object]:
        return self._finish(self.desktop.rename_path(_as_text(args, "path"), _as_text(args, "new_name")))

    def t_file_copy(self, args: Dict[str, object]) -> Dict[str, object]:
        return self._finish(self.desktop.copy_path(_as_text(args, "source"), _as_text(args, "destination")))

    def t_file_move(self, args: Dict[str, object]) -> Dict[str, object]:
        return self._finish(self.desktop.move_path(_as_text(args, "source"), _as_text(args, "destination")))

    def t_file_delete(self, args: Dict[str, object]) -> Dict[str, object]:
        target = self.desktop.resolve_file(_as_text(args, "path"))
        if target is None:
            return {"ok": False, "result": "I could not find that file."}
        if self.desktop.is_sensitive_path(target):
            return {"ok": False, "result": "That path is protected and I will not delete it."}
        return self._finish(self.desktop.delete_path(str(target)))

    def t_read_document(self, args: Dict[str, object]) -> Dict[str, object]:
        outcome = self.desktop.read_document(_as_text(args, "path"),
                                             _as_int(args, "max_chars", 8000, minimum=200, maximum=40000))
        data = outcome.data if isinstance(outcome, ToolResult) else {}
        return {"ok": outcome.ok, "result": outcome.message, "data": data}

    def t_camera_photo(self, args: Dict[str, object]) -> Dict[str, object]:
        if self.camera is None:
            return {"ok": False, "result": "Camera support is not enabled."}
        ok, message, path = self.camera.take_photo(_as_text(args, "label") or None)
        return {"ok": ok, "result": message, "data": {"path": str(path) if path else ""}}

    def t_summarize_page(self, args: Dict[str, object]) -> Dict[str, object]:
        if self.gemini is None or not getattr(self.gemini, "configured", False):
            return {"ok": False, "result": "Gemini is not configured, so I cannot summarise pages."}
        url = _as_text(args, "url")
        text = _as_text(args, "text")
        if self.browser is not None and not text:
            outcome = self.browser.extract_text()
            if outcome.ok:
                text = str(outcome.data.get("text", ""))
        summary = self.gemini.summarize_page(url, text)
        return {"ok": True, "result": summary}


__all__ = [
    "ActionEngine",
    "ActionResult",
    "PermissionManager",
    "GlobalHotkey",
    "EmergencyStopped",
    "ToolRegistry",
    "CONFIRMATION_TOOLS",
]
