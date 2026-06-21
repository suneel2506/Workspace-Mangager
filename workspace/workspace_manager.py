"""
============================================================
  workspace_manager.py -- Workspace CRUD & Launcher
============================================================

PURPOSE:
    Provides the ``WorkspaceManager`` class which encapsulates
    every operation the application can perform on *workspaces*
    and their *items* (apps / URLs):

        * CREATE / DELETE / RENAME a workspace
        * Retrieve a single workspace or list all workspaces
        * ADD / REMOVE items to a workspace
        * OPEN a workspace (launch all its items)

DATA FLOW:
    +-----------+      SQL      +----------+
    | Workspace | <-----------> | SQLite   |
    | Manager   |               | database |
    +-----------+               +----------+
         |
         |  launch
         v
    +-------------------+
    | AppLauncher /     |
    | BrowserTasks      |
    +-------------------+

DATABASE SCHEMA (expected):
    workspaces
    ----------
    id          INTEGER PRIMARY KEY AUTOINCREMENT
    name        TEXT    NOT NULL UNIQUE
    path        TEXT    DEFAULT ''
    created_at  TEXT    DEFAULT CURRENT_TIMESTAMP

    workspace_items
    ---------------
    id            INTEGER PRIMARY KEY AUTOINCREMENT
    workspace_id  INTEGER NOT NULL  (FK -> workspaces.id)
    item_type     TEXT    NOT NULL   ('app' | 'url')
    value         TEXT    NOT NULL   (exe path or URL)
    name          TEXT    DEFAULT ''
    created_at    TEXT    DEFAULT CURRENT_TIMESTAMP

FUTURE HOOKS:
    * Workspace export/import (JSON, YAML).
    * Workspace duplication ("clone").
    * Track PIDs of launched apps so they can be closed later.
    * Tagging / categorising workspaces.
============================================================
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

# ── Internal imports ──────────────────────────────────────
# database.db supplies a shared SQLite connection.
# automations.* supply launchers that are called by open().
from database.db import get_connection
from automations.app_launcher import AppLauncher
from automations.browser_tasks import BrowserTasks

# ── Logger ────────────────────────────────────────────────
# All managers share the application-wide logger so that log
# output ends up in one consistent place.
logger: logging.Logger = logging.getLogger("Workspace Automation System")


class WorkspaceManager:
    """
    CRUD manager for workspaces and their items.

    Every public method:
      1. Validates inputs.
      2. Executes a single SQL statement (or a small batch).
      3. Logs the outcome at INFO / WARNING / ERROR level.
      4. Returns a simple Python type (int, bool, dict, list).

    Attributes
    ----------
    conn : sqlite3.Connection
        Shared database connection with ``Row`` row-factory,
        so every fetched row behaves like a dict.

    Usage
    -----
        wm = WorkspaceManager()
        ws_id = wm.create("coding", path="C:/projects")
        wm.add_item(ws_id, "app", "code", name="VS Code")
        wm.add_item(ws_id, "url", "https://github.com", name="GitHub")
        wm.open(ws_id)
    """

    # ── Constructor ───────────────────────────────────────
    def __init__(self) -> None:
        """
        Initialise the manager by obtaining a database connection.

        The connection's ``row_factory`` is set to ``sqlite3.Row``
        so that fetched rows support both index-based and
        key-based access (``row["name"]``).
        """
        self.conn: sqlite3.Connection = get_connection()
        # sqlite3.Row lets us access columns by name:
        #   row["name"]  instead of  row[1]
        self.conn.row_factory = sqlite3.Row
        logger.info("WorkspaceManager initialised.")

    # ===========================================================
    #  WORKSPACE CRUD
    # ===========================================================

    def create(self, name: str, path: str = "") -> int:
        """
        Insert a new workspace into the database.

        Parameters
        ----------
        name : str
            Unique, human-readable workspace name (e.g. "coding").
        path : str, optional
            An optional filesystem path associated with the
            workspace (e.g. a project directory).

        Returns
        -------
        int
            The ``id`` of the newly created workspace row.

        Raises
        ------
        ValueError
            If a workspace with the same *name* already exists
            (case-insensitive check).
        sqlite3.Error
            On any unexpected database failure.
        """
        # ── Guard: duplicate name ─────────────────────────
        if self.get_by_name(name) is not None:
            logger.warning(
                "Workspace creation blocked -- duplicate name: '%s'", name,
            )
            raise ValueError(
                f"A workspace named '{name}' already exists.  "
                "Choose a different name or delete the existing one first."
            )

        # ── INSERT ────────────────────────────────────────
        try:
            cursor: sqlite3.Cursor = self.conn.execute(
                "INSERT INTO workspaces (name, path) VALUES (?, ?)",
                (name.strip(), path.strip()),
            )
            self.conn.commit()

            new_id: int = cursor.lastrowid  # type: ignore[assignment]
            logger.info(
                "Workspace created: id=%d, name='%s', path='%s'",
                new_id, name, path,
            )
            return new_id

        except sqlite3.Error:
            self.conn.rollback()
            logger.exception("Failed to create workspace '%s'.", name)
            raise

    # ----------------------------------------------------------
    def delete(self, workspace_id: int) -> bool:
        """
        Delete a workspace (and its items) by primary key.

        Parameters
        ----------
        workspace_id : int
            The ``id`` of the workspace to remove.

        Returns
        -------
        bool
            ``True`` if a row was actually deleted, ``False`` if
            no workspace with that id existed.
        """
        try:
            # Delete child items first (referential integrity).
            self.conn.execute(
                "DELETE FROM workspace_items WHERE workspace_id = ?",
                (workspace_id,),
            )
            cursor: sqlite3.Cursor = self.conn.execute(
                "DELETE FROM workspaces WHERE id = ?",
                (workspace_id,),
            )
            self.conn.commit()

            deleted: bool = cursor.rowcount > 0
            if deleted:
                logger.info("Workspace deleted: id=%d", workspace_id)
            else:
                logger.warning(
                    "Workspace delete -- no row with id=%d", workspace_id,
                )
            return deleted

        except sqlite3.Error:
            self.conn.rollback()
            logger.exception(
                "Failed to delete workspace id=%d.", workspace_id,
            )
            raise

    # ----------------------------------------------------------
    def rename(self, workspace_id: int, new_name: str) -> bool:
        """
        Update the name of an existing workspace.

        Parameters
        ----------
        workspace_id : int
            The workspace to rename.
        new_name : str
            The desired new name.

        Returns
        -------
        bool
            ``True`` if the row was updated, ``False`` if no
            workspace with that id exists.
        """
        try:
            cursor: sqlite3.Cursor = self.conn.execute(
                "UPDATE workspaces SET name = ? WHERE id = ?",
                (new_name.strip(), workspace_id),
            )
            self.conn.commit()

            updated: bool = cursor.rowcount > 0
            if updated:
                logger.info(
                    "Workspace renamed: id=%d -> '%s'",
                    workspace_id, new_name,
                )
            else:
                logger.warning(
                    "Workspace rename -- no row with id=%d", workspace_id,
                )
            return updated

        except sqlite3.Error:
            self.conn.rollback()
            logger.exception(
                "Failed to rename workspace id=%d.", workspace_id,
            )
            raise

    # ===========================================================
    #  WORKSPACE QUERIES
    # ===========================================================

    def get_by_id(self, workspace_id: int) -> dict[str, Any] | None:
        """
        Fetch a single workspace by its primary key.

        Parameters
        ----------
        workspace_id : int
            The ``id`` to look up.

        Returns
        -------
        dict | None
            A dict with keys ``id``, ``name``, ``path``,
            ``created_at`` -- or ``None`` if not found.
        """
        try:
            row: sqlite3.Row | None = self.conn.execute(
                "SELECT * FROM workspaces WHERE id = ?",
                (workspace_id,),
            ).fetchone()

            if row is None:
                logger.debug("get_by_id: no workspace with id=%d", workspace_id)
                return None

            return dict(row)

        except sqlite3.Error:
            logger.exception(
                "Failed to fetch workspace id=%d.", workspace_id,
            )
            raise

    # ----------------------------------------------------------
    def get_by_name(self, name: str) -> dict[str, Any] | None:
        """
        Case-insensitive lookup of a workspace by name.

        SQLite's ``LOWER()`` function is used so that "Coding",
        "coding", and "CODING" all match.

        Parameters
        ----------
        name : str
            The workspace name to search for.

        Returns
        -------
        dict | None
            Workspace dict or ``None``.
        """
        try:
            row: sqlite3.Row | None = self.conn.execute(
                "SELECT * FROM workspaces WHERE LOWER(name) = LOWER(?)",
                (name.strip(),),
            ).fetchone()

            if row is None:
                logger.debug("get_by_name: no workspace named '%s'", name)
                return None

            return dict(row)

        except sqlite3.Error:
            logger.exception(
                "Failed to fetch workspace named '%s'.", name,
            )
            raise

    # ----------------------------------------------------------
    def list_all(self) -> list[dict[str, Any]]:
        """
        Return every workspace in the database, ordered by name.

        Returns
        -------
        list[dict]
            A (possibly empty) list of workspace dicts.
        """
        try:
            rows: list[sqlite3.Row] = self.conn.execute(
                "SELECT * FROM workspaces ORDER BY name",
            ).fetchall()

            logger.debug("list_all: returned %d workspace(s).", len(rows))
            return [dict(r) for r in rows]

        except sqlite3.Error:
            logger.exception("Failed to list workspaces.")
            raise

    # ===========================================================
    #  WORKSPACE ITEMS
    # ===========================================================

    def add_item(
        self,
        workspace_id: int,
        item_type: str,
        value: str,
        name: str = "",
    ) -> int:
        """
        Attach an app or URL to a workspace.

        Parameters
        ----------
        workspace_id : int
            The parent workspace.
        item_type : str
            ``"app"`` or ``"url"``.
        value : str
            For apps: the executable path or command.
            For URLs: the web address.
        name : str, optional
            A human-friendly display name (e.g. "VS Code").

        Returns
        -------
        int
            The ``id`` of the new ``workspace_items`` row.

        Raises
        ------
        ValueError
            If ``item_type`` is not ``"app"`` or ``"url"``.
        sqlite3.Error
            On any database failure.
        """
        # ── Validate item_type ────────────────────────────
        allowed_types: tuple[str, ...] = ("app", "url")
        if item_type.lower() not in allowed_types:
            raise ValueError(
                f"item_type must be one of {allowed_types}, "
                f"got '{item_type}'."
            )

        try:
            cursor: sqlite3.Cursor = self.conn.execute(
                """
                INSERT INTO workspace_items
                    (workspace_id, item_type, value, name)
                VALUES (?, ?, ?, ?)
                """,
                (workspace_id, item_type.lower(), value.strip(), name.strip()),
            )
            self.conn.commit()

            new_id: int = cursor.lastrowid  # type: ignore[assignment]
            logger.info(
                "Item added: id=%d, workspace=%d, type='%s', value='%s'",
                new_id, workspace_id, item_type, value,
            )
            return new_id

        except sqlite3.Error:
            self.conn.rollback()
            logger.exception(
                "Failed to add item to workspace id=%d.", workspace_id,
            )
            raise

    # ----------------------------------------------------------
    def remove_item(self, item_id: int) -> bool:
        """
        Remove a single item from a workspace.

        Parameters
        ----------
        item_id : int
            The primary key of the ``workspace_items`` row.

        Returns
        -------
        bool
            ``True`` if the row existed and was deleted.
        """
        try:
            cursor: sqlite3.Cursor = self.conn.execute(
                "DELETE FROM workspace_items WHERE id = ?",
                (item_id,),
            )
            self.conn.commit()

            deleted: bool = cursor.rowcount > 0
            if deleted:
                logger.info("Item removed: id=%d", item_id)
            else:
                logger.warning("Item remove -- no row with id=%d", item_id)
            return deleted

        except sqlite3.Error:
            self.conn.rollback()
            logger.exception("Failed to remove item id=%d.", item_id)
            raise

    # ----------------------------------------------------------
    def get_items(self, workspace_id: int) -> list[dict[str, Any]]:
        """
        Retrieve all items belonging to a workspace.

        Parameters
        ----------
        workspace_id : int
            The parent workspace.

        Returns
        -------
        list[dict]
            A list of item dicts, each with keys ``id``,
            ``workspace_id``, ``item_type``, ``value``, ``name``,
            ``created_at``.
        """
        try:
            rows: list[sqlite3.Row] = self.conn.execute(
                """
                SELECT * FROM workspace_items
                WHERE workspace_id = ?
                ORDER BY id
                """,
                (workspace_id,),
            ).fetchall()

            logger.debug(
                "get_items: workspace=%d returned %d item(s).",
                workspace_id, len(rows),
            )
            return [dict(r) for r in rows]

        except sqlite3.Error:
            logger.exception(
                "Failed to fetch items for workspace id=%d.", workspace_id,
            )
            raise

    # ===========================================================
    #  OPEN (LAUNCH) A WORKSPACE
    # ===========================================================

    def open(self, workspace_id: int) -> bool:
        """
        Launch every item in a workspace.

        * Items with ``item_type == 'app'`` are opened via
          ``AppLauncher().launch_by_path(value)``.
        * Items with ``item_type == 'url'`` are opened via
          ``BrowserTasks().open_url(value)``.

        Errors on individual items are caught and logged so that
        one broken shortcut does not prevent the rest from
        launching.

        Parameters
        ----------
        workspace_id : int
            The workspace whose items should be launched.

        Returns
        -------
        bool
            ``True`` if *all* items launched successfully,
            ``False`` if any item failed (or the workspace was
            empty / not found).
        """
        # ── Resolve the workspace ─────────────────────────
        workspace: dict[str, Any] | None = self.get_by_id(workspace_id)
        if workspace is None:
            logger.error(
                "Cannot open workspace -- id=%d not found.", workspace_id,
            )
            return False

        workspace_name: str = workspace["name"]

        # ── Fetch items ───────────────────────────────────
        items: list[dict[str, Any]] = self.get_items(workspace_id)
        if not items:
            logger.warning(
                "Workspace '%s' (id=%d) has no items to launch.",
                workspace_name, workspace_id,
            )
            return False

        # ── Instantiate launchers once ────────────────────
        app_launcher: AppLauncher = AppLauncher()
        browser_tasks: BrowserTasks = BrowserTasks()

        success_count: int = 0
        fail_count: int = 0

        for item in items:
            item_type: str = item.get("item_type", "")
            value: str = item.get("value", "")
            display_name: str = item.get("name", "") or value

            try:
                if item_type == "app":
                    app_launcher.launch_by_path(value)
                    logger.info(
                        "[+] Launched app: '%s' (%s)", display_name, value,
                    )

                elif item_type == "url":
                    browser_tasks.open_url(value)
                    logger.info(
                        "[+] Opened URL: '%s' (%s)", display_name, value,
                    )

                else:
                    # Unknown type -- skip gracefully.
                    logger.warning(
                        "[!] Skipped item id=%d -- unknown type '%s'.",
                        item.get("id", -1), item_type,
                    )
                    fail_count += 1
                    continue

                success_count += 1

            except Exception:
                # Catch *everything* so one bad item cannot
                # prevent the remaining items from launching.
                fail_count += 1
                logger.exception(
                    "[x] Failed to launch '%s' (%s).", display_name, value,
                )

        # ── Summary log ───────────────────────────────────
        total: int = len(items)
        all_ok: bool = fail_count == 0
        logger.info(
            "Workspace '%s' opened: %d/%d succeeded, %d failed.",
            workspace_name, success_count, total, fail_count,
        )
        return all_ok
