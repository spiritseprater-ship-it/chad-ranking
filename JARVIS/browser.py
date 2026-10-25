"""
browser.py - Playwright browser automation (optional capability).

Keeps one Chromium instance with a small tab tracker so multi-step tasks
("search for the best flights, then open the third result") work across steps.
The browser is started lazily and only when a request needs it, so JARVIS does
not carry a ~150 MB browser footprint for users who never use it.

Content read from the web is treated as untrusted text and is never executed.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import quote_plus

from desktop import ToolResult

log = logging.getLogger("jarvis.browser")

SEARCH_PROVIDERS = {
    "google": "https://www.google.com/search?q={query}",
    "bing": "https://www.bing.com/search?q={query}",
    "duckduckgo": "https://duckduckgo.com/?q={query}",
    "youtube": "https://www.youtube.com/results?search_query={query}",
}

TEXT_LIMIT = 6000


@dataclass
class Tab:
    index: int
    url: str
    title: str = ""


class BrowserController:
    """Lazily-started Playwright Chromium with a small tab registry."""

    def __init__(self, headless: bool = False, user_data_dir: Optional[str] = None) -> None:
        self.headless = headless
        self.user_data_dir = user_data_dir
        self._playwright = None
        self._browser = None
        self._context = None
        self._tabs: List[Tab] = []
        self._counter = 0
        self._last_error: Optional[str] = None

    # -- lifecycle ----------------------------------------------------------

    def _ensure_started(self) -> bool:
        if self._context is not None:
            return True
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except ImportError:
            self._last_error = (
                "Playwright is not installed. Run:  pip install playwright && "
                "playwright install chromium"
            )
            return False
        try:
            self._playwright = sync_playwright().start()
            args = ["--disable-blink-features=AutomationControlled"]
            if self.headless:
                args.append("--headless=new")
            self._browser = self._playwright.chromium.launch(headless=self.headless, args=args)
            self._context = self._browser.new_context(
                ignore_https_errors=True,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
            )
            return True
        except Exception as exc:
            self._last_error = str(exc).split("\n")[0]
            log.warning("browser launch failed: %s", exc)
            return False

    def stop(self) -> None:
        for closer in (
            lambda: self._context and self._context.close(),
            lambda: self._browser and self._browser.close(),
            lambda: self._playwright and self._playwright.stop(),
        ):
            try:
                closer()
            except Exception:
                continue
        self._context = None
        self._browser = None
        self._playwright = None
        self._tabs = []
        self._counter = 0

    @property
    def available(self) -> bool:
        try:
            import playwright  # type: ignore

            return True
        except ImportError:
            return False

    def install_hint(self) -> str:
        return (
            "Playwright's Chromium browser is not installed yet. Run once on the PC:\n"
            "    playwright install chromium"
        )

    # -- tab management ----------------------------------------------------

    def open(self, url: str, activate: bool = True) -> ToolResult:
        url = (url or "").strip()
        if not re.match(r"^[a-z][a-z0-9+.-]*://", url, re.IGNORECASE):
            provider, term = self._search_term(url)
            url = SEARCH_PROVIDERS.get(provider, "google").format(query=quote_plus(term))
        if not self._ensure_started():
            return ToolResult(False, self._last_error or "Could not start the browser.")
        try:
            page = self._context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            self._counter += 1
            tab = Tab(self._counter, page.url, page.title())
            self._tabs.append(tab)
            page.close() if activate and self._tabs else None
            return ToolResult(
                True,
                f"Opened tab {tab.index}: {tab.url}",
                {"url": tab.url, "title": tab.title, "index": tab.index},
            )
        except Exception as exc:
            return ToolResult(False, f"Could not open '{url}': {exc}")

    def search(self, query: str, provider: str = "google") -> ToolResult:
        url = SEARCH_PROVIDERS.get((provider or "google").lower(), SEARCH_PROVIDERS["google"]).format(
            query=quote_plus(query or "")
        )
        return self.open(url, activate=False)

    def _search_term(self, url: str) -> tuple:
        """Split 'flights to mumbai' into provider guess + search term."""
        low = url.lower()
        if "youtube" in low:
            return "youtube", url
        if "bing" in low:
            return "bing", url
        if "duckduckgo" in low:
            return "duckduckgo", url
        return "google", url

    def navigate(self, direction: str = "back") -> ToolResult:
        """Move backwards or forwards in the active browser tab."""
        if not self._tabs:
            return ToolResult(False, "No browser tab is open yet.")
        if not self._ensure_started():
            return ToolResult(False, self._last_error or "The browser is not running.")
        direction = (direction or "back").strip().lower()
        if direction not in ("back", "forward"):
            return ToolResult(False, "Direction must be 'back' or 'forward'.")
        try:
            pages = [p for p in self._context.pages if p is not None]
            page = pages[-1] if pages else None
            if page is None:
                return ToolResult(False, "That browser tab is no longer available.")
            if direction == "back":
                page.go_back(wait_until="domcontentloaded", timeout=30000)
            else:
                page.go_forward(wait_until="domcontentloaded", timeout=30000)
            tab = self._tabs[-1]
            tab.url = page.url
            tab.title = page.title()
            return ToolResult(True, f"Navigated {direction}", {"url": page.url})
        except Exception as exc:
            return ToolResult(False, f"Could not navigate: {exc}")

    def list_tabs(self) -> ToolResult:
        if not self._ensure_started():
            return ToolResult(False, self._last_error or "The browser is not running.")
        results = []
        for tab in self._tabs:
            results.append(f"{tab.index}. {tab.title or '(untitled)'} - {tab.url}")
        if not results:
            return ToolResult(False, "No browser tabs are open.")
        return ToolResult(True, "\n".join(results), {"count": len(results)})

    def activate_tab(self, index: int) -> ToolResult:
        if not self._ensure_started():
            return ToolResult(False, self._last_error or "The browser is not running.")
        for tab in self._tabs:
            if tab.index == int(index):
                return ToolResult(True, f"Focused tab {tab.index}", {"url": tab.url, "title": tab.title})
        return ToolResult(False, f"No tab with index {index}. Open tabs: {self.list_tabs().message}")

    def navigate(self, url: str) -> ToolResult:
        return self.open(url, activate=True)

    def scroll(self, direction: str = "down", amount: int = 4) -> ToolResult:
        if not self._tabs:
            return ToolResult(False, "No browser tab is open yet.")
        if not self._ensure_started():
            return ToolResult(False, self._last_error or "The browser is not running.")
        try:
            page = self._context.pages[-1] if self._context.pages else None
            if page is None:
                return ToolResult(False, "That browser tab is no longer available.")
            page.mouse.wheel(0, -int(amount) * 600 if direction.lower().startswith("down")
                             else int(amount) * 600)
            return ToolResult(True, f"Scrolled {direction}")
        except Exception as exc:
            return ToolResult(False, f"Scroll failed: {exc}")

    def extract_text(self, limit: int = TEXT_LIMIT) -> ToolResult:
        """Extract readable text from the active browser tab."""
        if not self._tabs:
            return ToolResult(False, "No browser tab is open yet.")
        if not self._ensure_started():
            return ToolResult(False, self._last_error or "The browser is not running.")
        try:
            pages = [p for p in self._context.pages if p is not None]
            page = pages[-1] if pages else None
            if page is None:
                return ToolResult(False, "That browser tab is no longer available.")
            page.wait_for_timeout(800)
            text = page.evaluate(
                "() => Array.from(document.body.innerText).slice(0, %d).join('\\n').trim()" % int(limit)
            )
            if not text:
                return ToolResult(False, "That page has no readable text.")
            return ToolResult(True, f"Extracted {len(text)} characters from {page.url}", {"text": text})
        except Exception as exc:
            return ToolResult(False, f"Could not read that page: {exc}")

    def open_search_result(self, index: int = 1) -> ToolResult:
        """Open the nth search result on the active search page."""
        if not self._tabs:
            return ToolResult(False, "No browser tab is open yet.")
        if not self._ensure_started():
            return ToolResult(False, self._last_error or "The browser is not running.")
        try:
            pages = [p for p in self._context.pages if p is not None]
            page = pages[-1] if pages else None
            if page is None:
                return ToolResult(False, "That browser tab is no longer available.")
            candidates = page.eval_on_selector_all(
                "a",
                "(links) => links.map((a) => ({text: (a.innerText||'').trim().slice(0,120), href: a.href}))"
                " .filter((item) => item.href && !item.href.includes('google.com/url')"
                " && !item.href.includes('duckduckgo.com') && item.text.length > 15))",
            )
            if not candidates:
                return ToolResult(False, "I could not find any search results on that page.")
            target = candidates[min(int(index) - 1, len(candidates) - 1)]
            self._counter += 1
            tab = Tab(self._counter, target["href"], target["text"])
            self._tabs.append(tab)
            return ToolResult(
                True,
                f"Opening search result: {target['text']}",
                {"url": target["href"], "title": target["text"], "index": tab.index},
            )
        except Exception as exc:
            return ToolResult(False, f"Could not open that result: {exc}")


__all__ = ["BrowserController", "Tab", "SEARCH_PROVIDERS"]
