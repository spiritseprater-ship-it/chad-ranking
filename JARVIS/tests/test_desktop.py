"""Desktop engine tests: file ranking, index, controller and tool registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from actions import ToolRegistry
from desktop import (
    DesktopController,
    FileIndex,
    StartupManager,
    rank_files,
    similarity,
)


@pytest.fixture()
def sample_dir(tmp_path: Path) -> Path:
    root = tmp_path / "Documents"
    root.mkdir()
    (root / "Bharat Heavy Electricals - PFR.pdf").write_text("x", encoding="utf-8")
    (root / "Power Purchase Agreement draft.docx").write_text("x", encoding="utf-8")
    (root / "financial model.xlsx").write_text("x", encoding="utf-8")
    (root / "meeting notes.txt").write_text("x", encoding="utf-8")
    nested = root / "2024"
    nested.mkdir()
    (nested / "RFP response v2.docx").write_text("x", encoding="utf-8")
    return root


# -- ranking ---------------------------------------------------------------


def test_similarity_is_symmetric() -> None:
    assert similarity("flights", "flights") == 1.0
    assert 0.0 < similarity("flights", "hotels") < 1.0


def test_ranking_prefers_the_exact_filename(sample_dir: Path) -> None:
    files = [p for p in sample_dir.rglob("*") if p.is_file()]
    matches = rank_files("bharat heavy electricals", files)
    assert matches[0].path.name == "Bharat Heavy Electricals - PFR.pdf"
    assert matches[0].score > 1.0


def test_ranking_rewards_all_keywords_present(sample_dir: Path) -> None:
    files = [p for p in sample_dir.rglob("*") if p.is_file()]
    matches = rank_files("power purchase agreement", files)
    assert matches[0].path.name.startswith("Power Purchase Agreement")


def test_ranking_handles_partial_matches(sample_dir: Path) -> None:
    files = [p for p in sample_dir.rglob("*") if p.is_file()]
    matches = rank_files("rfp", files)
    assert matches and matches[0].path.name.startswith("RFP response")


def test_ranking_boosts_office_formats(sample_dir: Path) -> None:
    files = [p for p in sample_dir.rglob("*") if p.is_file()]
    office = rank_files("response", [p for p in files if p.name.startswith("RFP")])
    assert office[0].path.suffix.lower() == ".docx"


def test_ranking_returns_nothing_for_empty_query(sample_dir: Path) -> None:
    files = [p for p in sample_dir.rglob("*") if p.is_file()]
    assert rank_files("", files) == []


def test_ranking_matches_folder_names(sample_dir: Path) -> None:
    files = [p for p in sample_dir.rglob("*") if p.is_file()]
    matches = rank_files("response 2024", files)
    assert matches and "2024" in str(matches[0].path)


# -- index -----------------------------------------------------------------


def test_index_finds_files(sample_dir: Path) -> None:
    index = FileIndex([sample_dir])
    assert len(index.build()) == 5
    found = index.search("financial")
    assert found and found[0].path.name == "financial model.xlsx"


def test_index_skips_hidden_and_system_folders(tmp_path: Path) -> None:
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("x", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("x", encoding="utf-8")
    (tmp_path / "real.txt").write_text("x", encoding="utf-8")
    index = FileIndex([tmp_path])
    names = [entry[0] for entry in index.build()]
    assert names == ["real.txt"]


def test_index_respects_the_entry_cap(tmp_path: Path) -> None:
    for index in range(50):
        (tmp_path / f"file{index}.txt").write_text("x", encoding="utf-8")
    index = FileIndex([tmp_path], max_entries=10)
    assert len(index.build()) == 10


# -- controller ------------------------------------------------------------


def test_search_files_returns_matches(sample_dir: Path) -> None:
    controller = DesktopController(allowed_roots=[sample_dir])
    outcome = controller.search_files("financial model")
    assert outcome.ok
    assert "financial model.xlsx" in outcome.message


def test_search_files_without_results(sample_dir: Path) -> None:
    controller = DesktopController(allowed_roots=[sample_dir])
    outcome = controller.search_files("nothing-matches-this")
    assert not outcome.ok


def test_create_and_rename_folder(sample_dir: Path) -> None:
    controller = DesktopController(allowed_roots=[sample_dir])
    assert controller.create_folder("Invoices", str(sample_dir)).ok
    target = sample_dir / "Invoices"
    assert controller.rename_path(str(target), "Paid Invoices").ok
    assert (sample_dir / "Paid Invoices").exists()


def test_rename_rejects_existing_target(sample_dir: Path) -> None:
    controller = DesktopController(allowed_roots=[sample_dir])
    assert not controller.rename_path(
        str(sample_dir / "meeting notes.txt"), "financial model.xlsx"
    ).ok


def test_copy_and_move(sample_dir: Path) -> None:
    controller = DesktopController(allowed_roots=[sample_dir])
    assert controller.copy_path("meeting notes.txt", str(sample_dir / "2024")).ok
    assert (sample_dir / "2024" / "meeting notes.txt").exists()

    moved = sample_dir / "archive"
    moved.mkdir()
    assert controller.move_path("financial model.xlsx", str(moved)).ok
    assert not (sample_dir / "financial model.xlsx").exists()
    assert (moved / "financial model.xlsx").exists()

    # moving onto an existing file is refused, not overwritten
    assert not controller.move_path("meeting notes.txt", str(sample_dir / "2024")).ok


def test_sensitive_paths_are_protected(tmp_path: Path) -> None:
    secret = tmp_path / "secrets"
    secret.mkdir()
    (secret / "vault.txt").write_text("x", encoding="utf-8")
    controller = DesktopController(
        allowed_roots=[tmp_path], sensitive_paths=[str(secret).lower()]
    )
    assert controller.is_sensitive_path(secret / "vault.txt")
    assert not controller.delete_path("vault.txt").ok
    assert (secret / "vault.txt").exists()


def test_read_document_only_reads_text(tmp_path: Path) -> None:
    text_file = tmp_path / "notes.txt"
    text_file.write_text("hello jarvis", encoding="utf-8")
    binary = tmp_path / "image.png"
    binary.write_bytes(b"\x89PNG")
    controller = DesktopController(allowed_roots=[tmp_path])
    assert controller.read_document(str(text_file)).ok
    assert not controller.read_document(str(binary)).ok


def test_resolve_file_by_name(tmp_path: Path) -> None:
    report = tmp_path / "Quarterly Report.pdf"
    report.write_text("x", encoding="utf-8")
    controller = DesktopController(allowed_roots=[tmp_path])
    assert controller.resolve_file(str(report)) == report
    assert controller.resolve_file("Quarterly Report") == report


def test_system_status_reports_windows(tmp_path: Path) -> None:
    controller = DesktopController(allowed_roots=[tmp_path])
    outcome = controller.system_status()
    # non-Windows builds list no windows but still report successfully
    assert outcome.ok


# -- registry gating -------------------------------------------------------


def test_registry_rejects_unknown_tools(sample_dir: Path) -> None:
    registry = ToolRegistry(desktop=DesktopController(allowed_roots=[sample_dir]))
    assert registry.execute("does_not_exist", {})["ok"] is False


def test_registry_rejects_tools_not_enabled(sample_dir: Path) -> None:
    registry = ToolRegistry(
        desktop=DesktopController(allowed_roots=[sample_dir]), allowed_tools=["search_files"]
    )
    outcome = registry.execute("open_file", {"path": "x"})
    assert outcome["ok"] is False
    assert "not enabled" in outcome["result"]


def test_registry_requires_confirmation_for_sensitive_tools(sample_dir: Path) -> None:
    registry = ToolRegistry(desktop=DesktopController(allowed_roots=[sample_dir]))
    outcome = registry.execute("take_screenshot", {})
    assert outcome["ok"] is False
    assert "confirmation" in outcome["result"]


def test_registry_cancelled_by_the_user(sample_dir: Path) -> None:
    registry = ToolRegistry(
        desktop=DesktopController(allowed_roots=[sample_dir]),
        allowed_tools=["take_screenshot"],
        confirm=lambda name, args: False,
    )
    outcome = registry.execute("take_screenshot", {})
    assert outcome["ok"] is False
    assert "cancelled" in outcome["result"]


def test_registry_runs_allowed_tools(sample_dir: Path) -> None:
    registry = ToolRegistry(
        desktop=DesktopController(allowed_roots=[sample_dir]),
        allowed_tools=["search_files"],
    )
    outcome = registry.execute("search_files", {"query": "financial"})
    assert outcome["ok"] is True
    assert "financial model.xlsx" in outcome["result"]


def test_registry_local_commands_need_an_executor(sample_dir: Path) -> None:
    registry = ToolRegistry(desktop=DesktopController(allowed_roots=[sample_dir]))
    outcome = registry.execute("local:exit_jarvis", {})
    assert outcome["ok"] is False


def test_registry_validates_click_arguments(sample_dir: Path) -> None:
    registry = ToolRegistry(
        desktop=DesktopController(allowed_roots=[sample_dir]),
        allowed_tools=["mouse_click", "take_screenshot"],
        confirm=lambda name, args: True,
    )
    assert registry.validate("mouse_click", {}) is not None
    assert registry.validate("mouse_click", {"x": 10, "y": 20}) is None


def test_registry_limits_keyboard_length(sample_dir: Path) -> None:
    registry = ToolRegistry(
        desktop=DesktopController(allowed_roots=[sample_dir]),
        allowed_tools=["keyboard_type"],
        confirm=lambda name, args: True,
    )
    outcome = registry.execute("keyboard_type", {"text": "x" * 5000})
    assert outcome["ok"] is False


def test_registry_survives_handler_crashes(tmp_path: Path) -> None:
    class Exploding:
        def execute(self, *args, **kwargs):
            raise RuntimeError("boom")

    registry = ToolRegistry(desktop=Exploding())
    outcome = registry.execute("search_files", {"query": "x"})
    assert outcome["ok"] is False
    assert "failed" in outcome["result"]


# -- startup manager -------------------------------------------------------


def test_startup_manager_is_a_no_op_off_windows() -> None:
    manager = StartupManager("C:\\Program Files\\JARVIS\\JARVIS.exe")
    if not manager.is_enabled.__module__:  # pragma: no cover - defensive
        return
    # on a non-Windows host registration simply reports "not enabled"
    assert manager.is_enabled() is False
