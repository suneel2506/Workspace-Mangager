"""
============================================================
  dashboard_plugin.py — Dashboard Lifecycle Commands
============================================================

Manages the singleton dashboard window:
    * Open  — create or bring-to-front
    * Close — terminate dashboard process
    * Hide  — withdraw (minimize to invisible)
    * Show  — restore from hidden state

Singleton logic ensures duplicate dashboards are never created.
============================================================
"""

from __future__ import annotations

import logging
import threading
from typing import Any, TYPE_CHECKING

from voice.plugins import BasePlugin
from voice.command_registry import no_args

if TYPE_CHECKING:
    from voice.command_registry import CommandRegistry

_log: logging.Logger = logging.getLogger(__name__)


class DashboardPlugin(BasePlugin):
    """Plugin for dashboard open/close/hide/show commands."""

    def __init__(self) -> None:
        self._dashboard_ref: Any = None
        self._dashboard_lock: threading.Lock = threading.Lock()
        self._assistant: Any = None

    @property
    def name(self) -> str:
        return "Dashboard"

    @property
    def description(self) -> str:
        return "Open, close, hide, and show the dashboard window"

    def set_assistant(self, assistant: Any) -> None:
        """Inject the Assistant reference (called by overlay startup)."""
        self._assistant = assistant

    def register(self, registry: CommandRegistry) -> None:
        """Register dashboard lifecycle commands."""
        registry.register(
            intent="dashboard.open",
            phrases=[
                "open dashboard",
                "show dashboard",
                "launch dashboard",
                "workspace open",
                "display dashboard",
            ],
            handler=self._open_dashboard,
            description="Open or focus the dashboard window",
            extractor=no_args,
        )

        registry.register(
            intent="dashboard.close",
            phrases=[
                "close dashboard",
                "exit dashboard",
                "shut dashboard",
                "kill dashboard",
            ],
            handler=self._close_dashboard,
            description="Close the dashboard window",
            extractor=no_args,
        )

        registry.register(
            intent="dashboard.hide",
            phrases=[
                "hide dashboard",
                "minimize dashboard",
            ],
            handler=self._hide_dashboard,
            description="Hide the dashboard window",
            extractor=no_args,
        )

    # ── Handlers ───────────────────────────────────────────

    def _open_dashboard(self, text: str, args: dict[str, Any]) -> str:
        """Open or bring-to-front the singleton dashboard."""

        # Try using the Assistant's singleton dashboard.
        if self._assistant is not None:
            return self._assistant.open_dashboard()

        # Fallback: manage our own reference.
        with self._dashboard_lock:
            if self._dashboard_ref is not None:
                try:
                    root = self._dashboard_ref.root
                    if root.winfo_exists():
                        root.deiconify()
                        root.lift()
                        root.focus_force()
                        return "Dashboard is already open."
                except Exception:
                    self._dashboard_ref = None

            def _launch() -> None:
                try:
                    from core.assistant import Assistant
                    from gui.dashboard import Dashboard

                    assistant = self._assistant or Assistant()
                    dash = Dashboard(assistant)
                    self._dashboard_ref = dash
                    dash.run()
                except Exception as exc:
                    _log.error("Dashboard launch error: %s", exc)
                finally:
                    with self._dashboard_lock:
                        self._dashboard_ref = None

            threading.Thread(
                target=_launch,
                daemon=True,
                name="DashboardThread",
            ).start()

            return "Opening dashboard."

    def _close_dashboard(self, text: str, args: dict[str, Any]) -> str:
        """Close the dashboard window."""
        if self._assistant is not None:
            ref = getattr(self._assistant, "_dashboard_ref", None)
            if ref is not None:
                try:
                    ref.root.after(0, ref.root.destroy)
                    return "Dashboard closed."
                except Exception:
                    pass
            return "Dashboard is not open."

        with self._dashboard_lock:
            if self._dashboard_ref is not None:
                try:
                    self._dashboard_ref.root.after(
                        0, self._dashboard_ref.root.destroy
                    )
                    self._dashboard_ref = None
                    return "Dashboard closed."
                except Exception:
                    self._dashboard_ref = None
            return "Dashboard is not open."

    def _hide_dashboard(self, text: str, args: dict[str, Any]) -> str:
        """Hide (withdraw) the dashboard window."""
        if self._assistant is not None:
            ref = getattr(self._assistant, "_dashboard_ref", None)
            if ref is not None:
                try:
                    ref.root.after(0, ref.root.withdraw)
                    return "Dashboard hidden."
                except Exception:
                    pass
            return "Dashboard is not open."

        with self._dashboard_lock:
            if self._dashboard_ref is not None:
                try:
                    self._dashboard_ref.root.after(
                        0, self._dashboard_ref.root.withdraw
                    )
                    return "Dashboard hidden."
                except Exception:
                    pass
            return "Dashboard is not open."
