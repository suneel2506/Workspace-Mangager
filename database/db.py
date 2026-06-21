"""
database/db.py
~~~~~~~~~~~~~~
SQLite database layer for the Workspace Automation System.

This module owns **everything** that touches the database file:

* **get_connection()** -- open (or create) the SQLite database and return a
  ready-to-use ``sqlite3.Connection``.
* **init_db()** -- run the schema DDL so all four tables exist.
* **migrate_from_json()** -- one-time import of the legacy
  ``workspaces.json`` into SQLite.

Design decisions
----------------
* **WAL mode** is enabled for better concurrent-read performance.
* **Foreign keys** are turned on per-connection (SQLite disables them by
  default -- a common gotcha).
* The module never hardcodes the DB path; it reads ``DB_PATH`` from
  ``config.settings`` so you can point it at a test database trivially.
* Every public function has thorough docstrings and inline comments aimed
  at beginners.

Migrating away from SQLite
--------------------------
If you later switch to PostgreSQL / MySQL, only *this file* needs to change.
The rest of the codebase talks to the DB through these three functions.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

# Import the canonical paths from the config layer.
from config.settings import DB_PATH, LEGACY_JSON, APP_NAME

# Grab the application logger (created by setup_logging in settings.py).
logger: logging.Logger = logging.getLogger(APP_NAME)

# ---------------------------------------------------------------------------
#  SQL Schema
# ---------------------------------------------------------------------------
# Each statement is a string constant so ``init_db()`` can iterate over them.
# ``IF NOT EXISTS`` makes the statements idempotent -- safe to run every
# time the app starts.

_CREATE_WORKSPACES: str = """
CREATE TABLE IF NOT EXISTS workspaces (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    path        TEXT    DEFAULT '',
    created_at  TEXT    DEFAULT (datetime('now', 'localtime'))
);
"""

_CREATE_WORKSPACE_ITEMS: str = """
CREATE TABLE IF NOT EXISTS workspace_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id  INTEGER NOT NULL,
    type          TEXT    NOT NULL CHECK(type IN ('app', 'url')),
    value         TEXT    NOT NULL,
    name          TEXT    DEFAULT '',
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);
"""

_CREATE_TASKS: str = """
CREATE TABLE IF NOT EXISTS tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id  INTEGER,
    title         TEXT    NOT NULL,
    description   TEXT    DEFAULT '',
    status        TEXT    DEFAULT 'pending'
                         CHECK(status IN ('pending', 'in_progress', 'completed')),
    priority      TEXT    DEFAULT 'medium'
                         CHECK(priority IN ('low', 'medium', 'high', 'critical')),
    due_date      TEXT    DEFAULT NULL,
    created_at    TEXT    DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE SET NULL
);
"""

_CREATE_COMMAND_LOG: str = """
CREATE TABLE IF NOT EXISTS command_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    command     TEXT    NOT NULL,
    result      TEXT    DEFAULT '',
    timestamp   TEXT    DEFAULT (datetime('now', 'localtime'))
);
"""

# Collected into a tuple so ``init_db`` can loop over them.
_ALL_TABLES: tuple[str, ...] = (
    _CREATE_WORKSPACES,
    _CREATE_WORKSPACE_ITEMS,
    _CREATE_TASKS,
    _CREATE_COMMAND_LOG,
)

# ---------------------------------------------------------------------------
#  Connection Management
# ---------------------------------------------------------------------------


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Open (or create) the SQLite database and return a connection.

    The function ensures the parent directory for the ``.db`` file exists,
    enables **WAL journal mode** for better read concurrency, and turns on
    **foreign-key enforcement** (SQLite ignores FK constraints by default
    unless you explicitly ``PRAGMA foreign_keys = ON``).

    Parameters
    ----------
    db_path : Path | None, optional
        Override the default database location.  Useful for unit tests that
        want an in-memory or temp-file database.  When ``None``, the path
        from ``config.settings.DB_PATH`` is used.

    Returns
    -------
    sqlite3.Connection
        A ready-to-use connection with ``row_factory`` set to
        ``sqlite3.Row`` so you can access columns by name
        (e.g. ``row['title']``).

    Example
    -------
    >>> conn = get_connection()
    >>> cursor = conn.execute("SELECT name FROM workspaces")
    >>> rows = cursor.fetchall()
    """
    if db_path is None:
        db_path = DB_PATH

    # Make sure the directory tree for the database file exists.
    # e.g.  WorkspaceManager/database/  must be present before SQLite
    # tries to create  tasks.db  inside it.
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Connect.  ``check_same_thread=False`` allows the connection to be
    # shared across threads (needed later for background-task workers).
    conn: sqlite3.Connection = sqlite3.connect(
        str(db_path),
        check_same_thread=False,
    )

    # Use Row factory so query results support both index and name access.
    conn.row_factory = sqlite3.Row

    # --- Pragmas -----------------------------------------------------------
    # WAL (Write-Ahead Logging) lets readers and writers work concurrently.
    conn.execute("PRAGMA journal_mode = WAL;")

    # Without this, ON DELETE CASCADE / SET NULL constraints silently do
    # nothing -- one of SQLite's most surprising defaults.
    conn.execute("PRAGMA foreign_keys = ON;")

    logger.debug("Database connection opened: %s", db_path)
    return conn


