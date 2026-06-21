"""
============================================================
  system_control.py -- Workstation Power Management
============================================================

PURPOSE:
    Provides safe, logged wrappers around Windows system
    commands for shutting down, restarting, locking, and
    sleeping the workstation.

SAFETY:
    ``shutdown`` and ``restart`` are **destructive** actions --
    they will close all running applications.  Both methods
    enforce a CLI confirmation prompt (``input()``) before
    executing.  A configurable delay (default 30 seconds) gives
    the user time to call ``cancel_shutdown()`` if they change
    their mind.

    ``lock_screen`` and ``sleep_screen`` are non-destructive and
    do **not** require confirmation.

PLATFORM NOTES:
    All commands in this module target **Windows**.  On other
    operating systems the methods log a warning and return
    ``False`` without executing anything.  Cross-platform
    support can be added later behind the same interface.

FUTURE HOOKS:
    * Linux support (``systemctl poweroff``, ``xdg-screensaver``).
    * macOS support (``osascript``, ``pmset``).
    * Scheduled shutdown at a specific wall-clock time.
    * Integrate with a GUI dialog instead of ``input()``.
============================================================
"""

from __future__ import annotations

import logging
import platform
import subprocess

# ── Module-level logger ────────────────────────────────────
logger: logging.Logger = logging.getLogger("Workspace Automation System")


