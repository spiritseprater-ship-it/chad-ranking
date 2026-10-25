"""
desktop.py - Windows desktop control engine.

Primitives used by every JARVIS capability (local commands and Gemini tool calls):

* mouse       click / move / drag / scroll / double / right click
* keyboard    type / shortcut / hotkeys
* windows     list / focus / minimize / maximize / restore / close / move / resize
* applications launch by name (whitelisted lookup, never arbitrary shell)
* files       search, rank, open, create, rename, copy, move, read
* screen      screenshot capture
* startup     per-user "launch at Windows start" registry entry

Window management uses the Windows API through ``ctypes`` (no extra dependency),
input uses ``pyautogui``, and control finding uses ``pywinauto`` UI Automation
when available with a coordinate fallback.  Everything is lazily imported so the
module can be imported and unit-tested on non-Windows machines.

Ranking of file matches is pure Python and fully unit-tested here.
"""

from __future__ import annotations

import ctypes
import difflib
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

log = logging.getLogger("jarvis.desktop")

WINDOWS = sys.platform.startswith("win")

# Directories skipped while indexing/searching.
_SKIP_DIRS = {
    "windows", "$recycle.bin", "appdata", "program files", "program files (x86)",
    "programdata", "perflogs", "system volume information", "node_modules",
    ".git", ".svn", "__pycache__", "thumbs.db", "onedrive - personal",
}


# ---------------------------------------------------------------------------
# file matching (pure, testable)
# ---------------------------------------------------------------------------

@dataclass
class FileMatch:
    path: Path
    score: float
    reasons: List[str] = field(default_factory=list)

    def describe(self) -> str:
        when = datetime.fromtimestamp(self.path.stat().st_mtime)
        return f"{self.path.name}  (score {self.score:.2f}, modified {when:%Y-%m-%d})"


_EXTENSION_HINTS = {
    "pdf": 1.0, "doc": 0.9, "docx": 0.9, "ppt": 0.9, "pptx": 0.9,
    "xls": 0.9, "xlsx": 0.9, "txt": 0.8, "md": 0.8, "csv": 0.7,
    "py": 0.6, "js": 0.6, "json": 0.6, "png": 0.5, "jpg": 0.5, "jpeg": 0.5,
}


def similarity(a: str, b: str) -> float:
    """Normalised similarity between two names (0..1)."""
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def rank_files(query: str, candidates: Iterable[Path]) -> List[FileMatch]:
    """Rank candidate files against a natural-language query.

    Signals: filename similarity, extension preference, directory match and
    modification recency.  Returns matches sorted best-first.
    """
    query = (query or "").strip().lower()
    if not query:
        return []

    tokens = [t for t in re.split(r"[^a-z0-9]+", query) if len(t) > 1]
    scored: List[FileMatch] = []
    now = time.time()

    for path in candidates:
        name = path.name.lower()
        stem = path.stem.lower()
        ext = path.suffix.lower().lstrip(".")
        reasons: List[str] = []
        score = 0.0

        # 1. whole-name similarity (strongest signal)
        name_score = similarity(query.replace(" ", ""), name.replace(" ", ""))
        if name_score > 0.4:
            score += name_score * 2.2
            reasons.append("filename match")

        # 2. all query tokens present in the name
        if tokens and all(token in name for token in tokens):
            score += 1.5
            reasons.append("all keywords in filename")

        # 3. any token present (partial credit)
        hits = [t for t in tokens if t in name]
        if hits and not all(token in name for token in tokens):
            score += 0.55 * len(hits)
            reasons.append("keywords: " + ", ".join(hits))

        # 4. directory mentioned in the query
        parent = str(path.parent).lower()
        for token in tokens:
            if token in parent and token not in name:
                score += 0.6
                reasons.append("matches folder")
                break

        # 5. extension preference
        ext_score = _EXTENSION_HINTS.get(ext)
        if ext_score:
            score += ext_score * 0.5
            reasons.append(f"{ext} file")
        if ext in ("pdf", "doc", "docx", "ppt", "pptx"):
            score += 0.3

        # 6. recency (recency-weighted, not dominant)
        try:
            age_days = (now - path.stat().st_mtime) / 86400.0
            if age_days < 1:
                score += 0.35
            elif age_days < 30:
                score += 0.2
            reasons.append("recent")
        except OSError:
            pass

        if score > 0.2:
            scored.append(FileMatch(path, round(score, 3), reasons))

    scored.sort(key=lambda item: (item.score, item.path.name), reverse=True)
    return scored


