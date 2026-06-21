"""
============================================================
  browser_tasks.py -- Browser Automation Helpers
============================================================

PURPOSE:
    Convenience wrappers around Python's ``webbrowser`` module
    that handle common edge-cases (missing scheme, URL encoding)
    and provide batch-open support.

HOW IT WORKS:
    ``webbrowser.open(url)`` asks the operating system to open
    *url* in the user's default browser.  On most systems this
    opens a new tab rather than a new window.

    The class is deliberately thin -- it does *not* scrape pages
    or automate in-browser actions (that would require Selenium
    or Playwright).  It simply *opens things*.

DESIGN NOTES:
    All methods are instance methods (not static) so that future
    enhancements (e.g. injecting a specific browser profile or a
    headless driver) only require changes to ``__init__``.

FUTURE HOOKS:
    * Open in a specific browser (Chrome / Firefox / Edge).
    * Support browser profiles per workspace.
    * Playwright integration for full in-browser automation.
============================================================
"""

from __future__ import annotations

import logging
import urllib.parse
import webbrowser

# ── Module-level logger ────────────────────────────────────
logger: logging.Logger = logging.getLogger("Workspace Automation System")


class BrowserTasks:
    """
    Open URLs and perform web searches from Python.

    Usage
    -----
        browser = BrowserTasks()
        browser.open_url("github.com")          # auto-adds https://
        browser.search_google("Python pathlib")
        browser.open_multiple(["docs.python.org", "pypi.org"])
    """

    # ── Public API ─────────────────────────────────────────

    def open_url(self, url: str) -> bool:
        """
        Open a single URL in the default web browser.

        If the URL does not start with ``http://`` or ``https://``
        the method automatically prepends ``https://`` so that
        bare domains like ``"github.com"`` work correctly.

        Parameters
        ----------
        url : str
            The URL to open.  May be a full URL or a bare domain.

        Returns
        -------
        bool
            ``True`` if the browser was instructed to open the URL
            without raising an exception, ``False`` otherwise.

        Examples
        --------
        >>> BrowserTasks().open_url("github.com")
        True
        >>> BrowserTasks().open_url("https://docs.python.org")
        True
        """
        if not url or not url.strip():
            logger.error("open_url() called with an empty URL.")
            return False

        url = url.strip()

        # Auto-prepend scheme if missing.
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
            logger.debug("Auto-prepended 'https://' -> %s", url)

        logger.info("Opening URL: %s", url)

        try:
            webbrowser.open(url)
            logger.info("URL opened successfully: %s", url)
            return True

        except webbrowser.Error as exc:
            logger.error("Failed to open URL '%s': %s", url, exc)
            return False

    def search_google(self, query: str) -> bool:
        """
        Open a Google search for the given query string.

        The query is URL-encoded so that special characters
        (spaces, ampersands, etc.) are handled correctly.

        Parameters
        ----------
        query : str
            The search terms (e.g. ``"Python pathlib tutorial"``).

        Returns
        -------
        bool
            ``True`` if the search page was opened, ``False`` if
            the query was empty or the browser raised an error.

        Examples
        --------
        >>> BrowserTasks().search_google("Python pathlib tutorial")
        True
        """
        if not query or not query.strip():
            logger.error("search_google() called with an empty query.")
            return False

        # URL-encode the query so spaces become ``+`` and special
        # characters are percent-escaped.
        encoded_query: str = urllib.parse.quote_plus(query.strip())
        search_url: str = f"https://www.google.com/search?q={encoded_query}"

        logger.info("Google search: '%s' -> %s", query.strip(), search_url)

        try:
            webbrowser.open(search_url)
            logger.info("Google search opened successfully for '%s'.", query.strip())
            return True

        except webbrowser.Error as exc:
            logger.error("Google search failed for '%s': %s", query, exc)
            return False

    def open_multiple(self, urls: list[str]) -> int:
        """
        Open several URLs at once, returning how many succeeded.

        Each URL is passed through ``open_url()`` (so the
        auto-prepend logic still applies).  Failures for
        individual URLs do **not** prevent the rest from opening.

        Parameters
        ----------
        urls : list[str]
            A list of URLs or bare domains to open.

        Returns
        -------
        int
            The number of URLs that were opened successfully.

        Examples
        --------
        >>> BrowserTasks().open_multiple(["github.com", "pypi.org"])
        2
        """
        if not urls:
            logger.warning("open_multiple() called with an empty list.")
            return 0

        success_count: int = 0

        for url in urls:
            if self.open_url(url):
                success_count += 1

        logger.info(
            "open_multiple(): %d/%d URLs opened successfully.",
            success_count,
            len(urls),
        )
        return success_count
