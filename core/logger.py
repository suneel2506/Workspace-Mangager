"""
============================================================
  logger.py — Workspace Manager Logging Module
============================================================

PURPOSE:
    Writes structured log entries to `logs.txt` every time a
    workspace is launched (or fails to launch).  This makes it
    easy to review history and debug issues.

LOG FORMAT:
    [2026-06-20 10:30:15]
    Workspace: coding
    Items:     VS Code, ChatGPT, GitHub
    Status:    Success
    ──────────────────────────────

FUTURE HOOKS:
    • Rotate logs when the file exceeds a configurable size.
    • Support JSON-structured logs for machine parsing.
    • Push critical errors to a desktop notification system.
============================================================
"""

from datetime import datetime
from pathlib import Path


# ── Default log file location ──────────────────────────────
# Sits next to main.py so users can find it easily.
DEFAULT_LOG_FILE: Path = Path(__file__).resolve().parent.parent / "logs.txt"


class Logger:
    """
    Simple append-only logger that writes human-readable entries
    to a plain-text file.

    Attributes
    ----------
    log_path : Path
        Absolute path to the log file.

    Usage
    -----
        logger = Logger()
        logger.log("coding", ["VS Code", "ChatGPT"], success=True)
    """

    def __init__(self, log_path: Path = DEFAULT_LOG_FILE) -> None:
        """
        Parameters
        ----------
        log_path : Path, optional
            Where to write log entries.  Defaults to ``logs.txt``
            in the project root.
        """
        self.log_path: Path = log_path

    # ── Public API ─────────────────────────────────────────
    def log(
        self,
        workspace_name: str,
        items_launched: list[str],
        success: bool,
        error_message: str = "",
    ) -> None:
        """
        Append a log entry for one workspace-launch attempt.

        Parameters
        ----------
        workspace_name : str
            Name of the workspace (e.g. ``"coding"``).
        items_launched : list[str]
            Display names of the items that were opened.
        success : bool
            ``True`` if everything launched without errors.
        error_message : str, optional
            Human-readable description of what went wrong.
        """
        timestamp: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status: str = "Success" if success else f"Failed - {error_message}"
        items_display: str = ", ".join(items_launched) if items_launched else "None"

        entry: str = (
            f"[{timestamp}]\n"
            f"Workspace: {workspace_name}\n"
            f"Items:     {items_display}\n"
            f"Status:    {status}\n"
            f"{'-' * 30}\n\n"
        )

        # Append to file (creates it if missing).
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(entry)

    def log_voice_event(self, event: str) -> None:
        """
        Log a voice-related event (recognition start, result, error).

        Parameters
        ----------
        event : str
            Free-text description of the voice event.
        """
        timestamp: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry: str = (
            f"[{timestamp}]\n"
            f"Voice:     {event}\n"
            f"{'-' * 30}\n\n"
        )
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(entry)
