"""
config/settings.py
~~~~~~~~~~~~~~~~~~
Central configuration module for the Workspace Automation System.

This file is the **single source of truth** for every setting the app uses:
project paths, UI constants, voice-recording parameters, the application
launcher registry, file-organisation rules, and the logging setup.

Why one file?
    Keeping all tunables in one place means you never have to hunt through
    ten modules to change a path or tweak a timeout.  Other modules simply
    ``from config.settings import <CONSTANT>`` and they are ready to go.

Extending this later:
    * Swap hard-coded values for ``os.environ.get(...)`` when you want
      environment-variable overrides.
    * Load a ``settings.toml`` / ``settings.yaml`` and merge it here.
    * The flat-constant style is deliberately database-agnostic -- nothing
      in this file imports SQLite, so migrating to PostgreSQL only touches
      ``database/db.py``.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
#  Project Paths
# ---------------------------------------------------------------------------
# ``Path(__file__).resolve()`` gives the absolute path of *this* file.
# ``.parent`` twice climbs from  config/settings.py  ->  config/  ->  project root.

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
"""Absolute path to the top-level WorkspaceManager directory."""

DB_PATH: Path = PROJECT_ROOT / "database" / "tasks.db"
"""Where the SQLite database file lives (created on first run)."""

LOG_DIR: Path = PROJECT_ROOT / "logs"
"""Directory that will contain rotating log files."""

LOG_FILE: Path = LOG_DIR / "app.log"
"""Main application log -- every DEBUG-and-above message lands here."""

ASSETS_DIR: Path = PROJECT_ROOT / "assets"
"""Static assets (icons, images, sounds) used by the GUI or TTS."""

LEGACY_JSON: Path = PROJECT_ROOT / "workspaces.json"
"""Path to the old JSON file used before the SQLite migration."""

# ---------------------------------------------------------------------------
#  Application Metadata
# ---------------------------------------------------------------------------

APP_NAME: str = "Workspace Automation System"
"""Human-readable name shown in window titles, logs, and dialogs."""

APP_VERSION: str = "2.0.0"
"""Semantic version string.  Bump this when you ship a release."""

DEFAULT_BROWSER: str | None = None
"""
Browser executable for ``webbrowser.get()``.
``None`` means "use whatever the OS considers the default browser".
Set to e.g. ``'chrome'`` or ``'firefox'`` to force a specific one.
"""

# ---------------------------------------------------------------------------
#  Voice / Audio Settings
# ---------------------------------------------------------------------------
# These are consumed by the voice-command subsystem (e.g. sounddevice,
# speech_recognition).  Adjust RECORD_DURATION if users need more time.

SAMPLE_RATE: int = 16_000
"""Audio sample rate in Hz.  16 kHz is the sweet spot for speech models."""

RECORD_DURATION: float = 5.0
"""How many seconds of audio to capture per voice command."""

RECORD_CHANNELS: int = 1
"""Mono recording -- stereo is unnecessary for speech and doubles file size."""

# ---------------------------------------------------------------------------
#  App Launcher Registry
# ---------------------------------------------------------------------------
# Maps *friendly names* (what the user says or types) to the command /
# executable that ``subprocess`` will call.
#
# Adding a new app is as easy as adding one line here:
#     'slack': r'C:\Users\you\AppData\Local\slack\slack.exe',
#
# On Windows the short names (``calc``, ``notepad``) are already on PATH,
# so a bare name is enough.  For apps installed elsewhere, use the full path.

APP_REGISTRY: dict[str, str] = {
    "chrome":       "chrome",
    "vscode":       "code",
    "code":         "code",
    "vs code":      "code",
    "notepad":      "notepad",
    "calculator":   "calc",
    "explorer":     "explorer",
    "terminal":     "wt",          # Windows Terminal
    "cmd":          "cmd",
    "powershell":   "powershell",
}

# ---------------------------------------------------------------------------
#  Downloads & File-Organisation Rules
# ---------------------------------------------------------------------------

DOWNLOADS_DIR: Path = Path(os.path.expanduser("~")) / "Downloads"
"""
Auto-detected Downloads folder for the current user.
``os.path.expanduser('~')`` resolves to ``C:\\Users\\<you>`` on Windows.
"""

FILE_CATEGORIES: dict[str, list[str]] = {
    "Images":       [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico"],
    "Documents":    [".pdf", ".doc", ".docx", ".txt", ".ppt", ".pptx",
                     ".xls", ".xlsx", ".csv"],
    "Videos":       [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv"],
    "Audio":        [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma"],
    "Archives":     [".zip", ".rar", ".7z", ".tar", ".gz"],
    "Code":         [".py", ".js", ".html", ".css", ".java", ".cpp",
                     ".c", ".h", ".json", ".xml"],
    "Executables":  [".exe", ".msi", ".bat", ".cmd"],
}
"""
Extension-to-folder mapping used by the ``organize_downloads`` feature.

How it works:
    The organiser iterates over every file in ``DOWNLOADS_DIR``.  It checks
    the file's suffix against each category.  If it matches, the file is
    moved into a sub-folder named after the category (e.g. ``Downloads/Images/``).
    Files that match *no* category are left in place (or moved to ``Other/``).

To add a new category, just insert a new key with a list of extensions:
    ``'3DModels': ['.obj', '.stl', '.fbx']``
"""

# ---------------------------------------------------------------------------
#  Logging Setup
# ---------------------------------------------------------------------------


def setup_logging() -> logging.Logger:
    """Configure and return the application-wide logger.

    Call this **once** at application startup (usually in ``main.py``).
    Subsequent calls are safe -- the function detects existing handlers and
    returns the cached logger without adding duplicates.

    What it creates
    ---------------
    * **File handler** -- writes *every* message (``DEBUG`` and above) to
      ``logs/app.log`` so you have a full audit trail for debugging.
    * **Console handler** -- prints ``INFO`` and above to ``stdout`` so the
      terminal stays readable during normal use.

    Returns
    -------
    logging.Logger
        The configured logger instance.  Other modules can also grab it
        with ``logging.getLogger('Workspace Automation System')``.

    Example
    -------
    >>> from config.settings import setup_logging
    >>> logger = setup_logging()
    >>> logger.info('Application started')
    INFO     Application started
    """
    # Ensure the log directory exists before we try to open a file in it.
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger: logging.Logger = logging.getLogger(APP_NAME)
    logger.setLevel(logging.DEBUG)

    # Guard: if handlers are already attached (e.g. module was re-imported),
    # skip setup and just hand back the existing logger.
    if logger.handlers:
        return logger

    # -- File handler -- captures everything (DEBUG+) -----------------------
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_fmt)

    # -- Console handler -- INFO and above ----------------------------------
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_fmt = logging.Formatter("%(levelname)-8s %(message)s")
    console_handler.setFormatter(console_fmt)

    # Attach both handlers to the logger.
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