class FileIndex:
    """In-memory filename index over the user's allowed directories."""

    def __init__(self, roots: Sequence[Path], max_entries: int = 40000) -> None:
        self.roots = [Path(root) for root in roots]
        self.max_entries = int(max_entries)
        self._entries: List[Tuple[str, Path, float]] = []
        self._built = False

    def build(self, force: bool = False) -> List[Tuple[str, Path, float]]:
        if self._built and not force:
            return self._entries
        index: List[Tuple[str, Path, float]] = []
        scanned = 0
        for root in self.roots:
            if not root.exists():
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [
                    d for d in dirnames
                    if d.lower() not in _SKIP_DIRS and not d.startswith(".")
                ]
                for filename in filenames:
                    full = Path(dirpath) / filename
                    try:
                        mtime = full.stat().st_mtime
                    except OSError:
                        continue
                    index.append((filename.lower(), full, mtime))
                    scanned += 1
                    if scanned >= self.max_entries:
                        break
                if scanned >= self.max_entries:
                    break
            if scanned >= self.max_entries:
                break
        self._entries = index
        self._built = True
        log.info("file index built: %d entries", len(index))
        return index

    def search(self, query: str, directory: Optional[str] = None) -> List[FileMatch]:
        self.build()
        query_clean = re.sub(r"\s+", " ", (query or "").strip().lower())
        directory_low = (directory or "").strip().lower()

        variants = {query_clean, query_clean.replace(" ", "")}
        if " " in query_clean:
            variants.add(query_clean.replace(" ", "."))

        collected: List[Path] = []
        seen: set = set()
        for variant in variants:
            for name, path, _mtime in self._entries:
                if variant and variant in name and path not in seen:
                    if directory_low and directory_low not in str(path).lower():
                        continue
                    seen.add(path)
                    collected.append(path)

        return rank_files(query, collected)


# ---------------------------------------------------------------------------
# result type
# ---------------------------------------------------------------------------

@dataclass
class ToolResult:
    ok: bool
    message: str
    data: Dict[str, object] = field(default_factory=dict)

    def as_text(self) -> str:
        return self.message


# ---------------------------------------------------------------------------
# desktop controller
# ---------------------------------------------------------------------------