# ---------------------------------------------------------------------------
#  Schema Initialisation
# ---------------------------------------------------------------------------


def init_db(conn: sqlite3.Connection | None = None) -> None:
    """Create all application tables if they do not already exist.

    This is **idempotent** -- calling it multiple times is safe because
    every ``CREATE TABLE`` uses ``IF NOT EXISTS``.

    Parameters
    ----------
    conn : sqlite3.Connection | None, optional
        An existing connection to reuse.  When ``None``, a new connection
        is opened (and closed at the end).

    Side Effects
    ------------
    * Creates the four tables: ``workspaces``, ``workspace_items``,
      ``tasks``, and ``command_log``.
    * Calls ``migrate_from_json()`` to import legacy data the first time.

    Example
    -------
    >>> init_db()          # uses default DB_PATH
    >>> init_db(my_conn)   # reuse an open connection
    """
    # Determine whether we own the connection (and should close it later).
    owns_connection: bool = conn is None
    if conn is None:
        conn = get_connection()

    try:
        for ddl in _ALL_TABLES:
            conn.execute(ddl)
        conn.commit()
        logger.info("[+] Database schema initialised successfully.")

        # Attempt a one-time migration from the legacy JSON file.
        migrate_from_json(conn)

    except sqlite3.Error as exc:
        logger.error("[x] Failed to initialise database schema: %s", exc)
        raise
    finally:
        if owns_connection:
            conn.close()


# ---------------------------------------------------------------------------
#  Legacy JSON Migration
# ---------------------------------------------------------------------------


