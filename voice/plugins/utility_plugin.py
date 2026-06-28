"""
============================================================
  utility_plugin.py — General Utility Commands
============================================================

Registers voice commands for:
    * Current time
    * Today's date
    * Organize downloads
    * Show help / list commands
    * Add / show tasks (delegated to Assistant)
============================================================
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, TYPE_CHECKING

from voice.plugins import BasePlugin
from voice.command_registry import extract_after_keyword, no_args

if TYPE_CHECKING:
    from voice.command_registry import CommandRegistry

_log: logging.Logger = logging.getLogger(__name__)


class UtilityPlugin(BasePlugin):
    """Plugin for general utility voice commands."""

    def __init__(self) -> None:
        self._assistant: Any = None
        self._registry_ref: CommandRegistry | None = None

    @property
    def name(self) -> str:
        return "Utility"

    @property
    def description(self) -> str:
        return "Time, date, downloads, help, and task commands"

    def set_assistant(self, assistant: Any) -> None:
        """Inject the Assistant reference."""
        self._assistant = assistant

    def register(self, registry: CommandRegistry) -> None:
        """Register utility commands."""
        self._registry_ref = registry

        # ── Time / Date ────────────────────────────────────
        registry.register(
            intent="util.time",
            phrases=[
                "what time is it",
                "current time",
                "what's the time",
                "tell me the time",
                "time please",
            ],
            handler=self._get_time,
            description="Get the current time",
            extractor=no_args,
        )

        registry.register(
            intent="util.date",
            phrases=[
                "today's date",
                "what's the date",
                "what day is it",
                "current date",
                "tell me the date",
            ],
            handler=self._get_date,
            description="Get today's date",
            extractor=no_args,
        )

        # ── File operations ────────────────────────────────
        registry.register(
            intent="util.organize_downloads",
            phrases=[
                "organize downloads",
                "clean downloads",
                "sort downloads",
                "tidy downloads",
            ],
            handler=self._organize_downloads,
            description="Organize the Downloads folder",
            extractor=no_args,
        )

        # ── Help ───────────────────────────────────────────
        registry.register(
            intent="util.help",
            phrases=[
                "help",
                "what can you do",
                "list commands",
                "show commands",
                "available commands",
            ],
            handler=self._show_help,
            description="Show available voice commands",
            extractor=no_args,
        )

        # ── Task commands (delegated) ──────────────────────
        registry.register(
            intent="util.add_task",
            phrases=[
                "add task",
                "new task",
                "create task",
            ],
            handler=self._delegate_to_assistant,
            description="Add a new task",
            extractor=extract_after_keyword,
        )

        registry.register(
            intent="util.show_tasks",
            phrases=[
                "show tasks",
                "list tasks",
                "pending tasks",
                "my tasks",
            ],
            handler=self._delegate_to_assistant,
            description="Show pending tasks",
            extractor=no_args,
        )

        registry.register(
            intent="util.complete_task",
            phrases=[
                "complete task",
                "finish task",
                "done task",
                "mark task",
            ],
            handler=self._delegate_to_assistant,
            description="Complete a task",
            extractor=extract_after_keyword,
        )

    # ── Handlers ───────────────────────────────────────────

    def _get_time(self, text: str, args: dict[str, Any]) -> str:
        """Return the current time."""
        now = datetime.now()
        return f"It's {now.strftime('%I:%M %p')}."

    def _get_date(self, text: str, args: dict[str, Any]) -> str:
        """Return today's date."""
        now = datetime.now()
        return f"Today is {now.strftime('%A, %B %d, %Y')}."

    def _organize_downloads(self, text: str, args: dict[str, Any]) -> str:
        """Organize the downloads folder."""
        assistant = self._get_assistant()
        return assistant.process_text("organize downloads")

    def _show_help(self, text: str, args: dict[str, Any]) -> str:
        """Show all available voice commands."""
        if self._registry_ref is not None:
            return self._registry_ref.get_help_text()
        return "Help is not available."

    def _delegate_to_assistant(self, text: str, args: dict[str, Any]) -> str:
        """Delegate the command to the existing Assistant."""
        assistant = self._get_assistant()
        return assistant.process_text(text)

    def _get_assistant(self) -> Any:
        """Get or create Assistant instance."""
        if self._assistant is None:
            from core.assistant import Assistant
            self._assistant = Assistant()
        return self._assistant
