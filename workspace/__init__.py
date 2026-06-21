"""
============================================================
  workspace/ package -- Business Logic for Workspaces & Tasks
============================================================

This package contains the data-layer managers that sit between
the database and the rest of the application.  Each manager
owns a single domain entity:

    workspace_manager.py
        CRUD operations on workspaces and their items
        (apps, URLs).  Also handles "open workspace" by
        delegating to the automations layer.

    task_manager.py
        CRUD operations on tasks -- create, complete, update,
        filter by priority / status / workspace.

Both managers obtain their database connection from
``database.db.get_connection()`` and use ``sqlite3.Row`` for
dict-like row access, keeping the rest of the code decoupled
from raw SQL.

FUTURE HOOKS:
    * Workspace templates (clone a workspace definition).
    * Bulk import/export of tasks (CSV / JSON).
    * Undo / soft-delete support.
============================================================
"""
