"""
paths.py - filesystem locations that work from source and from the packaged EXE.

PyInstaller puts the Python sources in ``<bundle>/_internal``, so anything that
derives a path from ``__file__`` silently points inside the bundle instead of at
the folder the user extracted.  This module is the single place that decides
where JARVIS keeps its config, logs, history and assets, and it behaves correctly
in both modes:

* **source**  - the JARVIS folder (``python main.py``)
* **packaged** - the folder containing ``JARVIS.exe`` (onedir), with read-only
  resources read from the bundle

Nothing in here creates directories at import time.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

APP_NAME = "JARVIS"

#: bundled, read-only copy of config.json shipped inside the app
CONFIG_FILENAME = "config.json"


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    """Root of the extracted bundle (``sys._MEIPASS`` when frozen)."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent


def application_dir() -> Path:
    """Folder the user sees: the onedir folder, or the source folder."""
    if is_frozen():
        try:
            return Path(sys.executable).resolve().parent
        except Exception:  # pragma: no cover - defensive
            return bundle_root().parent
    return Path(__file__).resolve().parent


def resource_dir() -> Path:
    """Folder holding read-only bundled resources (icons, default config)."""
    return bundle_root()


def user_data_dir() -> Path:
    """Per-user data folder (config, logs, history, screenshots, photos)."""
    override = os.environ.get("JARVIS_USER_DATA_DIR", "").strip()
    if override:
        return Path(override)
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_NAME
    return Path.home() / ".jarvis"


def log_dir() -> Path:
    return user_data_dir() / "logs"


def default_config_path() -> Path:
    """Best candidate for the live config file.

    Order: user data dir (writable, survives upgrades and Program Files
    permissions) -> application dir -> bundled read-only default. If nothing
    exists yet the canonical user data location is returned, which is where
    :func:`ensure_user_config` creates it on first run.
    """
    candidates = [
        user_data_dir() / CONFIG_FILENAME,
        application_dir() / CONFIG_FILENAME,
        resource_dir() / CONFIG_FILENAME,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def ensure_user_config(source: Optional[Path] = None) -> Path:
    """Make sure a writable config.json exists in the user data dir.

    The first time JARVIS runs from a packaged build it copies the bundled
    default config into the user data dir, so later edits never need to write
    into the (possibly read-only) application folder.
    """
    target = user_data_dir() / CONFIG_FILENAME
    if target.exists():
        return target

    source_path = source or resource_dir() / CONFIG_FILENAME
    if not source_path.exists():
        source_path = application_dir() / CONFIG_FILENAME
    if not source_path.exists():
        # nothing to copy: create an empty object so validation reports it
        try:
            user_data_dir().mkdir(parents=True, exist_ok=True)
            target.write_text("{}\n", encoding="utf-8")
        except OSError:
            pass
        return target

    try:
        user_data_dir().mkdir(parents=True, exist_ok=True)
        # do not clobber a config the user already placed there
        if not target.exists():
            target.write_text(
                source_path.read_text(encoding="utf-8"), encoding="utf-8"
            )
    except OSError:
        pass
    return target


def find_dotenv() -> Optional[Path]:
    """Locate a ``.env`` file: user data dir first, then next to the app."""
    candidates = [
        user_data_dir() / ".env",
        application_dir() / ".env",
        resource_dir() / ".env",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def resource_path(*parts: str) -> Path:
    """Absolute path inside the bundled resources."""
    return resource_dir().joinpath(*parts)


def entry_path() -> str:
    """Path to the program entry point (the exe, or main.py from source)."""
    if is_frozen():
        return sys.executable
    return str(application_dir() / "main.py")


__all__ = [
    "APP_NAME",
    "CONFIG_FILENAME",
    "application_dir",
    "bundle_root",
    "default_config_path",
    "ensure_user_config",
    "entry_path",
    "find_dotenv",
    "is_frozen",
    "log_dir",
    "resource_dir",
    "resource_path",
    "user_data_dir",
]