class SystemControl:
    """
    Control workstation power state (shutdown, restart, lock,
    sleep) with safety confirmations and logging.

    Usage
    -----
        sc = SystemControl()
        sc.lock_screen()              # immediate, no confirmation
        sc.shutdown(delay=60)         # asks for confirmation first
        sc.cancel_shutdown()          # abort a pending shutdown
    """

    # ── Public API ─────────────────────────────────────────

    def shutdown(self, delay: int = 30) -> bool:
        """
        Shut down the workstation after *delay* seconds.

        A confirmation prompt is shown before the command is
        executed.  The user must type ``y`` or ``yes`` to proceed.

        On Windows this runs::

            shutdown /s /t <delay>

        Parameters
        ----------
        delay : int, optional
            Number of seconds to wait before the system powers
            off.  Defaults to ``30``.  During this window the
            shutdown can be aborted with ``cancel_shutdown()``.

        Returns
        -------
        bool
            ``True`` if the shutdown command was issued, ``False``
            if the user cancelled, the platform is unsupported,
            or an error occurred.
        """
        logger.info("Shutdown requested with %d-second delay.", delay)

        # ── Platform guard ─────────────────────────────────
        if not self._is_windows():
            return False

        # ── Confirmation ───────────────────────────────────
        if not self._confirm(
            f"System will SHUT DOWN in {delay} seconds. Are you sure?"
        ):
            logger.info("Shutdown cancelled by user.")
            return False

        # ── Execute ────────────────────────────────────────
        return self._run_command(
            f"shutdown /s /t {delay}",
            action_name="Shutdown",
        )

    def restart(self, delay: int = 30) -> bool:
        """
        Restart the workstation after *delay* seconds.

        A confirmation prompt is shown before the command is
        executed.  The user must type ``y`` or ``yes`` to proceed.

        On Windows this runs::

            shutdown /r /t <delay>

        Parameters
        ----------
        delay : int, optional
            Number of seconds to wait before the system restarts.
            Defaults to ``30``.

        Returns
        -------
        bool
            ``True`` if the restart command was issued, ``False``
            if the user cancelled, the platform is unsupported,
            or an error occurred.
        """
        logger.info("Restart requested with %d-second delay.", delay)

        if not self._is_windows():
            return False

        if not self._confirm(
            f"System will RESTART in {delay} seconds. Are you sure?"
        ):
            logger.info("Restart cancelled by user.")
            return False

        return self._run_command(
            f"shutdown /r /t {delay}",
            action_name="Restart",
        )

    def cancel_shutdown(self) -> bool:
        """
        Abort a pending shutdown or restart.

        On Windows this runs::

            shutdown /a

        Returns
        -------
        bool
            ``True`` if the abort command succeeded, ``False``
            otherwise.
        """
        logger.info("Attempting to cancel pending shutdown/restart.")

        if not self._is_windows():
            return False

        return self._run_command(
            "shutdown /a",
            action_name="Cancel shutdown",
        )

    def lock_screen(self) -> bool:
        """
        Lock the workstation immediately.

        On Windows this runs::

            rundll32.exe user32.dll,LockWorkStation

        No confirmation is required -- locking is non-destructive.

        Returns
        -------
        bool
            ``True`` if the lock command was issued, ``False``
            otherwise.
        """
        logger.info("Locking workstation.")

        if not self._is_windows():
            return False

        return self._run_command(
            "rundll32.exe user32.dll,LockWorkStation",
            action_name="Lock screen",
        )

    def sleep_screen(self) -> bool:
        """
        Turn off the monitor (put it to sleep).

        On Windows this sends a ``WM_SYSCOMMAND`` /
        ``SC_MONITORPOWER`` message via a small PowerShell
        one-liner.  The monitor wakes up on any mouse/keyboard
        input.

        No confirmation is required -- the monitor simply turns
        off.

        Returns
        -------
        bool
            ``True`` if the command was issued, ``False``
            otherwise.
        """
        logger.info("Turning off monitor (sleep screen).")

        if not self._is_windows():
            return False

        # PowerShell one-liner that sends SC_MONITORPOWER = 2 (off)
        # to the foreground window via the Win32 SendMessage API.
        ps_command: str = (
            "powershell -Command \""
            "(Add-Type '[DllImport(\\\"user32.dll\\\")]"
            "public static extern int SendMessage(int hWnd, int hMsg, int wParam, int lParam);'"
            " -Name a -Pas)::SendMessage(-1, 0x0112, 0xF170, 2)"
            "\""
        )

        return self._run_command(
            ps_command,
            action_name="Sleep screen",
        )

    # ── Private helpers ────────────────────────────────────

    @staticmethod
    def _is_windows() -> bool:
        """
        Check whether the current OS is Windows.

        If the OS is **not** Windows, a warning is logged and
        ``False`` is returned so that the caller can bail out.

        Returns
        -------
        bool
            ``True`` on Windows, ``False`` otherwise.
        """
        if platform.system() != "Windows":
            logger.warning(
                "SystemControl is Windows-only. "
                "Current OS: %s. Command skipped.",
                platform.system(),
            )
            return False
        return True

    @staticmethod
    def _confirm(message: str) -> bool:
        """
        Display a CLI confirmation prompt and return the result.

        Parameters
        ----------
        message : str
            The warning message to show the user.

        Returns
        -------
        bool
            ``True`` if the user types ``y`` or ``yes``,
            ``False`` for any other input (including blank).
        """
        try:
            answer: str = input(f"  [!] {message} [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            # Non-interactive context or Ctrl+C.
            logger.info("Confirmation prompt interrupted; treating as 'No'.")
            return False

        return answer in ("y", "yes")

    @staticmethod
    def _run_command(command: str, action_name: str) -> bool:
        """
        Execute a system command and log the outcome.

        Parameters
        ----------
        command : str
            The full shell command to execute.
        action_name : str
            Human-readable label for log messages
            (e.g. ``"Shutdown"``, ``"Lock screen"``).

        Returns
        -------
        bool
            ``True`` if the command exited with return code 0,
            ``False`` otherwise.
        """
        try:
            result: subprocess.CompletedProcess[bytes] = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                timeout=15,  # seconds; avoids hanging on broken commands
            )

            if result.returncode == 0:
                logger.info("%s command executed successfully.", action_name)
                return True

            # Non-zero exit code -- log stderr for debugging.
            stderr_text: str = result.stderr.decode("utf-8", errors="replace").strip()
            logger.error(
                "%s command failed (exit code %d): %s",
                action_name,
                result.returncode,
                stderr_text or "(no stderr output)",
            )
            return False

        except subprocess.TimeoutExpired:
            logger.error("%s command timed out.", action_name)
            return False

        except OSError as exc:
            logger.error("%s command OS error: %s", action_name, exc)
            return False
