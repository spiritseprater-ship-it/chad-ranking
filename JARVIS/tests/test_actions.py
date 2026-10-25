"""Execution-layer tests: permissions, disambiguation, emergency stop."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from actions import ActionEngine, ActionResult, EmergencyStopped, PermissionManager
from brain import ParsedCommand


def make_engine(tmp_path: Path, permissions: dict | None = None) -> ActionEngine:
    root = str(tmp_path / "Documents")
    config = {
        "automation": {
            "scroll_amount": 5, "volume_step": 10,
            "search_max_results": 8, "search_max_seconds": 8,
            "search_max_entries": 40000,
        },
        "browser": {
            "default": "chrome",
            "search_url": "https://www.google.com/search?q={query}",
        },
        "permissions": {
            "require_confirmation": permissions
            if permissions is not None
            else {"delete_files": True, "screenshot": False, "system_configuration": True},
            "allowed_file_roots": [root],
            "sensitive_paths": ["Windows", "System32"],
        },
    }
    return ActionEngine(config)


def parsed(command: str, slots: dict | None = None) -> ParsedCommand:
    return ParsedCommand(command=command, raw="", normalized=command, confidence=0.9,
                         slots=slots or {})


def test_current_time_and_date(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    time_result = engine.execute(parsed("current_time"))
    date_result = engine.execute(parsed("current_date"))
    assert time_result.success and "It is" in time_result.message
    assert date_result.success and "Today is" in date_result.message


def test_unknown_command_is_reported(tmp_path: Path) -> None:
    result = make_engine(tmp_path).execute(parsed("teleport_to_mars"))
    assert result.success is False
    assert result.status == "error"
    assert "don't know" in result.message


def test_missing_folder_is_reported_not_raised(tmp_path: Path) -> None:
    result = make_engine(tmp_path).execute(parsed("open_folder", {"folder": "nope"}))
    assert result.success is False
    assert "couldn't find a folder" in result.message


def test_screenshot_requires_confirmation(tmp_path: Path) -> None:
    engine = make_engine(tmp_path, permissions={"screenshot": True})
    result = engine.execute(parsed("screenshot"))
    assert result.needs_confirmation is True
    assert result.status == "confirm"
    assert "screenshot" in result.confirmation_payload["message"].lower()


def test_web_search_confirmation_is_configurable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ActionEngine, "_open_url", lambda self, url: "stub-browser")
    engine = make_engine(tmp_path, permissions={"external_communication": False})
    result = engine.execute(parsed("google_search", {"query": "python"}))
    assert result.needs_confirmation is False
    assert result.success and "python" in result.message

    strict = make_engine(tmp_path, permissions={"external_communication": True})
    confirmed = strict.execute(parsed("google_search", {"query": "python"}))
    assert confirmed.needs_confirmation is True


def test_volume_confirmation_payload(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    result = engine.execute(parsed("set_volume", {"level": "60"}))
    assert result.needs_confirmation is True
    assert result.confirmation_payload["percent"] == 60


def test_volume_without_number_asks_for_one(tmp_path: Path) -> None:
    result = make_engine(tmp_path).execute(parsed("set_volume", {"level": ""}))
    assert result.success is False
    assert "level" in result.message


def test_search_file_disambiguates(tmp_path: Path, monkeypatch) -> None:
    opened: list = []
    monkeypatch.setattr(ActionEngine, "_open", lambda self, path: opened.append(path))
    documents = tmp_path / "Documents"
    documents.mkdir()
    (documents / "report-a.pdf").write_bytes(b"a")
    (documents / "report-b.pdf").write_bytes(b"b")
    (documents / "report-c.pdf").write_bytes(b"c")

    engine = make_engine(tmp_path)
    result = engine.execute(parsed("search_file", {"query": "report"}))
    assert result.needs_choice is True
    assert result.status == "choice"
    assert len(result.choices) == 3
    assert result.choice_payload["kind"] == "file"
    assert len(result.choice_payload["paths"]) == 3


def test_search_file_single_match_opens(tmp_path: Path, monkeypatch) -> None:
    opened: list = []
    monkeypatch.setattr(ActionEngine, "_open", lambda self, path: opened.append(path))
    documents = tmp_path / "Documents"
    documents.mkdir()
    (documents / "only-one.txt").write_bytes(b"x")

    engine = make_engine(tmp_path)
    result = engine.execute(parsed("search_file", {"query": "only-one"}))
    assert result.success is True
    assert result.needs_choice is False


def test_choice_by_number_and_by_name(tmp_path: Path, monkeypatch) -> None:
    opened: list = []
    monkeypatch.setattr(ActionEngine, "_open", lambda self, path: opened.append(path))
    documents = tmp_path / "Documents"
    documents.mkdir()
    (documents / "alpha.txt").write_bytes(b"a")
    (documents / "beta.txt").write_bytes(b"b")

    engine = make_engine(tmp_path)
    payload = {
        "kind": "file",
        "paths": [str(documents / "alpha.txt"), str(documents / "beta.txt")],
    }
    by_number = engine.execute_choice("2", payload)
    assert by_number.success and "beta" in by_number.message
    assert opened and opened[-1].name == "beta.txt"
    by_name = engine.execute_choice("alpha", payload)
    assert by_name.success and "alpha" in by_name.message
    assert opened[-1].name == "alpha.txt"


def test_delete_file_requires_confirmation_and_respects_sensitive_paths(
    tmp_path: Path,
) -> None:
    documents = tmp_path / "Documents"
    documents.mkdir()
    victim = documents / "old-notes.txt"
    victim.write_bytes(b"bye")

    engine = make_engine(tmp_path)
    result = engine.execute(parsed("delete_file", {"file": "old-notes"}))
    assert result.needs_confirmation is True
    assert "cannot be undone" in result.confirmation_payload["message"]

    confirmed = engine.confirm(result.confirmation_payload)
    assert confirmed.success is True
    assert not victim.exists()


def test_confirmation_runners_work(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ActionEngine, "_open_url", lambda self, url: "stub-browser")
    engine = make_engine(tmp_path, permissions={"screenshot": False})
    # google search confirmation
    confirmed = engine.confirm(
        {"action": "google_search", "query": "python"}
    )
    assert confirmed.success
    assert "python" in confirmed.message

    # unknown action cannot be confirmed
    bad = engine.confirm({"action": "teleport", "query": "x"})
    assert bad.success is False


def test_emergency_stop_interrupts_and_releases(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    engine.emergency_stop()
    assert engine.emergency_stopped is True
    result = engine.execute(parsed("open_calculator"))
    assert result.success is False
    assert "Emergency stop" in result.message
    assert engine.emergency_stopped is False  # reset after the abort


def test_permission_manager_rules() -> None:
    manager = PermissionManager(
        rules={"delete_files": True, "camera_access": False},
        allowed_roots=["Documents"],
        sensitive_paths=["Windows"],
    )
    assert manager.requires_confirmation("delete_file") is True
    assert manager.requires_confirmation("screenshot") is False
    assert manager.category_for("screenshot") == "camera_access"
    assert manager.category_for("scroll_up") is None
    assert manager.is_sensitive_path(Path("C:/Windows/System32/cmd.exe")) is True
    assert manager.is_sensitive_path(Path("C:/Users/me/Documents/a.txt")) is False


def test_browser_search_url_is_encoded(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    assert engine._search_url("hello world") == "https://www.google.com/search?q=hello+world"
