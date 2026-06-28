"""
============================================================
  workspace_plugin.py — Workspace Management Commands
============================================================

Thin delegation layer that routes workspace voice commands
to the existing ``Assistant.process_text()`` method.  No
duplicated logic — all workspace CRUD is handled by the
existing workspace_manager module.
============================================================
"""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from voice.plugins import BasePlugin
from voice.command_registry import extract_name, no_args

if TYPE_CHECKING:
    from voice.command_registry import CommandRegistry

_log: logging.Logger = logging.getLogger(__name__)


class WorkspacePlugin(BasePlugin):
    """Plugin for workspace management commands."""

    def __init__(self) -> None:
        self._assistant: Any = None

    @property
    def name(self) -> str:
        return "Workspace"

    @property
    def description(self) -> str:
        return "Create, open, delete, and list workspaces"

    def set_assistant(self, assistant: Any) -> None:
        """Inject the Assistant reference."""
        self._assistant = assistant

    def register(self, registry: CommandRegistry) -> None:
        """Register workspace management commands."""

        registry.register(
            intent="workspace.create",
            phrases=[
                "create workspace",
                "new workspace",
                "make workspace",
            ],
            handler=self._create_workspace,
            description="Create a new workspace",
            extractor=extract_name,
        )

        registry.register(
            intent="workspace.open",
            phrases=[
                "open workspace",
                "launch workspace",
                "start workspace",
            ],
            handler=self._open_workspace,
            description="Open a workspace",
            extractor=extract_name,
        )

        registry.register(
            intent="workspace.delete",
            phrases=[
                "delete workspace",
                "remove workspace",
            ],
            handler=self._delete_workspace,
            description="Delete a workspace",
            extractor=extract_name,
        )

        registry.register(
            intent="workspace.list",
            phrases=[
                "list workspaces",
                "show workspaces",
                "all workspaces",
                "my workspaces",
            ],
            handler=self._list_workspaces,
            description="List all workspaces",
            extractor=no_args,
        )

    # ── Handlers ───────────────────────────────────────────

    def _get_assistant(self) -> Any:
        """Get or create Assistant instance."""
        if self._assistant is None:
            from core.assistant import Assistant
            self._assistant = Assistant()
        return self._assistant

    def _create_workspace(self, text: str, args: dict[str, Any]) -> str:
        """Delegate workspace creation to the Assistant."""
        return self._get_assistant().process_text(text)

    def _open_workspace(self, text: str, args: dict[str, Any]) -> str:
        """Delegate workspace opening to the Assistant."""
        return self._get_assistant().process_text(text)

    def _delete_workspace(self, text: str, args: dict[str, Any]) -> str:
        """Delegate workspace deletion to the Assistant."""
        return self._get_assistant().process_text(text)

    def _list_workspaces(self, text: str, args: dict[str, Any]) -> str:
        """Delegate workspace listing to the Assistant."""
        return self._get_assistant().process_text(text)
