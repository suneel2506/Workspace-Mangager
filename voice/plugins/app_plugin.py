"""
============================================================
  app_plugin.py — Application Launcher Commands
============================================================

Dynamically registers voice commands for every app in the
``APP_REGISTRY`` from ``config.settings``.  Adding a new app
to the registry auto-creates voice commands.

Also registers some extra apps not in the default registry.
============================================================
"""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from voice.plugins import BasePlugin
from voice.command_registry import extract_after_keyword

if TYPE_CHECKING:
    from voice.command_registry import CommandRegistry

_log: logging.Logger = logging.getLogger(__name__)


class AppPlugin(BasePlugin):
    """Plugin for launching desktop applications."""

    def __init__(self) -> None:
        self._app_launcher: Any = None

    @property
    def name(self) -> str:
        return "App Launcher"

    @property
    def description(self) -> str:
        return "Launch desktop applications by voice"

    def set_app_launcher(self, launcher: Any) -> None:
        """Inject the AppLauncher reference."""
        self._app_launcher = launcher

    def register(self, registry: CommandRegistry) -> None:
        """Register app launch commands from the APP_REGISTRY."""
        try:
            from config.settings import APP_REGISTRY
        except ImportError:
            _log.warning("Could not import APP_REGISTRY — app plugin disabled.")
            return

        # Collect unique app names to avoid duplicate registrations.
        registered_apps: set[str] = set()

        for app_name in APP_REGISTRY:
            if app_name in registered_apps:
                continue
            registered_apps.add(app_name)

            # Generate phrases for each app.
            phrases = [
                f"open {app_name}",
                f"launch {app_name}",
                f"start {app_name}",
                f"run {app_name}",
            ]

            registry.register(
                intent=f"app.launch.{app_name}",
                phrases=phrases,
                handler=self._make_launcher(app_name),
                description=f"Launch {app_name}",
            )

        # Register a catch-all "open/launch" handler for unknown apps.
        registry.register(
            intent="app.launch.generic",
            phrases=["open app", "launch app", "start app"],
            handler=self._launch_generic,
            description="Launch an application",
            extractor=extract_after_keyword,
        )

        _log.info(
            "AppPlugin registered %d app commands.",
            len(registered_apps),
        )

    # ── Handlers ───────────────────────────────────────────

    def _get_launcher(self) -> Any:
        """Get or create AppLauncher instance."""
        if self._app_launcher is None:
            from automations.app_launcher import AppLauncher
            self._app_launcher = AppLauncher()
        return self._app_launcher

    def _make_launcher(self, app_name: str):
        """Create a handler closure for a specific app."""
        def handler(text: str, args: dict[str, Any]) -> str:
            launcher = self._get_launcher()
            success = launcher.launch(app_name)
            if success:
                return f"Launched {app_name}."
            return f"Could not launch '{app_name}'. Check that it's installed."
        return handler

    def _launch_generic(self, text: str, args: dict[str, Any]) -> str:
        """Try to launch an app from the query argument."""
        query = args.get("query", "").strip().lower()
        if not query:
            launcher = self._get_launcher()
            available = ", ".join(launcher.list_available())
            return f"Please specify an app to launch. Available: {available}"

        launcher = self._get_launcher()
        success = launcher.launch(query)
        if success:
            return f"Launched {query}."
        return f"Could not launch '{query}'. Check that it's installed."
