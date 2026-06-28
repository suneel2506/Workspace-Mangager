"""
============================================================
  browser_plugin.py — Browser & Search Commands
============================================================

Registers voice commands for:
    * Google search
    * YouTube search
    * Open ChatGPT
    * Open URL

Delegates to the existing ``BrowserTasks`` class.
============================================================
"""

from __future__ import annotations

import logging
import webbrowser
from typing import Any, TYPE_CHECKING

from voice.plugins import BasePlugin
from voice.command_registry import extract_after_keyword, no_args

if TYPE_CHECKING:
    from voice.command_registry import CommandRegistry

_log: logging.Logger = logging.getLogger(__name__)


class BrowserPlugin(BasePlugin):
    """Plugin for browser and search commands."""

    def __init__(self) -> None:
        self._browser_tasks: Any = None

    @property
    def name(self) -> str:
        return "Browser"

    @property
    def description(self) -> str:
        return "Google search, YouTube search, open URLs and ChatGPT"

    def set_browser_tasks(self, browser: Any) -> None:
        """Inject the BrowserTasks reference."""
        self._browser_tasks = browser

    def register(self, registry: CommandRegistry) -> None:
        """Register browser and search commands."""

        registry.register(
            intent="browser.search_google",
            phrases=[
                "search google for",
                "google search",
                "search for",
                "look up",
                "search",
            ],
            handler=self._search_google,
            description="Search Google",
            extractor=extract_after_keyword,
        )

        registry.register(
            intent="browser.search_youtube",
            phrases=[
                "search youtube for",
                "youtube search",
                "find on youtube",
                "play on youtube",
            ],
            handler=self._search_youtube,
            description="Search YouTube",
            extractor=extract_after_keyword,
        )

        registry.register(
            intent="browser.open_chatgpt",
            phrases=[
                "open chatgpt",
                "launch chatgpt",
                "open chat gpt",
                "start chatgpt",
            ],
            handler=self._open_chatgpt,
            description="Open ChatGPT in browser",
            extractor=no_args,
        )

        registry.register(
            intent="browser.open_url",
            phrases=[
                "open url",
                "go to",
                "visit",
                "browse to",
                "navigate to",
            ],
            handler=self._open_url,
            description="Open a URL in browser",
            extractor=extract_after_keyword,
        )

    # ── Handlers ───────────────────────────────────────────

    def _get_browser(self) -> Any:
        """Get or create BrowserTasks instance."""
        if self._browser_tasks is None:
            from automations.browser_tasks import BrowserTasks
            self._browser_tasks = BrowserTasks()
        return self._browser_tasks

    def _search_google(self, text: str, args: dict[str, Any]) -> str:
        """Search Google for the given query."""
        query = args.get("query", "").strip()
        if not query:
            return "What would you like to search for?"

        browser = self._get_browser()
        browser.search_google(query)
        _log.info("Google search: '%s'", query)
        return f"Searching Google for '{query}'."

    def _search_youtube(self, text: str, args: dict[str, Any]) -> str:
        """Search YouTube for the given query."""
        query = args.get("query", "").strip()
        if not query:
            return "What would you like to search on YouTube?"

        import urllib.parse
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.youtube.com/results?search_query={encoded}"
        webbrowser.open(url)
        _log.info("YouTube search: '%s'", query)
        return f"Searching YouTube for '{query}'."

    def _open_chatgpt(self, text: str, args: dict[str, Any]) -> str:
        """Open ChatGPT in the default browser."""
        webbrowser.open("https://chat.openai.com")
        _log.info("Opening ChatGPT.")
        return "Opening ChatGPT."

    def _open_url(self, text: str, args: dict[str, Any]) -> str:
        """Open a URL in the default browser."""
        url = args.get("query", "").strip()
        if not url:
            return "Please specify a URL."

        # Add https:// if no protocol specified.
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        webbrowser.open(url)
        _log.info("Opening URL: %s", url)
        return f"Opening {url}."