def migrate_from_json(
    conn: sqlite3.Connection,
    json_path: Path | None = None,
) -> None:
    """Import workspaces from the legacy ``workspaces.json`` into SQLite.

    The old JSON format looked like this::

        {
            "MyProject": [
                {"type": "app",  "path": "code", "name": "VS Code"},
                {"type": "url",  "value": "https://github.com", "name": "GitHub"}
            ],
            ...
        }

    For each workspace name the function:

    1. Inserts a row into ``workspaces`` (skipping if the name already
       exists -- this makes the migration idempotent).
    2. For every item in the list, inserts a row into ``workspace_items``
       with the correct ``workspace_id``.

    Parameters
    ----------
    conn : sqlite3.Connection
        An open database connection (tables must already exist).
    json_path : Path | None, optional
        Override the default JSON location.  When ``None``, uses
        ``config.settings.LEGACY_JSON``.

    Notes
    -----
    * If the JSON file does not exist, the function silently returns -- this
      is the normal case for fresh installs.
    * If a workspace name is already present in the DB (from a prior run),
      its items are **not** re-imported, preventing duplicates.
    """
    if json_path is None:
        json_path = LEGACY_JSON

    # Nothing to migrate if the old file is not on disk.
    if not json_path.exists():
        logger.debug("No legacy JSON file found at %s -- skipping migration.", json_path)
        return

    # ------------------------------------------------------------------
    # Read and parse the JSON
    # ------------------------------------------------------------------
    try:
        raw_text: str = json_path.read_text(encoding="utf-8")
        data: dict = json.loads(raw_text)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("[!] Could not read legacy JSON (%s): %s", json_path, exc)
        return

    if not isinstance(data, dict):
        logger.warning("[!] Legacy JSON is not a dict -- skipping migration.")
        return

    migrated_count: int = 0

    for workspace_name, items in data.items():
        # ------------------------------------------------------------------
        # 1.  Ensure the workspace row exists
        # ------------------------------------------------------------------
        # ``INSERT OR IGNORE`` skips if the UNIQUE(name) constraint fires,
        # meaning we will not re-import items for an already-migrated
        # workspace.
        try:
            conn.execute(
                "INSERT OR IGNORE INTO workspaces (name) VALUES (?);",
                (workspace_name,),
            )
        except sqlite3.Error as exc:
            logger.warning(
                "[!] Could not insert workspace '%s': %s",
                workspace_name,
                exc,
            )
            continue

        # Retrieve the workspace_id (whether just inserted or pre-existing).
        cursor = conn.execute(
            "SELECT id FROM workspaces WHERE name = ?;",
            (workspace_name,),
        )
        row = cursor.fetchone()
        if row is None:
            # Should not happen, but guard defensively.
            logger.warning("[!] Workspace '%s' vanished after insert -- skipping.", workspace_name)
            continue

        workspace_id: int = row["id"]

        # Check whether items were already imported for this workspace.
        cursor = conn.execute(
            "SELECT COUNT(*) AS cnt FROM workspace_items WHERE workspace_id = ?;",
            (workspace_id,),
        )
        existing_items: int = cursor.fetchone()["cnt"]
        if existing_items > 0:
            # Items already present -- skip to avoid duplicates.
            logger.debug(
                "Workspace '%s' already has %d items -- skipping import.",
                workspace_name,
                existing_items,
            )
            continue

        # ------------------------------------------------------------------
        # 2.  Import each item into workspace_items
        # ------------------------------------------------------------------
        if not isinstance(items, list):
            logger.warning(
                "[!] Expected a list for workspace '%s', got %s -- skipping items.",
                workspace_name,
                type(items).__name__,
            )
            continue

        for item in items:
            if not isinstance(item, dict):
                continue

            item_type: str = item.get("type", "").lower()
            if item_type not in ("app", "url"):
                logger.debug("Skipping unknown item type '%s' in workspace '%s'.", item_type, workspace_name)
                continue

            # The old JSON used "path" for apps and "value" for URLs.
            if item_type == "app":
                item_value: str = item.get("path", "")
            else:
                item_value = item.get("value", "")

            item_name: str = item.get("name", "")

            if not item_value:
                logger.debug("Skipping item with empty value in workspace '%s'.", workspace_name)
                continue

            try:
                conn.execute(
                    "INSERT INTO workspace_items (workspace_id, type, value, name) "
                    "VALUES (?, ?, ?, ?);",
                    (workspace_id, item_type, item_value, item_name),
                )
            except sqlite3.Error as exc:
                logger.warning(
                    "[!] Could not insert item '%s' for workspace '%s': %s",
                    item_value,
                    workspace_name,
                    exc,
                )

        migrated_count += 1

    # Commit all inserts in one transaction.
    conn.commit()

    if migrated_count > 0:
        logger.info(
            "[+] Migrated %d workspace(s) from legacy JSON into SQLite.",
            migrated_count,
        )
    else:
        logger.debug("JSON migration ran but no new workspaces were imported.")


# ---------------------------------------------------------------------------
#  Command Logging
# ---------------------------------------------------------------------------


def log_command(
    conn: sqlite3.Connection,
    command: str,
    result: str = "",
) -> None:
    """Insert a row into the ``command_log`` table.

    This is called by the Assistant after every voice or text command
    so the GUI dashboard can display a "Recent Activity" feed.

    Parameters
    ----------
    conn : sqlite3.Connection
        An open database connection.
    command : str
        The raw command text (e.g. ``"create workspace IronForge"``).
    result : str, optional
        A short outcome description (e.g. ``"Created workspace id=3"``).
    """
    try:
        conn.execute(
            "INSERT INTO command_log (command, result) VALUES (?, ?);",
            (command, result),
        )
        conn.commit()
        logger.debug("Logged command: '%s'", command)
    except sqlite3.Error as exc:
        logger.warning("Failed to log command '%s': %s", command, exc)


def get_recent_commands(
    conn: sqlite3.Connection,
    limit: int = 20,
) -> list[dict]:
    """Return the most recent entries from ``command_log``.

    Parameters
    ----------
    conn : sqlite3.Connection
        An open database connection.
    limit : int, optional
        Maximum number of rows to return.  Defaults to 20.

    Returns
    -------
    list[dict]
        Each dict has keys ``id``, ``command``, ``result``, ``timestamp``.
    """
    try:
        rows = conn.execute(
            "SELECT * FROM command_log ORDER BY id DESC LIMIT ?;",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as exc:
        logger.warning("Failed to fetch recent commands: %s", exc)
        return []

