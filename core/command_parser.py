"""
============================================================
  command_parser.py -- Expandable Voice/Text Command Router
============================================================

PURPOSE:
    Converts raw text input (from voice or keyboard) into a
    structured ``ParsedCommand`` that the ``Assistant`` can
    dispatch to the correct handler.

HOW IT WORKS:
    1.  The parser holds a registry of *intents*.  Each intent
        has a list of trigger keywords/phrases and an argument-
        extraction function.
    2.  When ``parse(text)`` is called, the parser checks the
        text against each intent's keywords (longest match first).
    3.  If a match is found, the extractor pulls out arguments
        (e.g. the workspace name from "create workspace IronForge").
    4.  A ``ParsedCommand`` dataclass is returned.

EXPANDING:
    To add a new command, either:
      a) Add a new entry to ``COMMAND_PATTERNS`` in settings.py
         and register an extractor here, or
      b) Call ``parser.register(intent, keywords, extractor)``
         at runtime.

FUTURE HOOKS:
    * Replace keyword matching with an NLP model (spaCy, Rasa).
    * Fuzzy matching with ``rapidfuzz`` for typo tolerance.
    * Context-aware parsing (e.g. "delete it" = delete last item).
============================================================
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from config.settings import COMMAND_PATTERNS, APP_REGISTRY

# ── Logger ─────────────────────────────────────────────────
_log: logging.Logger = logging.getLogger(__name__)


# ===========================================================
#  ParsedCommand dataclass
# ===========================================================

@dataclass
class ParsedCommand:
    """
    Structured representation of a parsed user command.

    Attributes
    ----------
    intent : str
        The matched intent name (e.g. ``"create_workspace"``).
    arguments : dict[str, Any]
        Extracted arguments (e.g. ``{"name": "IronForge"}``).
    raw_text : str
        The original unmodified input text.
    confidence : float
        Match confidence from 0.0 to 1.0.
        Keyword match = keyword_length / total_text_length.
    """
    intent: str
    arguments: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    confidence: float = 1.0


# ===========================================================
#  Default Argument Extractors
# ===========================================================
# Each extractor receives the full text and the matched keyword
# and returns a dict of extracted arguments.


def _extract_name_after_keyword(text: str, keyword: str) -> dict[str, Any]:
    """Extract the text that follows the keyword as a 'name' argument.

    Example:
        text    = "create workspace IronForge"
        keyword = "create workspace"
        result  = {"name": "IronForge"}
    """
    # Find where the keyword ends and grab the remainder.
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return {}
    remainder = text[idx + len(keyword):].strip()
    # Remove trailing filler words like "workspace", "please", etc.
    remainder = re.sub(
        r'\b(workspace|please|now|for me)\b', '', remainder, flags=re.IGNORECASE
    ).strip()
    if remainder:
        return {"name": remainder}
    return {}


def _extract_task_title(text: str, keyword: str) -> dict[str, Any]:
    """Extract a task title from text after the keyword.

    Example:
        text    = "add task finish authentication module"
        keyword = "add task"
        result  = {"title": "finish authentication module"}
    """
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return {}
    remainder = text[idx + len(keyword):].strip()
    if remainder:
        return {"title": remainder}
    return {}


def _extract_app_name(text: str, keyword: str) -> dict[str, Any]:
    """Extract an application name from the text.

    Checks the remainder against the APP_REGISTRY keys and also
    tries the word immediately after the keyword.

    Example:
        text    = "launch chrome"
        keyword = "launch"
        result  = {"app_name": "chrome"}
    """
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return {}
    remainder = text[idx + len(keyword):].strip().lower()

    # Check if the remainder (or its first word) is a known app.
    if remainder in APP_REGISTRY:
        return {"app_name": remainder}

    # Try multi-word matches (e.g. "vs code").
    for app_name in APP_REGISTRY:
        if app_name in remainder:
            return {"app_name": app_name}

    # Try the first word as fallback.
    first_word = remainder.split()[0] if remainder.split() else ""
    if first_word:
        return {"app_name": first_word}

    return {}


def _extract_search_query(text: str, keyword: str) -> dict[str, Any]:
    """Extract a search query from text after the keyword.

    Example:
        text    = "search Python pathlib tutorial"
        keyword = "search"
        result  = {"query": "Python pathlib tutorial"}
    """
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return {}
    remainder = text[idx + len(keyword):].strip()
    # Remove filler like "for", "about".
    remainder = re.sub(
        r'^(for|about)\s+', '', remainder, flags=re.IGNORECASE
    ).strip()
    if remainder:
        return {"query": remainder}
    return {}


def _extract_url(text: str, keyword: str) -> dict[str, Any]:
    """Extract a URL from text after the keyword.

    Example:
        text    = "go to github.com"
        keyword = "go to"
        result  = {"url": "github.com"}
    """
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return {}
    remainder = text[idx + len(keyword):].strip()
    if remainder:
        return {"url": remainder}
    return {}


def _extract_folder_path(text: str, keyword: str) -> dict[str, Any]:
    """Extract a folder path from text after the keyword."""
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return {}
    remainder = text[idx + len(keyword):].strip()
    if remainder:
        return {"path": remainder}
    return {}


def _no_args(text: str, keyword: str) -> dict[str, Any]:
    """Extractor that returns no arguments (for commands like 'help')."""
    return {}


# ===========================================================
#  Intent-to-Extractor Mapping
# ===========================================================
# Default extractors for each built-in intent.

_DEFAULT_EXTRACTORS: dict[str, Callable[[str, str], dict[str, Any]]] = {
    "create_workspace":   _extract_name_after_keyword,
    "open_workspace":     _extract_name_after_keyword,
    "delete_workspace":   _extract_name_after_keyword,
    "rename_workspace":   _extract_name_after_keyword,
    "list_workspaces":    _no_args,
    "add_task":           _extract_task_title,
    "complete_task":      _extract_task_title,
    "delete_task":        _extract_task_title,
    "show_tasks":         _no_args,
    "launch_app":         _extract_app_name,
    "search_google":      _extract_search_query,
    "open_url":           _extract_url,
    "organize_downloads": _no_args,
    "create_folder":      _extract_folder_path,
    "open_dashboard":     _no_args,
    "shutdown":           _no_args,
    "restart":            _no_args,
    "lock_screen":        _no_args,
    "help":               _no_args,
    # ── Voice overlay additions ────────────────────────────
    "close_dashboard":    _no_args,
    "hide_dashboard":     _no_args,
    "show_dashboard":     _no_args,
    "exit_workspace":     _no_args,
    "restart_workspace":  _no_args,
    "sleep_computer":     _no_args,
    "search_youtube":     _extract_search_query,
    "open_chatgpt":       _no_args,
}


# ===========================================================
#  CommandParser Class
# ===========================================================

class CommandParser:
    """
    Rule-based command parser with plugin registration.

    Matches user input against keyword patterns and extracts
    structured arguments for the ``Assistant`` to dispatch.

    Usage
    -----
    ::

        parser = CommandParser()
        result = parser.parse("create workspace IronForge")
        # result.intent == "create_workspace"
        # result.arguments == {"name": "IronForge"}

        # Register a custom command:
        parser.register(
            intent="greet",
            keywords=["hello", "hi", "hey"],
            extractor=lambda text, kw: {"greeting": text},
        )
    """

    def __init__(self) -> None:
        """Load built-in intents from ``COMMAND_PATTERNS`` in settings."""
        # Each entry: (intent, keyword, extractor)
        self._rules: list[tuple[str, str, Callable]] = []

        # Load all built-in patterns.
        for intent, keywords in COMMAND_PATTERNS.items():
            extractor = _DEFAULT_EXTRACTORS.get(intent, _no_args)
            for keyword in keywords:
                self._rules.append((intent, keyword.lower(), extractor))

        # Sort rules by keyword length (longest first) so that
        # "create workspace" matches before "create".
        self._rules.sort(key=lambda r: len(r[1]), reverse=True)

        _log.info(
            "CommandParser initialised with %d rules across %d intents.",
            len(self._rules),
            len(COMMAND_PATTERNS),
        )

    def register(
        self,
        intent: str,
        keywords: list[str],
        extractor: Callable[[str, str], dict[str, Any]] | None = None,
    ) -> None:
        """
        Register a new intent at runtime.

        Parameters
        ----------
        intent : str
            Unique intent name (e.g. ``"send_email"``).
        keywords : list[str]
            Trigger phrases (e.g. ``["send email", "email"]``).
        extractor : Callable, optional
            Function that extracts arguments from the text.
            Receives ``(text, matched_keyword)`` and returns a dict.
            Defaults to ``_no_args`` if not provided.
        """
        if extractor is None:
            extractor = _no_args

        for keyword in keywords:
            self._rules.append((intent, keyword.lower(), extractor))

        # Re-sort after adding new rules.
        self._rules.sort(key=lambda r: len(r[1]), reverse=True)

        _log.info(
            "Registered new intent '%s' with %d keywords.",
            intent, len(keywords),
        )

    def parse(self, text: str) -> ParsedCommand | None:
        """
        Parse raw text into a ``ParsedCommand``.

        Parameters
        ----------
        text : str
            Raw user input (from voice or keyboard).

        Returns
        -------
        ParsedCommand | None
            A structured command if a match was found, or ``None``
            if the text did not match any registered intent.
        """
        if not text or not text.strip():
            return None

        text_lower: str = text.strip().lower()

        for intent, keyword, extractor in self._rules:
            if keyword in text_lower:
                # Calculate confidence: keyword coverage over total text.
                confidence = len(keyword) / max(len(text_lower), 1)
                confidence = min(confidence, 1.0)

                # Extract arguments.
                try:
                    arguments = extractor(text.strip(), keyword)
                except Exception as exc:
                    _log.warning(
                        "Extractor error for intent '%s': %s",
                        intent, exc,
                    )
                    arguments = {}

                parsed = ParsedCommand(
                    intent=intent,
                    arguments=arguments,
                    raw_text=text.strip(),
                    confidence=confidence,
                )

                _log.info(
                    "Parsed: intent='%s', args=%s, confidence=%.2f",
                    parsed.intent, parsed.arguments, parsed.confidence,
                )
                return parsed

        _log.debug("No intent matched for text: '%s'", text)
        return None

    def get_help_text(self) -> str:
        """
        Return a formatted help string listing all available commands.

        Returns
        -------
        str
            Multi-line string with example commands grouped by intent.
        """
        # Group keywords by intent.
        intent_keywords: dict[str, list[str]] = {}
        for intent, keyword, _ in self._rules:
            intent_keywords.setdefault(intent, []).append(keyword)

        lines: list[str] = ["Available commands:", ""]
        for intent, keywords in sorted(intent_keywords.items()):
            # Show the intent name in a friendly format.
            friendly = intent.replace("_", " ").title()
            examples = ", ".join(f'"{kw}"' for kw in keywords[:3])
            lines.append(f"  • {friendly}: {examples}")

        return "\n".join(lines)
