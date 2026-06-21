"""
============================================================
  task_page.py -- Task Management Page
============================================================

PURPOSE:
    Tkinter frame that displays tasks in a Treeview with
    full CRUD operations: Add, Complete, Delete, Update
    priority, and filter by status.

    ┌──────────────────────────────────────────────────────┐
    │  TASKS                                  [+ Add Task] │
    │  Filter: [All ▼] [Pending ▼] [High Priority ▼]      │
    │  ┌────────────────────────────────────────────────┐  │
    │  │ Title       │ Priority │ Status  │ Due    │ WS │  │
    │  │ Finish auth │ High     │ Pending │ Jun 25 │ IF │  │
    │  │ Write tests │ Medium   │ Done    │ Jun 22 │ IF │  │
    │  └────────────────────────────────────────────────┘  │
    │  [Complete] [Set Priority] [Delete]                   │
    └──────────────────────────────────────────────────────┘
============================================================
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from workspace.task_manager import TaskManager
    from workspace.workspace_manager import WorkspaceManager


logger = logging.getLogger("Workspace Automation System")


class TaskPage(ttk.Frame):
    """
    Task management UI with filtering and CRUD operations.

    Parameters
    ----------
    parent : tk.Widget
        The parent container (Dashboard's content frame).
    task_mgr : TaskManager
        Business-logic layer for task CRUD.
    workspace_mgr : WorkspaceManager
        Used to resolve workspace names for display.
    """

    def __init__(
        self,
        parent: tk.Widget,
        task_mgr: TaskManager,
        workspace_mgr: WorkspaceManager,
    ) -> None:
        super().__init__(parent)
        self.task_mgr = task_mgr
        self.ws_mgr = workspace_mgr
        self._current_filter: str = "all"  # "all", "pending", "completed"

        self._build_ui()
        self.refresh_tasks()

    # ── UI Construction ────────────────────────────────────

    def _build_ui(self) -> None:
        """Build all widgets for the task page."""

        # -- Header row --
        header = ttk.Frame(self)
        header.pack(fill="x", padx=16, pady=(16, 8))

        ttk.Label(
            header, text="Tasks", font=("Segoe UI", 16, "bold"),
        ).pack(side="left")

        ttk.Button(
            header, text="+ Add Task", command=self._on_add,
        ).pack(side="right")

        # -- Filter row --
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill="x", padx=16, pady=(0, 8))

        ttk.Label(filter_frame, text="Filter:").pack(side="left", padx=(0, 8))

        self.filter_var = tk.StringVar(value="all")
        filters = [("All", "all"), ("Pending", "pending"), ("Completed", "completed")]
        for text, value in filters:
            ttk.Radiobutton(
                filter_frame, text=text, variable=self.filter_var,
                value=value, command=self.refresh_tasks,
            ).pack(side="left", padx=(0, 12))

        # -- Task Treeview --
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        columns = ("title", "priority", "status", "due_date", "workspace")
        self.task_tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", height=14,
            selectmode="browse",
        )
        self.task_tree.heading("title", text="Title")
        self.task_tree.heading("priority", text="Priority")
        self.task_tree.heading("status", text="Status")
        self.task_tree.heading("due_date", text="Due Date")
        self.task_tree.heading("workspace", text="Workspace")
        self.task_tree.column("title", width=250)
        self.task_tree.column("priority", width=80)
        self.task_tree.column("status", width=90)
        self.task_tree.column("due_date", width=100)
        self.task_tree.column("workspace", width=100)

        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=tree_scroll.set)
        self.task_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        # -- Priority color tags --
        self.task_tree.tag_configure("critical", foreground="#dc3545")
        self.task_tree.tag_configure("high", foreground="#fd7e14")
        self.task_tree.tag_configure("medium", foreground="#0d6efd")
        self.task_tree.tag_configure("low", foreground="#6c757d")
        self.task_tree.tag_configure("completed", foreground="#198754")

        # -- Action buttons --
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=16, pady=(0, 16))

        ttk.Button(btn_frame, text="Complete", command=self._on_complete).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Set Priority", command=self._on_set_priority).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Edit", command=self._on_edit).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Delete", command=self._on_delete).pack(side="left", padx=(0, 6))

        # -- Summary bar --
        self.summary_label = ttk.Label(self, text="", font=("Segoe UI", 10))
        self.summary_label.pack(fill="x", padx=16, pady=(0, 12))

    # ── Data Refresh ───────────────────────────────────────

    def refresh_tasks(self) -> None:
        """Reload the task list based on the current filter."""
        for row in self.task_tree.get_children():
            self.task_tree.delete(row)

        filter_val = self.filter_var.get()

        if filter_val == "pending":
            tasks = self.task_mgr.list_pending()
        elif filter_val == "completed":
            tasks = [t for t in self.task_mgr.list_all() if t["status"] == "completed"]
        else:
            tasks = self.task_mgr.list_all()

        # Build a workspace name lookup cache.
        ws_cache: dict[int, str] = {}
        for ws in self.ws_mgr.list_all():
            ws_cache[ws["id"]] = ws["name"]

        for task in tasks:
            ws_name = ws_cache.get(task["workspace_id"], "-") if task["workspace_id"] else "-"
            due = task["due_date"] or "-"
            priority = task["priority"]
            status = task["status"]

            # Choose color tag.
            tag = "completed" if status == "completed" else priority

            self.task_tree.insert(
                "", "end",
                iid=str(task["id"]),
                values=(task["title"], priority.capitalize(), status.capitalize(), due, ws_name),
                tags=(tag,),
            )

        # Update summary.
        all_tasks = self.task_mgr.list_all()
        pending = sum(1 for t in all_tasks if t["status"] != "completed")
        completed = sum(1 for t in all_tasks if t["status"] == "completed")
        self.summary_label.config(
            text=f"Total: {len(all_tasks)}  |  Pending: {pending}  |  Completed: {completed}",
        )

    # ── Event Handlers ─────────────────────────────────────

    def _on_add(self) -> None:
        """Prompt for task details and create a new task."""
        title = simpledialog.askstring("Add Task", "Task title:")
        if not title or not title.strip():
            return

        description = simpledialog.askstring("Add Task", "Description (optional):", initialvalue="")
        description = description.strip() if description else ""

        priority = simpledialog.askstring(
            "Add Task", "Priority (low / medium / high / critical):", initialvalue="medium",
        )
        if priority and priority.strip().lower() not in ("low", "medium", "high", "critical"):
            messagebox.showerror("Error", "Priority must be: low, medium, high, or critical.")
            return
        priority = priority.strip().lower() if priority else "medium"

        due_date = simpledialog.askstring("Add Task", "Due date (YYYY-MM-DD, optional):", initialvalue="")
        due_date = due_date.strip() if due_date else None

        # Optional: assign to a workspace.
        ws_name = simpledialog.askstring("Add Task", "Workspace name (optional):", initialvalue="")
        ws_id: int | None = None
        if ws_name and ws_name.strip():
            ws = self.ws_mgr.get_by_name(ws_name.strip())
            if ws:
                ws_id = ws["id"]
            else:
                messagebox.showwarning("Warning", f"Workspace '{ws_name.strip()}' not found. Task created without workspace.")

        try:
            self.task_mgr.add(
                title=title.strip(),
                workspace_id=ws_id,
                description=description,
                priority=priority,
                due_date=due_date,
            )
            logger.info("Added task: %s", title.strip())
            self.refresh_tasks()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_complete(self) -> None:
        """Mark the selected task as completed."""
        selection = self.task_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Select a task first.")
            return

        task_id = int(selection[0])
        self.task_mgr.complete(task_id)
        self.refresh_tasks()

    def _on_set_priority(self) -> None:
        """Change the priority of the selected task."""
        selection = self.task_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Select a task first.")
            return

        task_id = int(selection[0])
        priority = simpledialog.askstring(
            "Set Priority", "New priority (low / medium / high / critical):",
        )
        if not priority or priority.strip().lower() not in ("low", "medium", "high", "critical"):
            messagebox.showerror("Error", "Priority must be: low, medium, high, or critical.")
            return

        self.task_mgr.set_priority(task_id, priority.strip().lower())
        self.refresh_tasks()

    def _on_edit(self) -> None:
        """Edit the title/description of the selected task."""
        selection = self.task_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Select a task first.")
            return

        task_id = int(selection[0])
        task = self.task_mgr.get_by_id(task_id)
        if not task:
            return

        new_title = simpledialog.askstring(
            "Edit Task", "New title:", initialvalue=task["title"],
        )
        if new_title and new_title.strip():
            self.task_mgr.update(task_id, title=new_title.strip())

        new_desc = simpledialog.askstring(
            "Edit Task", "New description:", initialvalue=task["description"],
        )
        if new_desc is not None:
            self.task_mgr.update(task_id, description=new_desc.strip())

        self.refresh_tasks()

    def _on_delete(self) -> None:
        """Delete the selected task after confirmation."""
        selection = self.task_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Select a task first.")
            return

        task_id = int(selection[0])
        task = self.task_mgr.get_by_id(task_id)
        title = task["title"] if task else "Unknown"

        if messagebox.askyesno("Confirm Delete", f"Delete task '{title}'?"):
            self.task_mgr.delete(task_id)
            self.refresh_tasks()
