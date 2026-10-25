"""Command-understanding tests: English, Hindi, Hinglish and Indian English."""

from __future__ import annotations

import pytest

from brain import Brain, parse_number


@pytest.fixture()
def brain() -> Brain:
    return Brain()


# (utterance, expected command, expected slot)
CASES = [
    # --- acceptance test commands -----------------------------------------
    ("Hey Jarvis, chalo kaam karte hain", None, None),
    ("Jarvis, File Explorer kholo", "open_file_explorer", None),
    ("Open File Explorer", "open_file_explorer", None),
    ("Explorer kholo", "open_file_explorer", None),
    ("Jarvis, files dikhao", "open_file_explorer", None),
    ("Chrome par Python search karo", "google_search", "python"),
    ("Scroll down", "scroll_down", None),
    ("Scroll up", "scroll_up", None),
    ("Jarvis, stop listening", "stop_listening", None),
    # --- lifecycle ---------------------------------------------------------
    ("Go to standby", "go_standby", None),
    ("Back to standby", "go_standby", None),
    ("Jarvis, sleep", "go_standby", None),
    ("Exit Jarvis", "exit_jarvis", None),
    ("Jarvis, bye", "exit_jarvis", None),
    ("Khatam karo", "exit_jarvis", None),
    ("Band karo jarvis", "stop_listening", None),
    # --- browser / web ----------------------------------------------------
    ("Chrome kholo", "open_chrome", None),
    ("Open Chrome", "open_chrome", None),
    ("Browser kholo", "open_chrome", None),
    ("Search for weather", "google_search", "weather"),
    ("Google search cricket score", "google_search", "cricket score"),
    ("Search python on chrome", "google_search", "python"),
    ("Search for python file", "search_file", "python"),
    ("Go back", "browser_back", None),
    ("Browser forward", "browser_forward", None),
    ("Peeche jao", "browser_back", None),
    # --- files / applications ---------------------------------------------
    ("Open folder Downloads", "open_folder", "downloads"),
    ("Downloads folder kholo", "open_folder", "downloads"),
    ("Search for resume", "google_search", "resume"),
    ("File search project report", "search_file", "project report"),
    ("Find the file budget", "search_file", "budget"),
    ("Open report.pdf", "open_file", "report.pdf"),
    ("Open file report.pdf", "open_file", "report.pdf"),
    ("Open app Spotify", "open_app", "spotify"),
    ("Launch Visual Studio Code", "open_app", "visual studio code"),
    ("Close app Chrome", "close_app", "chrome"),
    ("Quit Notepad", "close_app", "notepad"),
    # --- system -----------------------------------------------------------
    ("Open settings", "open_settings", None),
    ("Settings kholo", "open_settings", None),
    ("Windows settings kholo", "open_settings", None),
    ("Open calculator", "open_calculator", None),
    ("Calculator kholo", "open_calculator", None),
    ("Calc kholo", "open_calculator", None),
    ("Open notepad", "open_notepad", None),
    ("Notepad kholo", "open_notepad", None),
    ("Take a screenshot", "screenshot", None),
    ("Screenshot le lo", "screenshot", None),
    ("Screenshot khincho", "screenshot", None),
    # --- time / date ------------------------------------------------------
    ("What time is it", "current_time", None),
    ("Time batao", "current_time", None),
    ("Waqt kya hai", "current_time", None),
    ("What is the date", "current_date", None),
    ("Date batao", "current_date", None),
    ("Tarikh kya hai", "current_date", None),
    # --- volume / audio ---------------------------------------------------
    ("Volume up", "volume_up", None),
    ("Volume down", "volume_down", None),
    ("Volume 80", "set_volume", "80"),
    ("Set volume to 50", "set_volume", "50"),
    ("Aawaj pachas karo", "set_volume", "pachas"),
    ("Volume do", "set_volume", "do"),
    ("Mute", "mute", None),
    ("Unmute", "unmute", None),
]


@pytest.mark.parametrize("text,expected,slot", CASES)
def test_command_mapping(brain: Brain, text: str, expected, slot) -> None:
    parsed = brain.parse(text)
    if expected is None:
        assert parsed is None, f"{text!r} should not map to a command"
        return
    assert parsed is not None, f"{text!r} did not map to any command"
    assert parsed.command == expected, f"{text!r} -> {parsed.command}, expected {expected}"
    if slot is not None:
        assert parsed.slots.get("query") == slot or parsed.slots.get("file") == slot \
            or parsed.slots.get("folder") == slot or parsed.slots.get("app") == slot \
            or parsed.slots.get("level") == slot, (
            f"{text!r} slots were {parsed.slots}"
        )


def test_scroll_without_direction_is_ambiguous(brain: Brain) -> None:
    parsed = brain.parse("Scroll")
    assert parsed is not None
    assert parsed.command == "scroll_unknown"
    assert parsed.is_ambiguous


def test_garbage_is_rejected(brain: Brain) -> None:
    assert brain.parse("bloop bleep blop") is None
    assert brain.parse("") is None
    assert brain.parse("   ") is None


def test_english_hindi_hinglish_equivalence(brain: Brain) -> None:
    """The same intent in three languages must map to one command."""
    groups = [
        ["Open File Explorer", "File Explorer kholo", "File Explorer kholo"],
        ["Open Chrome", "Chrome kholo", "Chrome kholo"],
        ["Scroll down", "Scroll niche karo", "Scroll niche karo"],
    ]
    for group in groups:
        commands = {brain.parse(text).command for text in group}
        assert len(commands) == 1, f"inconsistent mapping for {group}: {commands}"


def test_self_name_is_ignored(brain: Brain) -> None:
    assert brain.parse("Jarvis, open settings").command == "open_settings"
    assert brain.parse("Hey Jarvis open settings").command == "open_settings"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("50", 50), ("50%", 50), ("100", 100), ("pachas", 50), ("paanch", 5),
        ("do", 2), ("teen", 3), ("aath", 8), ("volume do", 2),
        ("ek sau", 101), ("", None), ("no number here", None),
    ],
)
def test_parse_number(text: str, expected) -> None:
    assert parse_number(text) == expected


def test_normalize_strips_filler_and_name() -> None:
    from brain import normalize_text

    normalized, meta = normalize_text("Jarvis, please can you open settings")
    assert "jarvis" not in normalized
    assert "please" not in normalized
    assert "settings" in normalized
    assert meta["had_jarvis"] is True