class DesktopController:
    """Windows desktop control primitives."""

    SW_HIDE = 0
    SW_SHOW = 5
    SW_MINIMIZE = 6
    SW_MAXIMIZE = 3
    SW_RESTORE = 9

    def __init__(
        self,
        allowed_roots: Optional[Sequence[str]] = None,
        sensitive_paths: Optional[Sequence[str]] = None,
        screenshot_dir: Optional[Path] = None,
        camera_enabled: bool = False,
    ) -> None:
        self.allowed_roots = [str(r) for r in (allowed_roots or [])]
        self.sensitive_paths = [str(p).lower() for p in (sensitive_paths or [])]
        self.screenshot_dir = Path(screenshot_dir) if screenshot_dir else None
        self.camera_enabled = camera_enabled
        self.file_index: Optional[FileIndex] = None
        self._pyautogui = None
        self._window_handles_cache: List[Dict[str, object]] = []
        self._last_screenshot: Optional[Path] = None

    # -- helpers ------------------------------------------------------------

    def _pg(self):
        if self._pyautogui is None:
            import pyautogui  # type: ignore

            pyautogui.FAILSAFE = True
            self._pyautogui = pyautogui
        return self._pyautogui

    def allowed_root_paths(self) -> List[Path]:
        home = Path.home()
        resolved: List[Path] = []
        for root in self.allowed_roots or []:
            candidate = Path(root)
            if not candidate.is_absolute():
                candidate = home / root
            if candidate.exists():
                resolved.append(candidate)
        if not resolved:
            for name in ("Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos"):
                candidate = home / name
                if candidate.exists():
                    resolved.append(candidate)
        return resolved or [home]

    def ensure_index(self) -> FileIndex:
        if self.file_index is None:
            self.file_index = FileIndex(self.allowed_root_paths())
        return self.file_index

    def is_sensitive_path(self, path: Path) -> bool:
        low = str(path).lower().replace("\\", "/")
        return any(marker in low for marker in self.sensitive_paths)

    def is_inside_allowed_roots(self, path: Path) -> bool:
        low = str(path).lower().replace("\\", "/")
        return any(str(root).lower() in low for root in self.allowed_root_paths())

    # -- mouse --------------------------------------------------------------

    def mouse_click(self, x: Optional[int] = None, y: Optional[int] = None,
                    button: str = "left", text: Optional[str] = None,
                    double: bool = False) -> ToolResult:
        if not WINDOWS:
            return ToolResult(False, "Mouse control requires Windows.")
        try:
            pg = self._pg()
            if text:
                target = self.find_visible_control(text)
                if target is None:
                    return ToolResult(False, f"Could not find a visible control labelled '{text}'.")
                x, y = target
                log.info("clicking visible control '%s' at %s", text, target)
            if x is None or y is None:
                return ToolResult(False, "Provide screen coordinates or visible text to click.")
            pg.moveTo(int(x), int(y))
            if double:
                pg.doubleClick(int(x), int(y))
            elif button == "right":
                pg.rightClick(int(x), int(y))
            else:
                pg.click(int(x), int(y))
            return ToolResult(True, f"Clicked at ({x}, {y})" + (f" on '{text}'" if text else ""))
        except Exception as exc:
            return ToolResult(False, f"Click failed: {exc}")

    def mouse_move(self, x: int, y: int) -> ToolResult:
        if not WINDOWS:
            return ToolResult(False, "Mouse control requires Windows.")
        try:
            self._pg().moveTo(int(x), int(y))
            return ToolResult(True, f"Moved mouse to ({x}, {y})")
        except Exception as exc:
            return ToolResult(False, f"Mouse move failed: {exc}")

    def mouse_drag(self, x1: int, y1: int, x2: int, y2: int) -> ToolResult:
        if not WINDOWS:
            return ToolResult(False, "Mouse control requires Windows.")
        try:
            pg = self._pg()
            pg.moveTo(int(x1), int(y1))
            pg.dragTo(int(x2), int(y2), duration=0.4)
            return ToolResult(True, f"Dragged ({x1},{y1}) -> ({x2},{y2})")
        except Exception as exc:
            return ToolResult(False, f"Drag failed: {exc}")

    def scroll(self, direction: str = "down", amount: int = 5) -> ToolResult:
        direction = (direction or "down").lower()
        if direction in ("up", "upwards"):
            direction = "up"
        elif direction in ("down", "downwards"):
            direction = "down"
        else:
            return ToolResult(False, "Scroll direction must be 'up' or 'down'.")
        if not WINDOWS:
            return ToolResult(False, "Scrolling requires Windows.")
        try:
            value = int(amount) * -1 if direction == "down" else int(amount)
            self._pg().scroll(value)
            return ToolResult(True, f"Scrolled {direction} by {abs(value)}")
        except Exception as exc:
            return ToolResult(False, f"Scroll failed: {exc}")

    # -- keyboard ------------------------------------------------------------

    def keyboard_type(self, text: str) -> ToolResult:
        if not text:
            return ToolResult(False, "Nothing to type.")
        if not WINDOWS:
            return ToolResult(False, "Keyboard control requires Windows.")
        try:
            self._pg().typewrite(text, interval=0.015)
            return ToolResult(True, f"Typed {len(text)} characters")
        except Exception as exc:
            return ToolResult(False, f"Typing failed: {exc}")

    def keyboard_shortcut(self, keys: str) -> ToolResult:
        parts = [k.strip().lower() for k in re.split(r"[+,]", keys or "") if k.strip()]
        if not parts:
            return ToolResult(False, "No keys given.")
        if not WINDOWS:
            return ToolResult(False, "Keyboard control requires Windows.")
        try:
            self._pg().hotkey(*parts)
            return ToolResult(True, f"Pressed {'+'.join(parts)}")
        except Exception as exc:
            return ToolResult(False, f"Shortcut failed: {exc}")

    # -- windows (ctypes, no extra dependency) ------------------------------

    def list_windows(self) -> List[Dict[str, object]]:
        """Enumerate visible top-level windows with their titles.

        Read-only and never raises: a failed enumeration simply reports no
        windows, so a status or focus request cannot crash the worker thread.
        """
        if not WINDOWS:
            return []
        try:
            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - non-Windows or broken COM
            log.debug("window enumeration unavailable: %s", exc)
            return []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)  # type: ignore[attr-defined]
        def enum_proc(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if not length:
                return True
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.strip()
            if title and title != "Program Manager":
                rect = ctypes.wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                self._window_handles_cache.append(
                    {
                        "handle": int(hwnd),
                        "title": title,
                        "left": rect.left,
                        "top": rect.top,
                        "right": rect.right,
                        "bottom": rect.bottom,
                        "width": rect.right - rect.left,
                        "height": rect.bottom - rect.top,
                    }
                )
            return True

        self._window_handles_cache = []
        try:
            user32.EnumWindows(enum_proc, 0)
        except Exception as exc:  # pragma: no cover - Win32 failure
            log.debug("EnumWindows failed: %s", exc)
            return []
        return list(self._window_handles_cache)

    def _match_window(self, title: str) -> Optional[Dict[str, object]]:
        low = (title or "").strip().lower()
        if not low:
            return None
        for window in self.list_windows():
            if low in str(window["title"]).lower():
                return window
        return None

    def focus_window(self, title: str) -> ToolResult:
        window = self._match_window(title)
        if window is None:
            return ToolResult(False, f"No visible window matching '{title}'.")
        try:
            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
            user32.ShowWindow(int(window["handle"]), self.SW_RESTORE)
            user32.SetForegroundWindow(int(window["handle"]))
            return ToolResult(True, f"Focused '{window['title']}'")
        except Exception as exc:
            return ToolResult(False, f"Could not focus that window: {exc}")

    def minimize_window(self, title: str) -> ToolResult:
        window = self._match_window(title)
        if window is None:
            return ToolResult(False, f"No visible window matching '{title}'.")
        try:
            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
            user32.ShowWindow(int(window["handle"]), self.SW_MINIMIZE)
            return ToolResult(True, f"Minimized '{window['title']}'")
        except Exception as exc:
            return ToolResult(False, f"Could not minimize that window: {exc}")

    def maximize_window(self, title: str) -> ToolResult:
        window = self._match_window(title)
        if window is None:
            return ToolResult(False, f"No visible window matching '{title}'.")
        try:
            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
            user32.ShowWindow(int(window["handle"]), self.SW_MAXIMIZE)
            return ToolResult(True, f"Maximized '{window['title']}'")
        except Exception as exc:
            return ToolResult(False, f"Could not maximize that window: {exc}")

    def close_window(self, title: str) -> ToolResult:
        window = self._match_window(title)
        if window is None:
            return ToolResult(False, f"No visible window matching '{title}'.")
        try:
            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
            user32.PostMessageW(int(window["handle"]), 0x0010, 0, 0)  # WM_CLOSE
            return ToolResult(True, f"Closed '{window['title']}'")
        except Exception as exc:
            return ToolResult(False, f"Could not close that window: {exc}")

    def minimize_all_others(self, keep_title: Optional[str] = None) -> ToolResult:
        closed = 0
        for window in self.list_windows():
            title = str(window["title"])
            if keep_title and keep_title.lower() in title.lower():
                continue
            if title.lower() in ("jarvis", "program manager"):
                continue
            try:
                user32 = ctypes.windll.user32  # type: ignore[attr-defined]
                user32.ShowWindow(int(window["handle"]), self.SW_MINIMIZE)
                closed += 1
            except Exception:
                continue
        return ToolResult(True, f"Minimized {closed} window(s)")

    def active_window(self) -> Optional[Dict[str, object]]:
        if not WINDOWS:
            return None
        try:
            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return None
            length = user32.GetWindowTextLengthW(hwnd)
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            return {"handle": int(hwnd), "title": buffer.value.strip()}
        except Exception:
            return None

    # -- UI automation ------------------------------------------------------

    def find_visible_control(self, text: str, timeout: float = 6.0) -> Optional[Tuple[int, int]]:
        """Locate a visible control by its label using UI Automation."""
        if not WINDOWS:
            return None
        try:
            from pywinauto import Desktop  # type: ignore

            deadline = time.monotonic() + timeout
            last_error: Optional[Exception] = None
            while time.monotonic() < deadline:
                try:
                    for window in Desktop(backend="uia").windows():
                        try:
                            for control in window.descendants():
                                try:
                                    label = str(control.window_text() or "").strip()
                                    if label and label.lower() == text.strip().lower():
                                        control.click_input()
                                        return (
                                            int(control.rectangle().left + control.rectangle().width() / 2),
                                            int(control.rectangle().top + control.rectangle().height() / 2),
                                        )
                                except Exception:
                                    continue
                        except Exception:
                            continue
                except Exception as exc:
                    last_error = exc
                time.sleep(0.4)
            if last_error:
                log.debug("UI automation lookup failed: %s", last_error)
            return None
        except ImportError:
            log.info("pywinauto not installed - falling back to coordinates")
            return None

    def click_visible_text(self, text: str, fallback_to_screenshot: bool = False) -> ToolResult:
        if not WINDOWS:
            return ToolResult(False, "Control finding requires Windows.")
        target = self.find_visible_control(text)
        if target is not None:
            return ToolResult(True, f"Clicked visible control '{text}'", {"x": target[0], "y": target[1]})
        if fallback_to_screenshot:
            shot = self.take_screenshot()
            return ToolResult(
                False,
                f"Could not find '{text}' in the accessibility tree. Screenshot saved: {shot.message}",
            )
        return ToolResult(False, f"Could not find a visible control labelled '{text}'.")

    # -- applications -------------------------------------------------------

    def find_executable(self, name: str) -> Optional[Path]:
        """Resolve an installed application to an executable path."""
        name = (name or "").strip().lower()
        if not name:
            return None
        for candidate in (name, f"{name}.exe"):
            found = shutil.which(candidate)
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

    def launch_application(self, name: str) -> ToolResult:
        app = self.find_executable(name)
        if app is None:
            return ToolResult(False, f"I could not find an application called '{name}'.")
        try:
            subprocess.Popen([str(app)], shell=False)
            time.sleep(0.4)
            return ToolResult(True, f"Launched {app.name}")
        except Exception as exc:
            return ToolResult(False, f"Could not launch {app.name}: {exc}")

    def open_path(self, path: Path) -> ToolResult:
        path = Path(path)
        if not path.exists():
            return ToolResult(False, f"{path} does not exist.")
        if self.is_sensitive_path(path):
            return ToolResult(False, "That path is protected and I will not touch it.")
        try:
            if WINDOWS:
                os.startfile(str(path))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(path)])
            return ToolResult(True, f"Opened {path.name}")
        except Exception as exc:
            return ToolResult(False, f"Could not open {path.name}: {exc}")

    # -- files --------------------------------------------------------------

    def search_files(self, query: str, directory: Optional[str] = None) -> ToolResult:
        if not query:
            return ToolResult(False, "What should I search for?")
        matches = self.ensure_index().search(query, directory)
        if not matches:
            return ToolResult(False, f"No files matched '{query}'.")
        data = {
            "matches": [{"path": str(m.path), "score": m.score, "reasons": m.reasons} for m in matches[:8]],
            "count": len(matches),
        }
        listing = "\n".join(f"{i + 1}. {m.describe()}" for i, m in enumerate(matches[:8]))
        if len(matches) == 1:
            return ToolResult(True, f"Found one match: {matches[0].path.name}", data)
        return ToolResult(True, f"Found {len(matches)} matches for '{query}':\n{listing}", data)

    def resolve_file(self, path_or_name: str) -> Optional[Path]:
        candidate = Path(path_or_name)
        if candidate.exists():
            return candidate
        matches = self.ensure_index().search(path_or_name)
        if not matches:
            return None
        return matches[0].path

    def create_folder(self, name: str, parent: Optional[str] = None) -> ToolResult:
        base = self._resolve_parent(parent)
        if base is None:
            return ToolResult(False, f"Could not find the folder '{parent}'.")
        target = base / name
        if target.exists():
            return ToolResult(False, f"'{name}' already exists in {base.name}.")
        try:
            target.mkdir(parents=True, exist_ok=False)
            return ToolResult(True, f"Created folder {target}")
        except OSError as exc:
            return ToolResult(False, f"Could not create that folder: {exc}")

    def _resolve_parent(self, name: Optional[str]) -> Optional[Path]:
        if not name:
            return None
        candidate = Path(name)
        if candidate.exists():
            return candidate
        for root in self.allowed_root_paths():
            for dirpath, dirnames, _files in os.walk(root):
                dirnames[:] = [d for d in dirnames if d.lower() not in _SKIP_DIRS]
                for dirname in dirnames:
                    if name.lower() in dirname.lower():
                        return Path(dirpath) / dirname
        return None

    def rename_path(self, path: str, new_name: str) -> ToolResult:
        source = self.resolve_file(path)
        if source is None:
            return ToolResult(False, f"Could not find '{path}'.")
        if self.is_sensitive_path(source):
            return ToolResult(False, "I will not rename files in a protected location.")
        target = source.with_name(new_name)
        if target.exists():
            return ToolResult(False, f"'{new_name}' already exists.")
        try:
            source.rename(target)
            return ToolResult(True, f"Renamed to {new_name}")
        except OSError as exc:
            return ToolResult(False, f"Rename failed: {exc}")

    def copy_path(self, source: str, destination: str) -> ToolResult:
        src = self.resolve_file(source)
        if src is None:
            return ToolResult(False, f"Could not find '{source}'.")
        dest_dir = self._resolve_parent(destination) or Path(destination)
        if not dest_dir.exists():
            return ToolResult(False, f"Destination '{destination}' does not exist.")
        if self.is_sensitive_path(dest_dir):
            return ToolResult(False, "I will not copy into a protected location.")
        target = dest_dir / src.name
        if target.exists():
            return ToolResult(False, f"'{src.name}' already exists in {dest_dir.name}.")
        try:
            shutil.copy2(src, target)
            return ToolResult(True, f"Copied {src.name} to {dest_dir.name}")
        except OSError as exc:
            return ToolResult(False, f"Copy failed: {exc}")

    def move_path(self, source: str, destination: str) -> ToolResult:
        src = self.resolve_file(source)
        if src is None:
            return ToolResult(False, f"Could not find '{source}'.")
        dest_dir = self._resolve_parent(destination) or Path(destination)
        if not dest_dir.exists():
            return ToolResult(False, f"Destination '{destination}' does not exist.")
        target = dest_dir / src.name
        if target.exists():
            return ToolResult(False, f"'{src.name}' already exists in {dest_dir.name}.")
        try:
            shutil.move(str(src), str(target))
            return ToolResult(True, f"Moved {src.name} to {dest_dir.name}")
        except OSError as exc:
            return ToolResult(False, f"Move failed: {exc}")

    def delete_path(self, path: str) -> ToolResult:
        target = self.resolve_file(path)
        if target is None:
            return ToolResult(False, f"Could not find '{path}'.")
        if self.is_sensitive_path(target):
            return ToolResult(False, "I will not delete files in a protected location.")
        if target.is_dir():
            try:
                shutil.rmtree(target)
                return ToolResult(True, f"Deleted folder {target.name}")
            except OSError as exc:
                return ToolResult(False, f"Delete failed: {exc}")
        try:
            target.unlink()
            return ToolResult(True, f"Deleted {target.name}")
        except OSError as exc:
            return ToolResult(False, f"Delete failed: {exc}")

    READABLE_SUFFIXES = {".txt", ".md", ".csv", ".json", ".log", ".py", ".js", ".ts", ".html", ".xml", ".yaml", ".yml", ".ini", ".cfg"}

    def read_document(self, path: str, max_chars: int = 8000) -> ToolResult:
        target = self.resolve_file(path)
        if target is None:
            return ToolResult(False, f"Could not find '{path}'.")
        if target.suffix.lower() not in self.READABLE_SUFFIXES:
            return ToolResult(False, f"I can read text files only (not {target.suffix or 'this format'}).")
        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return ToolResult(False, f"Could not read that file: {exc}")
        return ToolResult(
            True,
            f"Read {len(content)} characters from {target.name}",
            {"content": content[:max_chars], "path": str(target)},
        )

    # -- screen -------------------------------------------------------------

    def take_screenshot(self) -> ToolResult:
        if not WINDOWS:
            return ToolResult(False, "Screenshots require Windows.")
        try:
            from PIL import Image  # type: ignore
            import pyautogui  # type: ignore

            directory = self.screenshot_dir or (Path.home() / "Pictures" / "JARVIS Screenshots")
            directory.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            target = directory / f"jarvis-{stamp}.png"
            image = pyautogui.screenshot()
            if isinstance(image, Image.Image):
                image.save(str(target))
            self._last_screenshot = target
            return ToolResult(True, f"Screenshot saved to {target.name}", {"path": str(target)})
        except Exception as exc:
            return ToolResult(False, f"Screenshot failed: {exc}")

    def system_status(self) -> ToolResult:
        # a status report must never raise: it feeds diagnostics and the GUI
        try:
            windows = self.list_windows()
            active = self.active_window()
        except Exception as exc:  # pragma: no cover - defensive
            log.debug("system_status failed: %s", exc)
            return ToolResult(True, "Could not enumerate windows.", {"error": str(exc)})
        return ToolResult(
            True,
            f"{len(windows)} visible window(s); active: "
            f"{active['title'] if active else 'none'}",
            {"windows": [str(w["title"]) for w in windows[:12]], "active": active},
        )


