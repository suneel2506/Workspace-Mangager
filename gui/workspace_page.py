r"""
============================================================
  workspace_page.py -- Workspace Management Page
============================================================

PURPOSE:
    Tkinter frame that displays a list of workspaces and
    provides CRUD operations: Create, Rename, Open, Delete.

    This is a child frame embedded inside the Dashboard's
    main content area.

DESIGN:
    ┌──────────────────────────────────────────────────────┐
    │  WORKSPACES                          [+ Create]      │
    │  ┌────────────────────────────────────────────────┐  │
    │  │ Name        │ Path          │ Created    │ Act  │  │
    │  │ IronForge   │ C:\Proj\IF    │ 2026-06-21 │ ...  │  │
    │  │ College     │ C:\College    │ 2026-06-20 │ ...  │  │
    │  └────────────────────────────────────────────────┘  │
    │                                                      │
    │  WORKSPACE ITEMS (for selected workspace)            │
    │  ┌────────────────────────────────────────────────┐  │
    │  │ Type │ Value                │ Name             │  │
    │  │ app  │ code                 │ VS Code          │  │
    │  │ url  │ https://github.com   │ GitHub           │  │
    │  └────────────────────────────────────────────────┘  │
    │  [+ Add Item]  [Remove Item]  [Open Workspace]       │
    └──────────────────────────────────────────────────────┘
============================================================
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from workspace.workspace_manager import WorkspaceManager


logger = logging.getLogger("Workspace Automation System")


class WorkspacePage(ttk.Frame):
    """
    Workspace management UI.

    Displays all workspaces in a Treeview, lets the user
    create / rename / delete / open workspaces, and manage
    workspace items (apps + URLs).

    Parameters
    ----------
    parent : tk.Widget
        The parent container (Dashboard's content frame).
    workspace_mgr : WorkspaceManager
        Business-logic layer for workspace CRUD.
    """

    def __init__(self, parent: tk.Widget, workspace_mgr: WorkspaceManager) -> None:
        super().__init__(parent)
        self.ws_mgr = workspace_mgr
        self._selected_ws_id: int | None = None

        self._build_ui()
        self.refresh_workspaces()

    # ── UI Construction ────────────────────────────────────

    def _build_ui(self) -> None:
        """Build all widgets for the workspace page."""

        # -- Header row --
        header = ttk.Frame(self)
        header.pack(fill="x", padx=16, pady=(16, 8))

        ttk.Label(
            header, text="Workspaces", font=("Segoe UI", 16, "bold"),
        ).pack(side="left")

        ttk.Button(
            header, text="+ Create Workspace", command=self._on_create,
        ).pack(side="right")

        # -- Workspace Treeview --
        ws_frame = ttk.Frame(self)
        ws_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        columns = ("name", "path", "created_at")
        self.ws_tree = ttk.Treeview(
            ws_frame, columns=columns, show="headings", height=8,
            selectmode="browse",
        )
        self.ws_tree.heading("name", text="Name")
        self.ws_tree.heading("path", text="Path")
        self.ws_tree.heading("created_at", text="Created")
        self.ws_tree.column("name", width=180)
        self.ws_tree.column("path", width=250)
        self.ws_tree.column("created_at", width=150)

        ws_scroll = ttk.Scrollbar(ws_frame, orient="vertical", command=self.ws_tree.yview)
        self.ws_tree.configure(yscrollcommand=ws_scroll.set)
        self.ws_tree.pack(side="left", fill="both", expand=True)
        ws_scroll.pack(side="right", fill="y")

        self.ws_tree.bind("<<TreeviewSelect>>", self._on_ws_select)

        # -- Workspace action buttons --
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=16, pady=(0, 12))

        ttk.Button(btn_frame, text="Open", command=self._on_open).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Rename", command=self._on_rename).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Delete", command=self._on_delete).pack(side="left", padx=(0, 6))

        # -- Separator --
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=16, pady=4)

        # -- Items header --
        items_header = ttk.Frame(self)
        items_header.pack(fill="x", padx=16, pady=(8, 4))

        self.items_label = ttk.Label(
            items_header, text="Workspace Items (select a workspace above)",
            font=("Segoe UI", 12, "bold"),
        )
        self.items_label.pack(side="left")

        ttk.Button(
            items_header, text="+ Add Item", command=self._on_add_item,
        ).pack(side="right", padx=(6, 0))

        ttk.Button(
            items_header, text="Remove Item", command=self._on_remove_item,
        ).pack(side="right")

        # -- Items Treeview --
        items_frame = ttk.Frame(self)
        items_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        item_cols = ("type", "value", "name")
        self.items_tree = ttk.Treeview(
            items_frame, columns=item_cols, show="headings", height=6,
            selectmode="browse",
        )
        self.items_tree.heading("type", text="Type")
        self.items_tree.heading("value", text="Value")
        self.items_tree.heading("name", text="Display Name")
        self.items_tree.column("type", width=60)
        self.items_tree.column("value", width=300)
        self.items_tree.column("name", width=150)

        items_scroll = ttk.Scrollbar(items_frame, orient="vertical", command=self.items_tree.yview)
        self.items_tree.configure(yscrollcommand=items_scroll.set)
        self.items_tree.pack(side="left", fill="both", expand=True)
        items_scroll.pack(side="right", fill="y")

    # ── Data Refresh ───────────────────────────────────────

    def refresh_workspaces(self) -> None:
        """Reload the workspace list from the database."""
        # Clear existing rows.
        for row in self.ws_tree.get_children():
            self.ws_tree.delete(row)

        workspaces = self.ws_mgr.list_all()
        for ws in workspaces:
            self.ws_tree.insert(
                "", "end",
                iid=str(ws["id"]),
                values=(ws["name"], ws["path"], ws["created_at"]),
            )

        # Clear items view.
        self._selected_ws_id = None
        self._refresh_items()

    def _refresh_items(self) -> None:
        """Reload items for the currently selected workspace."""
        for row in self.items_tree.get_children():
            self.items_tree.delete(row)

        if self._selected_ws_id is None:
            self.items_label.config(text="Workspace Items (select a workspace above)")
            return

        ws = self.ws_mgr.get_by_id(self._selected_ws_id)
        if ws:
            self.items_label.config(text=f"Items in: {ws['name']}")

        items = self.ws_mgr.get_items(self._selected_ws_id)
        for item in items:
            self.items_tree.insert(
                "", "end",
                iid=str(item["id"]),
                values=(item["type"], item["value"], item["name"]),
            )

    # ── Event Handlers ─────────────────────────────────────

    def _on_ws_select(self, _event: tk.Event) -> None:
        """Handle workspace row selection."""
        selection = self.ws_tree.selection()
        if selection:
            self._selected_ws_id = int(selection[0])
            self._refresh_items()

    def _on_create(self) -> None:
        """Prompt for a name and create a new workspace."""
        name = simpledialog.askstring("Create Workspace", "Workspace name:")
        if not name or not name.strip():
            return

        path = simpledialog.askstring("Create Workspace", "Workspace path (optional):", initialvalue="")
        path = path.strip() if path else ""

        try:
            self.ws_mgr.create(name.strip(), path)
            logger.info("Created workspace: %s", name.strip())
            self.refresh_workspaces()
        except ValueError as exc:
            messagebox.showerror("Error", str(exc))

    def _on_rename(self) -> None:
        """Rename the selected workspace."""
        if self._selected_ws_id is None:
            messagebox.showwarning("No Selection", "Select a workspace first.")
            return

        new_name = simpledialog.askstring("Rename Workspace", "New name:")
        if not new_name or not new_name.strip():
            return

        self.ws_mgr.rename(self._selected_ws_id, new_name.strip())
        self.refresh_workspaces()

    def _on_delete(self) -> None:
        """Delete the selected workspace after confirmation."""
        if self._selected_ws_id is None:
            messagebox.showwarning("No Selection", "Select a workspace first.")
            return

        ws = self.ws_mgr.get_by_id(self._selected_ws_id)
        name = ws["name"] if ws else "Unknown"

        if messagebox.askyesno("Confirm Delete", f"Delete workspace '{name}'?\nThis also removes all its items."):
            self.ws_mgr.delete(self._selected_ws_id)
            self.refresh_workspaces()

    def _on_open(self) -> None:
        """Open (launch) all items in the selected workspace."""
        if self._selected_ws_id is None:
            messagebox.showwarning("No Selection", "Select a workspace first.")
            return

        ws = self.ws_mgr.get_by_id(self._selected_ws_id)
        name = ws["name"] if ws else "Unknown"

        success = self.ws_mgr.open(self._selected_ws_id)
        if success:
            messagebox.showinfo("Launched", f"Workspace '{name}' launched successfully!")
        else:
            messagebox.showwarning("Partial Launch", f"Workspace '{name}' launched with some errors.\nCheck logs/app.log.")

    def _on_add_item(self) -> None:
        """Add an app or URL item to the selected workspace."""
        if self._selected_ws_id is None:
            messagebox.showwarning("No Selection", "Select a workspace first.")
            return

        # Pop a small dialog for item type.
        item_type = simpledialog.askstring(
            "Add Item", "Item type ('app' or 'url'):", initialvalue="url",
        )
        if not item_type or item_type.strip().lower() not in ("app", "url"):
            messagebox.showerror("Error", "Type must be 'app' or 'url'.")
            return
        item_type = item_type.strip().lower()

        value = simpledialog.askstring("Add Item", "Value (command/path or URL):")
        if not value or not value.strip():
            return

        name = simpledialog.askstring("Add Item", "Display name (optional):", initialvalue="")
        name = name.strip() if name else ""

        self.ws_mgr.add_item(self._selected_ws_id, item_type, value.strip(), name)
        self._refresh_items()

    def _on_remove_item(self) -> None:
        """Remove the selected item from the workspace."""
        selection = self.items_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Select an item to remove.")
            return

        item_id = int(selection[0])
        if messagebox.askyesno("Confirm Remove", "Remove this item from the workspace?"):
            self.ws_mgr.remove_item(item_id)
            self._refresh_items()
