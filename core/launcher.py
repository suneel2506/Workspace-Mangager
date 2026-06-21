"""
============================================================
  launcher.py — Application & URL Launcher
============================================================

PURPOSE:
    Takes a list of workspace items (dicts) and opens each one:
      • "app"  items → launched via ``subprocess.Popen``
      • "url"  items → opened in the default browser

    Errors for individual items are caught and collected so that
    one bad entry doesn't prevent the rest from opening.

DESIGN NOTES:
    subprocess.Popen is non-blocking — it starts the process and
    returns immediately.  We do NOT wait for apps to close.

    webbrowser.open uses the OS default browser.  On Windows this
    typically opens a new tab in Chrome / Edge / Firefox.

FUTURE HOOKS:
    • Close all items opened by a workspace (track PIDs).
    • Custom browser profiles per workspace.
    • Delay / stagger launches to avoid overwhelming the system.
    • "Focus mode" — close everything except workspace items.
============================================================
"""

import subprocess
import webbrowser
import platform
from typing import Any

from core.logger import Logger


class Launcher:
    """
    Opens applications and URLs defined in a workspace.

    Attributes
    ----------
    logger : Logger
        Logger instance for recording launch outcomes.

    Usage
    -----
        launcher = Launcher()
        launcher.launch("coding", items)
    """

    def __init__(self, logger: Logger | None = None) -> None:
        """
        Parameters
        ----------
        logger : Logger, optional
            If not provided, a default Logger is created.
        """
        self.logger: Logger = logger or Logger()

    # ── Public API ─────────────────────────────────────────
    def launch(
        self,
        workspace_name: str,
        items: list[dict[str, str]],
    ) -> bool:
        """
        Open every item in a workspace.

        Parameters
        ----------
        workspace_name : str
            Used for logging and user feedback.
        items : list[dict[str, str]]
            Each dict must have a ``"type"`` key (``"app"`` or ``"url"``).

        Returns
        -------
        bool
            ``True`` if *all* items launched without error.
        """
        if not items:
            print("  [!] Workspace is empty - nothing to launch.")
            self.logger.log(workspace_name, [], success=False, error_message="Empty workspace")
            return False

        launched_names: list[str] = []
        errors: list[str] = []

        for item in items:
            item_type: str = item.get("type", "").lower()
            display_name: str = item.get("name", item.get("path", item.get("value", "Unknown")))

            try:
                if item_type == "app":
                    self._open_app(item)
                elif item_type == "url":
                    self._open_url(item)
                else:
                    raise ValueError(f"Unknown item type: '{item_type}'")

                launched_names.append(display_name)
                print(f"  [+] Launched: {display_name}")

            except Exception as exc:
                error_msg: str = f"{display_name} -> {exc}"
                errors.append(error_msg)
                print(f"  [x] Failed:   {display_name} - {exc}")

        # ── Log the outcome ────────────────────────────────
        success: bool = len(errors) == 0
        error_summary: str = "; ".join(errors) if errors else ""

        self.logger.log(
            workspace_name=workspace_name,
            items_launched=launched_names,
            success=success,
            error_message=error_summary,
        )

        return success

    # ── Private helpers ────────────────────────────────────
    @staticmethod
    def _open_app(item: dict[str, Any]) -> None:
        """
        Launch a desktop application via ``subprocess.Popen``.

        Parameters
        ----------
        item : dict
            Must contain ``"path"`` — the command or exe path.

        Raises
        ------
        FileNotFoundError
            If the executable is not found on ``PATH``.
        OSError
            For other OS-level launch failures.
        """
        app_path: str = item.get("path", "")
        if not app_path:
            raise ValueError("App item is missing the 'path' key.")

        # On Windows we use 'start' via shell to handle commands
        # like 'code' that are batch scripts / shims.
        if platform.system() == "Windows":
            subprocess.Popen(
                f'start "" "{app_path}"',
                shell=True,
            )
        else:
            # macOS / Linux: launch directly.
            subprocess.Popen(
                [app_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    @staticmethod
    def _open_url(item: dict[str, Any]) -> None:
        """
        Open a URL in the system default browser.

        Parameters
        ----------
        item : dict
            Must contain ``"value"`` — the URL string.

        Raises
        ------
        ValueError
            If the URL is missing or empty.
        """
        url: str = item.get("value", "")
        if not url:
            raise ValueError("URL item is missing the 'value' key.")

        webbrowser.open(url)
