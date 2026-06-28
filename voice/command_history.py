"""
============================================================
  command_history.py — Searchable Voice Command History
============================================================

PURPOSE:
    Persistent, searchable log of all voice commands.  Stores
    recognised speech, matched intent, confidence, execution
    time, result, timestamp, and engine name.

STORAGE:
    Uses the existing ``tasks.db`` SQLite database (new table
    ``voice_history``).  Does NOT touch existing tables.

USAGE:
    history = CommandHistory()
    history.add(entry)
    recent = history.get_recent(limit=20)
    results = history.search("dashboard")
    history.clear()
============================================================
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any

from database.db import get_connection

_log: logging.Logger = logging.getLogger(__name__)


# ── Schema ─────────────────────────────────────────────────

_CREATE_VOICE_HISTORY: str = """
CREATE TABLE IF NOT EXISTS voice_history (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    recognized_speech TEXT    NOT NULL,
    matched_command   TEXT    DEFAULT '',
    confidence        REAL   DEFAULT 0.0,
    execution_time_ms INTEGER DEFAULT 0,
    result            TEXT    DEFAULT '',
    engine            TEXT    DEFAULT '',
    timestamp         TEXT    DEFAULT (datetime('now', 'localtime'))
);
"""


# ── Data Classes ───────────────────────────────────────────

@dataclass
class HistoryEntry:
    """
    A single voice command history record.

    Attributes
    ----------
    recognized_speech : str
        The raw transcription from the speech engine.
    matched_command : str
        The intent that matched (or ``"ai_fallback"``).
    confidence : float
        Match confidence from 0.0 to 1.0.
    execution_time_ms : int
        How long the handler took in milliseconds.
    result : str
        Human-readable outcome.
    engine : str
        Name of the speech engine that produced the text.
    timestamp : str
        ISO 8601 timestamp (auto-set if empty).
    """
    recognized_speech: str = ""
    matched_command: str = ""
    confidence: float = 0.0
    execution_time_ms: int = 0
    result: str = ""
    engine: str = ""
    timestamp: str = ""


# ── Command History ────────────────────────────────────────

class CommandHistory:
    """
    Persistent, searchable voice command history.

    Stores entries in the ``voice_history`` table of the
    existing SQLite database.

    Usage
    -----
    ::
        history = CommandHistory()
        history.add(HistoryEntry(
            recognized_speech="open dashboard",
            matched_command="dashboard.open",
            confidence=0.95,
            execution_time_ms=42,
            result="Opening dashboard.",
            engine="Vosk",
        ))
        recent = history.get_recent(limit=10)
    """

    def __init__(self) -> None:
        self._conn: sqlite3.Connection = get_connection()
        self._init_table()
        _log.info("CommandHistory initialised.")

    def _init_table(self) -> None:
        """Create the voice_history table if it doesn't exist."""
        try:
            self._conn.execute(_CREATE_VOICE_HISTORY)
            self._conn.commit()
        except sqlite3.Error as exc:
            _log.error("Failed to create voice_history table: %s", exc)

    # ── Public API ─────────────────────────────────────────

    def add(self, entry: HistoryEntry) -> None:
        """
        Add a new entry to the command history.

        Parameters
        ----------
        entry : HistoryEntry
            The history record to store.
        """
        if not entry.timestamp:
            entry.timestamp = datetime.now().isoformat()

        try:
            self._conn.execute(
                """
                INSERT INTO voice_history
                    (recognized_speech, matched_command, confidence,
                     execution_time_ms, result, engine, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.recognized_speech,
                    entry.matched_command,
                    entry.confidence,
                    entry.execution_time_ms,
                    entry.result[:500],  # Truncate long results
                    entry.engine,
                    entry.timestamp,
                ),
            )
            self._conn.commit()
            _log.debug("History entry added: '%s'", entry.recognized_speech)
        except sqlite3.Error as exc:
            _log.error("Failed to add history entry: %s", exc)

    def get_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """
        Return the most recent history entries.

        Parameters
        ----------
        limit : int
            Maximum number of entries to return.

        Returns
        -------
        list[dict]
            Recent entries, newest first.
        """
        try:
            rows = self._conn.execute(
                "SELECT * FROM voice_history ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error as exc:
            _log.error("Failed to fetch history: %s", exc)
            return []

    def search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        Search history entries by speech text or command name.

        Parameters
        ----------
        query : str
            Search term (matched against speech and command).
        limit : int
            Maximum results.

        Returns
        -------
        list[dict]
            Matching entries, newest first.
        """
        try:
            search_term = f"%{query}%"
            rows = self._conn.execute(
                """
                SELECT * FROM voice_history
                WHERE recognized_speech LIKE ?
                   OR matched_command LIKE ?
                   OR result LIKE ?
                ORDER BY id DESC LIMIT ?
                """,
                (search_term, search_term, search_term, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error as exc:
            _log.error("Failed to search history: %s", exc)
            return []

    def clear(self) -> None:
        """Delete all voice command history."""
        try:
            self._conn.execute("DELETE FROM voice_history")
            self._conn.commit()
            _log.info("Voice command history cleared.")
        except sqlite3.Error as exc:
            _log.error("Failed to clear history: %s", exc)

    def count(self) -> int:
        """Return the total number of history entries."""
        try:
            row = self._conn.execute(
                "SELECT COUNT(*) AS cnt FROM voice_history"
            ).fetchone()
            return row["cnt"] if row else 0
        except sqlite3.Error as exc:
            _log.error("Failed to count history: %s", exc)
            return 0
