"""
============================================================
  system_plugin.py — System Control Commands
============================================================

Registers voice commands for:
    * Shutdown / Restart / Lock / Sleep computer
    * Exit / Restart workspace assistant

Delegates to the existing ``SystemControl`` class.
============================================================
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, TYPE_CHECKING

from voice.plugins import BasePlugin
from voice.command_registry import no_args

if TYPE_CHECKING:
    from voice.command_registry import CommandRegistry

_log: logging.Logger = logging.getLogger(__name__)


class SystemPlugin(BasePlugin):
    """Plugin for system power and workspace lifecycle commands."""

    def __init__(self) -> None:
        self._system_control: Any = None

    @property
    def name(self) -> str:
        return "System"

    @property
    def description(self) -> str:
        return "Shutdown, restart, lock, sleep, and workspace control"

    def set_system_control(self, system_control: Any) -> None:
        """Inject the SystemControl reference."""
        self._system_control = system_control

    def register(self, registry: CommandRegistry) -> None:
        """Register system control commands."""

        # ── Computer power ─────────────────────────────────
        registry.register(
            intent="system.shutdown",
            phrases=[
                "shutdown computer",
                "shut down computer",
                "power off",
                "turn off computer",
                "shutdown",
            ],
            handler=self._shutdown,
            description="Shut down the computer",
            extractor=no_args,
        )

        registry.register(
            intent="system.restart",
            phrases=[
                "restart computer",
                "reboot computer",
                "reboot",
            ],
            handler=self._restart,
            description="Restart the computer",
            extractor=no_args,
        )

        registry.register(
            intent="system.lock",
            phrases=[
                "lock computer",
                "lock screen",
                "lock",
                "lock workstation",
            ],
            handler=self._lock,
            description="Lock the computer screen",
            extractor=no_args,
        )

        registry.register(
            intent="system.sleep",
            phrases=[
                "sleep computer",
                "sleep mode",
                "put computer to sleep",
                "hibernate",
            ],
            handler=self._sleep,
            description="Put the computer to sleep",
            extractor=no_args,
        )

        # ── Workspace lifecycle ────────────────────────────
        registry.register(
            intent="system.exit_workspace",
            phrases=[
                "exit workspace",
                "quit workspace",
                "close workspace manager",
                "exit assistant",
                "quit assistant",
            ],
            handler=self._exit_workspace,
            description="Exit the workspace assistant",
            extractor=no_args,
        )

        registry.register(
            intent="system.restart_workspace",
            phrases=[
                "restart workspace",
                "restart assistant",
                "reload workspace",
            ],
            handler=self._restart_workspace,
            description="Restart the workspace assistant",
            extractor=no_args,
        )

    # ── Handlers ───────────────────────────────────────────

    def _get_system(self) -> Any:
        """Get or create SystemControl instance."""
        if self._system_control is None:
            from automations.system_control import SystemControl
            self._system_control = SystemControl()
        return self._system_control

    def _shutdown(self, text: str, args: dict[str, Any]) -> str:
        """Shut down the computer."""
        _log.info("Shutdown requested via voice.")
        sc = self._get_system()
        sc.shutdown(delay=30)
        return "Shutdown initiated. The computer will shut down in 30 seconds."

    def _restart(self, text: str, args: dict[str, Any]) -> str:
        """Restart the computer."""
        _log.info("Restart requested via voice.")
        sc = self._get_system()
        sc.restart(delay=30)
        return "Restart initiated. The computer will restart in 30 seconds."

    def _lock(self, text: str, args: dict[str, Any]) -> str:
        """Lock the screen."""
        _log.info("Lock screen requested via voice.")
        sc = self._get_system()
        success = sc.lock_screen()
        if success:
            return "Screen locked."
        return "Could not lock the screen."

    def _sleep(self, text: str, args: dict[str, Any]) -> str:
        """Put the computer to sleep."""
        _log.info("Sleep requested via voice.")
        import subprocess
        try:
            subprocess.run(
                "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
                shell=True,
                capture_output=True,
                timeout=10,
            )
            return "Computer going to sleep."
        except Exception as exc:
            _log.error("Sleep failed: %s", exc)
            return f"Could not put computer to sleep: {exc}"

    def _exit_workspace(self, text: str, args: dict[str, Any]) -> str:
        """Exit the workspace assistant."""
        _log.info("Exit workspace requested via voice.")
        # Schedule exit after a short delay to allow TTS.
        import threading
        threading.Timer(1.5, lambda: os._exit(0)).start()
        return "Goodbye! Exiting workspace assistant."

    def _restart_workspace(self, text: str, args: dict[str, Any]) -> str:
        """Restart the workspace assistant."""
        _log.info("Restart workspace requested via voice.")
        import threading
        def _do_restart() -> None:
            python = sys.executable
            os.execl(python, python, *sys.argv)
        threading.Timer(1.5, _do_restart).start()
        return "Restarting workspace assistant..."