# ---------------------------------------------------------------------------
# Windows startup integration (per-user registry, standard mechanism)
# ---------------------------------------------------------------------------

class StartupManager:
    """Enables/disables 'Launch JARVIS when Windows starts' for the current user.

    Uses the standard per-user Run registry key.  No service is installed and no
    elevated privileges are required.
    """

    RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    APP_ID = "JARVIS"

    def __init__(self, executable_path: Optional[str] = None) -> None:
        self.executable_path = executable_path or ""

    def is_enabled(self) -> bool:
        if not WINDOWS:
            return False
        try:
            import winreg  # type: ignore

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.RUN_KEY, 0, winreg.KEY_READ) as key:
                value, _ = winreg.QueryValueEx(key, self.APP_ID)
                return str(value) != ""
        except Exception:
            return False

    def set_enabled(self, enabled: bool, executable_path: Optional[str] = None) -> bool:
        if not WINDOWS:
            log.info("startup registration skipped (not Windows)")
            return False
        if executable_path:
            self.executable_path = executable_path
        if not self.executable_path:
            return False
        try:
            import winreg  # type: ignore

            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.RUN_KEY) as key:
                if enabled:
                    winreg.SetValueEx(key, self.APP_ID, 0, winreg.REG_SZ, f'"{self.executable_path}"')
                else:
                    try:
                        winreg.DeleteValue(key, self.APP_ID)
                    except FileNotFoundError:
                        pass
            log.info("startup registration %s", "enabled" if enabled else "disabled")
            return True
        except Exception as exc:
            log.error("could not update startup setting: %s", exc)
            return False


__all__ = [
    "DesktopController",
    "ToolResult",
    "FileMatch",
    "FileIndex",
    "rank_files",
    "similarity",
    "StartupManager",
    "WINDOWS",
]
