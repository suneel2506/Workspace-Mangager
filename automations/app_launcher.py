"""
============================================================
  app_launcher.py -- Desktop Application Launcher
============================================================

PURPOSE:
    Provides a simple interface to launch desktop applications
    either by a human-friendly name (looked up in the central
    APP_REGISTRY) or by an explicit executable path / command.

HOW IT WORKS:
    1.  The caller asks to launch "chrome" (case-insensitive).
    2.  ``AppLauncher`` finds the matching command in
        ``APP_REGISTRY`` (``"chrome"``).
    3.  On **Windows** the command is run via
            ``start "" "chrome"``
        which lets the shell locate batch-script shims (like
        ``code`` for VS Code) and detach the child process.
    4.  On **macOS / Linux** the command is executed directly
        with stdout/stderr silenced.

DESIGN NOTES:
    ``subprocess.Popen`` is *non-blocking* -- the launched app
    continues to run independently after this function returns.

    The class is intentionally decoupled from ``core.launcher``
    so it can be reused standalone (e.g. from the GUI or a CLI
    "open" command) without dragging in workspace logic.

FUTURE HOOKS:
    * Track returned PIDs so we can close apps later.
    * Support ``open`` on macOS and ``xdg-open`` on Linux.
    * Custom per-user registry loaded from a YAML config file.
============================================================
"""

from __future__ import annotations

import logging
import platform
import subprocess

from config.settings import APP_REGISTRY


# ── Module-level logger (shared by every AppLauncher instance) ─
logger: logging.Logger = logging.getLogger("Workspace Automation System")


class AppLauncher:
    """
    Launch desktop applications by friendly name or direct path.

    Attributes
    ----------
    registry : dict[str, str]
        Maps lower-case friendly names to shell commands.
        Loaded from ``config.settings.APP_REGISTRY`` at init.

    Usage
    -----
        launcher = AppLauncher()
        launcher.launch("chrome")              # by name
        launcher.launch_by_path("C:/my/app.exe")  # by path
        print(launcher.list_available())        # ['calculator', 'chrome', ...]
    """

    # ── Constructor ────────────────────────────────────────
    def __init__(self) -> None:
        """
        Initialise the launcher and load the application registry.

        The registry is a *copy* of ``APP_REGISTRY`` so that
        runtime mutations (e.g. adding a temporary alias) do not
        pollute the global config.
        """
        # Copy the registry so callers can safely mutate it at runtime
        # without side-effects on the global config constant.
        self.registry: dict[str, str] = dict(APP_REGISTRY)
        logger.info("AppLauncher initialised with %d registered apps.", len(self.registry))

    # ── Public API ─────────────────────────────────────────

    def launch(self, app_name: str) -> bool:
        """
        Launch an application by its friendly name.

        The look-up is **case-insensitive**: ``"Chrome"``,
        ``"CHROME"``, and ``"chrome"`` all resolve to the same
        registry entry.

        Parameters
        ----------
        app_name : str
            A human-friendly name that exists in ``APP_REGISTRY``
            (e.g. ``"vscode"``, ``"calculator"``).

        Returns
        -------
        bool
            ``True`` if the application was started successfully,
            ``False`` otherwise.

        Examples
        --------
        >>> launcher = AppLauncher()
        >>> launcher.launch("notepad")   # opens Notepad on Windows
        True
        """
        # Normalise to lower-case for the registry look-up.
        key: str = app_name.strip().lower()

        # Attempt to find the command in the registry.
        command: str | None = self.registry.get(key)

        if command is None:
            logger.warning(
                "App '%s' not found in registry. Available: %s",
                app_name,
                ", ".join(sorted(self.registry.keys())),
            )
            return False

        logger.info("Launching app '%s' (command: '%s')...", app_name, command)

        try:
            self._execute_command(command)
            logger.info("App '%s' launched successfully.", app_name)
            return True

        except FileNotFoundError:
            logger.error(
                "App '%s' failed: command '%s' not found on PATH.",
                app_name,
                command,
            )
            return False

        except OSError as exc:
            logger.error("App '%s' failed with OS error: %s", app_name, exc)
            return False

    def launch_by_path(self, path: str) -> bool:
        """
        Launch an application by its direct executable path or command.

        Use this when the app is **not** in the registry but the
        caller knows the exact command / path to run.

        Parameters
        ----------
        path : str
            Full path to an executable or a shell command.
            Examples: ``"C:/Program Files/MyApp/app.exe"``,
            ``"python -m http.server"``.

        Returns
        -------
        bool
            ``True`` if the command was started successfully,
            ``False`` otherwise.

        Examples
        --------
        >>> launcher = AppLauncher()
        >>> launcher.launch_by_path("notepad.exe")
        True
        """
        if not path or not path.strip():
            logger.error("launch_by_path() called with an empty path.")
            return False

        logger.info("Launching by path: '%s'...", path)

        try:
            self._execute_command(path)
            logger.info("Path launch successful: '%s'.", path)
            return True

        except FileNotFoundError:
            logger.error("Path launch failed: '%s' not found.", path)
            return False

        except OSError as exc:
            logger.error("Path launch failed for '%s': %s", path, exc)
            return False

    def list_available(self) -> list[str]:
        """
        Return a sorted list of all registered application names.

        Returns
        -------
        list[str]
            Alphabetically sorted friendly names (e.g.
            ``['calculator', 'chrome', 'cmd', ...]``).
        """
        return sorted(self.registry.keys())

    # ── Private helpers ────────────────────────────────────

    @staticmethod
    def _execute_command(command: str) -> None:
        """
        Run a command in a platform-aware, non-blocking fashion.

        On **Windows** we use ``start "" "<command>"`` through the
        shell so that:
          - Batch-script shims (e.g. ``code``) are found.
          - The child process is detached from the Python console.

        On **macOS / Linux** we launch the command directly with
        stdout and stderr silenced.

        Parameters
        ----------
        command : str
            The shell command or executable path to run.

        Raises
        ------
        FileNotFoundError
            If the executable cannot be located.
        OSError
            For any other operating-system-level error.
        """
        current_os: str = platform.system()

        if current_os == "Windows":
            # ``start ""`` opens a detached process; the first
            # pair of quotes is the window title (required by
            # ``start`` when the command itself is quoted).
            subprocess.Popen(
                f'start "" "{command}"',
                shell=True,
            )
        else:
            # On Unix-like systems, launch directly.
            subprocess.Popen(
                [command],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
