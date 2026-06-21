"""
============================================================
  task_manager.py -- Task CRUD & Filtering
============================================================

PURPOSE:
    Provides the ``TaskManager`` class for creating, updating,
    completing, deleting, and querying *tasks*.

    Tasks are lightweight to-do items that can optionally be
    linked to a workspace.  They carry a priority level and a
    status that progresses from ``"pending"`` to ``"completed"``.

DATA FLOW:
    +-----------+      SQL      +----------+
    |   Task    | <-----------> | SQLite   |
    |  Manager  |               | database |
    +-----------+               +----------+

DATABASE SCHEMA (expected):
    tasks
    -----
    id            INTEGER PRIMARY KEY AUTOINCREMENT
    title         TEXT    NOT NULL
    description   TEXT    DEFAULT ''
    priority      TEXT    DEFAULT 'medium'   -- low|medium|high|critical
    status        TEXT    DEFAULT 'pending'  -- pending|completed
    due_date      TEXT    DEFAULT NULL       -- ISO-8601 date string
    workspace_id  INTEGER DEFAULT NULL       -- FK -> workspaces.id
    created_at    TEXT    DEFAULT CURRENT_TIMESTAMP

DESIGN NOTES:
    * Every public method validates inputs, runs SQL, and logs.
    * ``sqlite3.Row`` is used so results behave like dicts.
    * ``update()`` accepts arbitrary keyword arguments so the
      caller can patch any combination of fields in one call.
    * All list_* helpers return ``list[dict]`` -- easy to
      serialise to JSON for a future REST API.

FUTURE HOOKS:
    * Recurring tasks (cron-style repeat rules).
    * Sub-tasks / checklist items.
    * Due-date reminders via system notifications.
    * Bulk status transitions (archive all completed).
============================================================
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

# ── Internal imports ──────────────────────────────────────
from database.db import get_connection

# ── Logger ────────────────────────────────────────────────
logger: logging.Logger = logging.getLogger("Workspace Automation System")

# ── Constants ─────────────────────────────────────────────
# Allowed priority values -- kept as a module-level tuple so
# both the class and potential callers can reference it.
VALID_PRIORITIES: tuple[str, ...] = ("low", "medium", "high", "critical")

# Columns that callers are allowed to patch via update().
# This whitelist prevents SQL-injection through crafted
# keyword-argument names.
UPDATABLE_FIELDS: frozenset[str] = frozenset(
    {
        "title",
        "description",
        "priority",
        "status",
        "due_date",
        "workspace_id",
    }
)


class TaskManager:
    """
    CRUD manager for tasks.

    Provides methods to add, delete, complete, update, and
    query tasks stored in the ``tasks`` table.

    Attributes
    ----------
    conn : sqlite3.Connection
        Shared database connection configured with
        ``sqlite3.Row`` as its row factory.

    Usage
    -----
        tm = TaskManager()
        task_id = tm.add("Review PR #42", workspace_id=1, priority="high")
        tm.complete(task_id)
        pending = tm.list_pending()
    """

    # ── Constructor ───────────────────────────────────────
    def __init__(self) -> None:
        """
        Obtain a database connection and configure it for
        dict-style row access.
        """
        self.conn: sqlite3.Connection = get_connection()
        self.conn.row_factory = sqlite3.Row
        logger.info("TaskManager initialised.")

    # ===========================================================
    #  CREATE / DELETE
    # ===========================================================

    def add(
        self,
        title: str,
        workspace_id: int | None = None,
        description: str = "",
        priority: str = "medium",
        due_date: str | None = None,
    ) -> int:
        """
        Insert a new task.

        Parameters
        ----------
        title : str
            Short summary of the task (required).
        workspace_id : int | None, optional
            Link the task to a workspace.  ``None`` means the
            task is standalone.
        description : str, optional
            Longer description or notes.
        priority : str, optional
            One of ``"low"``, ``"medium"``, ``"high"``,
            ``"critical"``.  Defaults to ``"medium"``.
        due_date : str | None, optional
            ISO-8601 date string (e.g. ``"2026-07-01"``).

        Returns
        -------
        int
            The ``id`` of the newly created task.

        Raises
        ------
        ValueError
            If ``priority`` is not in the allowed set.
        sqlite3.Error
            On any database failure.
        """
        # ── Validate priority ─────────────────────────────
        priority_lower: str = priority.strip().lower()
        if priority_lower not in VALID_PRIORITIES:
            raise ValueError(
                f"priority must be one of {VALID_PRIORITIES}, "
                f"got '{priority}'."
            )

        try:
            cursor: sqlite3.Cursor = self.conn.execute(
                """
                INSERT INTO tasks
                    (title, description, priority, status,
                     due_date, workspace_id)
                VALUES (?, ?, ?, 'pending', ?, ?)
                """,
                (
                    title.strip(),
                    description.strip(),
                    priority_lower,
                    due_date,
                    workspace_id,
                ),
            )
            self.conn.commit()

            new_id: int = cursor.lastrowid  # type: ignore[assignment]
            logger.info(
                "Task created: id=%d, title='%s', priority='%s'",
                new_id, title, priority_lower,
            )
            return new_id

        except sqlite3.Error:
            self.conn.rollback()
            logger.exception("Failed to create task '%s'.", title)
            raise

    # ----------------------------------------------------------
    def delete(self, task_id: int) -> bool:
        """
        Permanently remove a task.

        Parameters
        ----------
        task_id : int
            The primary key of the task to delete.

        Returns
        -------
        bool
            ``True`` if a row was actually removed.
        """
        try:
            cursor: sqlite3.Cursor = self.conn.execute(
                "DELETE FROM tasks WHERE id = ?",
                (task_id,),
            )
            self.conn.commit()

            deleted: bool = cursor.rowcount > 0
            if deleted:
                logger.info("Task deleted: id=%d", task_id)
            else:
                logger.warning("Task delete -- no row with id=%d", task_id)
            return deleted

        except sqlite3.Error:
            self.conn.rollback()
            logger.exception("Failed to delete task id=%d.", task_id)
            raise

    # ===========================================================
    #  STATUS & PRIORITY HELPERS
    # ===========================================================

    def complete(self, task_id: int) -> bool:
        """
        Mark a task as completed.

        This is a convenience wrapper around ``update()`` that
        sets ``status = 'completed'``.

        Parameters
        ----------
        task_id : int
            The task to mark as done.

        Returns
        -------
        bool
            ``True`` if the row was updated.
        """
        return self.update(task_id, status="completed")

    # ----------------------------------------------------------
    def set_priority(self, task_id: int, priority: str) -> bool:
        """
        Change a task's priority.

        Parameters
        ----------
        task_id : int
            The task to update.
        priority : str
            Must be one of ``"low"``, ``"medium"``, ``"high"``,
            ``"critical"``.

        Returns
        -------
        bool
            ``True`` if the row was updated.

        Raises
        ------
        ValueError
            If *priority* is not in the allowed set.
        """
        priority_lower: str = priority.strip().lower()
        if priority_lower not in VALID_PRIORITIES:
            raise ValueError(
                f"priority must be one of {VALID_PRIORITIES}, "
                f"got '{priority}'."
            )
        return self.update(task_id, priority=priority_lower)

    # ===========================================================
    #  GENERIC UPDATE
    # ===========================================================

    def update(self, task_id: int, **kwargs: Any) -> bool:
        """
        Patch one or more fields of a task in a single UPDATE.

        Allowed keyword arguments (any combination):
            ``title``, ``description``, ``priority``, ``status``,
            ``due_date``, ``workspace_id``.

        Parameters
        ----------
        task_id : int
            The task to update.
        **kwargs : Any
            Field-name / value pairs to set.

        Returns
        -------
        bool
            ``True`` if the row was updated.

        Raises
        ------
        ValueError
            If no keyword arguments are provided, or if an
            unknown field name is passed (prevents SQL injection
            through crafted kwargs).
        sqlite3.Error
            On any database failure.

        Examples
        --------
        >>> tm.update(1, title="New title", priority="high")
        True
        >>> tm.update(2, status="completed", due_date=None)
        True
        """
        if not kwargs:
            raise ValueError(
                "update() requires at least one keyword argument "
                "(e.g. title='...', priority='high')."
            )

        # ── Whitelist check ───────────────────────────────
        # Only allow known column names to reach the SQL
        # statement.  This is a safety net against injection.
        bad_keys: set[str] = set(kwargs.keys()) - UPDATABLE_FIELDS
        if bad_keys:
            raise ValueError(
                f"Unknown field(s): {bad_keys}.  "
                f"Allowed: {sorted(UPDATABLE_FIELDS)}"
            )

        # ── Build SET clause dynamically ──────────────────
        # Example:  "title = ?, priority = ?"
        set_parts: list[str] = [f"{col} = ?" for col in kwargs]
        set_clause: str = ", ".join(set_parts)

        # Corresponding parameter values, with task_id last
        # (for the WHERE clause).
        params: list[Any] = list(kwargs.values()) + [task_id]

        try:
            cursor: sqlite3.Cursor = self.conn.execute(
                f"UPDATE tasks SET {set_clause} WHERE id = ?",
                params,
            )
            self.conn.commit()

            updated: bool = cursor.rowcount > 0
            if updated:
                logger.info(
                    "Task updated: id=%d, fields=%s", task_id, list(kwargs.keys()),
                )
            else:
                logger.warning("Task update -- no row with id=%d", task_id)
            return updated

        except sqlite3.Error:
            self.conn.rollback()
            logger.exception("Failed to update task id=%d.", task_id)
            raise

    # ===========================================================
    #  QUERIES
    # ===========================================================

    def get_by_id(self, task_id: int) -> dict[str, Any] | None:
        """
        Fetch a single task by primary key.

        Parameters
        ----------
        task_id : int
            The ``id`` to look up.

        Returns
        -------
        dict | None
            A task dict, or ``None`` if not found.
        """
        try:
            row: sqlite3.Row | None = self.conn.execute(
                "SELECT * FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()

            if row is None:
                logger.debug("get_by_id: no task with id=%d", task_id)
                return None

            return dict(row)

        except sqlite3.Error:
            logger.exception("Failed to fetch task id=%d.", task_id)
            raise

    # ----------------------------------------------------------
    def list_all(self) -> list[dict[str, Any]]:
        """
        Return every task, ordered by creation date (newest first).

        Returns
        -------
        list[dict]
            A (possibly empty) list of task dicts.
        """
        try:
            rows: list[sqlite3.Row] = self.conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC",
            ).fetchall()

            logger.debug("list_all: returned %d task(s).", len(rows))
            return [dict(r) for r in rows]

        except sqlite3.Error:
            logger.exception("Failed to list all tasks.")
            raise

    # ----------------------------------------------------------
    def list_pending(self) -> list[dict[str, Any]]:
        """
        Return tasks whose status is *not* ``"completed"``.

        Results are ordered by priority weight (critical first)
        then by creation date.

        Returns
        -------
        list[dict]
            Pending / in-progress tasks.
        """
        try:
            rows: list[sqlite3.Row] = self.conn.execute(
                """
                SELECT * FROM tasks
                WHERE status != 'completed'
                ORDER BY
                    CASE priority
                        WHEN 'critical' THEN 1
                        WHEN 'high'     THEN 2
                        WHEN 'medium'   THEN 3
                        WHEN 'low'      THEN 4
                        ELSE 5
                    END,
                    created_at DESC
                """,
            ).fetchall()

            logger.debug("list_pending: returned %d task(s).", len(rows))
            return [dict(r) for r in rows]

        except sqlite3.Error:
            logger.exception("Failed to list pending tasks.")
            raise

    # ----------------------------------------------------------
    def list_by_workspace(self, workspace_id: int) -> list[dict[str, Any]]:
        """
        Return all tasks linked to a specific workspace.

        Parameters
        ----------
        workspace_id : int
            The workspace to filter by.

        Returns
        -------
        list[dict]
            Tasks belonging to that workspace.
        """
        try:
            rows: list[sqlite3.Row] = self.conn.execute(
                """
                SELECT * FROM tasks
                WHERE workspace_id = ?
                ORDER BY created_at DESC
                """,
                (workspace_id,),
            ).fetchall()

            logger.debug(
                "list_by_workspace: workspace=%d returned %d task(s).",
                workspace_id, len(rows),
            )
            return [dict(r) for r in rows]

        except sqlite3.Error:
            logger.exception(
                "Failed to list tasks for workspace id=%d.", workspace_id,
            )
            raise

    # ----------------------------------------------------------
    def list_by_priority(self, priority: str) -> list[dict[str, Any]]:
        """
        Return all tasks with a given priority level.

        Parameters
        ----------
        priority : str
            One of ``"low"``, ``"medium"``, ``"high"``,
            ``"critical"``.

        Returns
        -------
        list[dict]
            Tasks matching the requested priority.

        Raises
        ------
        ValueError
            If *priority* is not in the allowed set.
        """
        priority_lower: str = priority.strip().lower()
        if priority_lower not in VALID_PRIORITIES:
            raise ValueError(
                f"priority must be one of {VALID_PRIORITIES}, "
                f"got '{priority}'."
            )

        try:
            rows: list[sqlite3.Row] = self.conn.execute(
                """
                SELECT * FROM tasks
                WHERE priority = ?
                ORDER BY created_at DESC
                """,
                (priority_lower,),
            ).fetchall()

            logger.debug(
                "list_by_priority: priority='%s' returned %d task(s).",
                priority_lower, len(rows),
            )
            return [dict(r) for r in rows]

        except sqlite3.Error:
            logger.exception(
                "Failed to list tasks with priority '%s'.", priority_lower,
            )
            raise
