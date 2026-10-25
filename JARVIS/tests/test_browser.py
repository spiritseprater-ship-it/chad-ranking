"""Browser controller tests: provider mapping, tab state and error paths."""

from __future__ import annotations

from typing import List

import pytest

from browser import SEARCH_PROVIDERS, BrowserController, Tab
from desktop import ToolResult


def test_search_providers_are_supported() -> None:
    assert {"google", "bing", "duckduckgo", "youtube"} <= set(SEARCH_PROVIDERS)


def test_search_term_maps_known_sites() -> None:
    controller = BrowserController()
    assert controller._search_term("flights to mumbai") == ("google", "flights to mumbai")
    assert controller._search_term("react jobs youtube") == ("youtube", "react jobs youtube")
    assert controller._search_term("cheap flights bing") == ("bing", "cheap flights bing")


def test_open_builds_a_search_url(monkeypatch) -> None:
    controller = BrowserController()
    captured: List[str] = []
    monkeypatch.setattr(controller, "_ensure_started", lambda: True)
    monkeypatch.setattr(
        controller,
        "_context",
        _FakeContext(captured),
    )
    outcome = controller.open("react developer jobs")
    assert outcome.ok
    assert "google.com/search" in captured[0]
    assert "react+developer+jobs" in captured[0]


def test_search_uses_the_chosen_provider(monkeypatch) -> None:
    controller = BrowserController()
    captured: List[str] = []
    monkeypatch.setattr(controller, "_ensure_started", lambda: True)
    monkeypatch.setattr(controller, "_context", _FakeContext(captured))
    outcome = controller.search("kotlin jobs", provider="duckduckgo")
    assert outcome.ok
    assert "duckduckgo.com" in captured[0]


def test_tabs_are_tracked(monkeypatch) -> None:
    controller = BrowserController()
    monkeypatch.setattr(controller, "_ensure_started", lambda: True)
    monkeypatch.setattr(controller, "_context", _FakeContext([]))
    controller._tabs = [Tab(1, "https://example.com", "Example")]
    listing = controller.list_tabs()
    assert listing.ok
    assert "example.com" in listing.message

    focused = controller.activate_tab(1)
    assert focused.ok
    missing = controller.activate_tab(9)
    assert not missing.ok


def test_without_tabs_the_controller_explains(monkeypatch) -> None:
    controller = BrowserController()
    monkeypatch.setattr(controller, "_ensure_started", lambda: True)
    assert not controller.extract_text().ok
    assert not controller.scroll("down").ok
    assert not controller.navigate("https://example.com").ok or controller._tabs


def test_browser_unavailable_message_is_actionable(monkeypatch) -> None:
    controller = BrowserController()
    monkeypatch.setattr(controller, "_ensure_started", lambda: False)
    controller._last_error = "executable not found"
    outcome = controller.open("https://example.com")
    assert not outcome.ok
    assert "executable not found" in outcome.message


def test_install_hint_mentions_the_command() -> None:
    controller = BrowserController()
    hint = controller.install_hint()
    assert "playwright install chromium" in hint


class _FakePage:
    def __init__(self, url: str, captured: List[str]) -> None:
        self._url = url
        self._captured = captured

    def goto(self, url: str, **kwargs) -> None:
        self._url = url
        self._captured.append(url)

    @property
    def url(self) -> str:
        return self._url

    def title(self) -> str:
        return "Fake"

    def close(self) -> None:
        pass


class _FakeContext:
    def __init__(self, captured: List[str]) -> None:
        self._captured = captured
        self.pages: List[object] = []

    @property
    def urls(self) -> List[str]:
        return list(self._captured)

    def new_page(self) -> _FakePage:
        page = _FakePage("about:blank", self._captured)
        self.pages.append(page)
        return page
