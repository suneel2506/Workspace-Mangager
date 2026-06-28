"""
============================================================
  voice_logger.py — Separated, Rotating Log System
============================================================

PURPOSE:
    Creates dedicated log files for each subsystem of the voice
    assistant.  Each logger uses ``RotatingFileHandler`` with
    automatic rotation at 5 MB (3 backups kept).

    This module does NOT alter the existing root logger or
    ``setup_logging()`` in ``config.settings``.  It creates
    independent child loggers.

LOG FILES:
    logs/voice.log      — Speech recognition, wake word
    logs/system.log     — System commands, app launches
    logs/errors.log     — ERROR+ from all voice modules
    logs/dashboard.log  — Dashboard open/close/hide events
    logs/assistant.log  — Command dispatch, AI fallback

USAGE:
    from voice.voice_logger import get_voice_logger

    log = get_voice_logger("voice")
    log.info("Vosk engine started.")
============================================================
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.settings import LOG_DIR

# ── Constants ──────────────────────────────────────────────

_MAX_BYTES: int = 5 * 1024 * 1024   # 5 MB per file
_BACKUP_COUNT: int = 3               # keep 3 rotated backups
_LOG_FORMAT: str = "[%(asctime)s] %(levelname)-8s %(name)s: %(message)s"
_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

# Map of logger names to their dedicated log files.
_LOG_FILES: dict[str, str] = {
    "voice":     "voice.log",
    "system":    "system.log",
    "errors":    "errors.log",
    "dashboard": "dashboard.log",
    "assistant": "assistant.log",
}

# Track which loggers have been set up (avoid duplicate handlers).
_initialised: set[str] = set()


# ── Public API ─────────────────────────────────────────────

def get_voice_logger(name: str) -> logging.Logger:
    """
    Return a named logger with a dedicated rotating log file.

    Parameters
    ----------
    name : str
        Logger name.  Must be one of: ``"voice"``, ``"system"``,
        ``"errors"``, ``"dashboard"``, ``"assistant"``.
        If an unknown name is given, it maps to ``voice.log``.

    Returns
    -------
    logging.Logger
        Configured logger instance with file handler attached.
    """
    # Namespace all voice loggers under "voice_assistant."
    full_name = f"voice_assistant.{name}"

    if full_name in _initialised:
        return logging.getLogger(full_name)

    # Ensure log directory exists.
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(full_name)
    logger.setLevel(logging.DEBUG)

    # Prevent propagation to root logger (avoids duplicate console output).
    logger.propagate = False

    # Determine which file to use.
    log_filename = _LOG_FILES.get(name, "voice.log")
    log_path: Path = LOG_DIR / log_filename

    # ── File handler (rotating) ────────────────────────────
    file_handler = RotatingFileHandler(
        str(log_path),
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    )
    logger.addHandler(file_handler)

    # ── Error logger also captures ERROR+ from all voice modules ──
    if name != "errors":
        _setup_error_forwarder(logger)

    _initialised.add(full_name)
    return logger


def _setup_error_forwarder(source_logger: logging.Logger) -> None:
    """
    Add a handler to ``source_logger`` that forwards ERROR+
    messages to the dedicated ``errors.log`` file.
    """
    errors_log_path = LOG_DIR / "errors.log"

    error_handler = RotatingFileHandler(
        str(errors_log_path),
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(
        logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    )
    source_logger.addHandler(error_handler)
