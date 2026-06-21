"""
============================================================
  dashboard.py -- Main Tkinter Dashboard Window
============================================================

PURPOSE:
    The main application window with:
      • Left sidebar navigation (Dashboard, Workspaces, Tasks,
        Automation, Voice, Logs).
      • Content area that swaps between pages.
      • Dashboard home page with stat cards and recent activity.
      • Automation page with quick-action buttons.
      • Status bar at the bottom.

DESIGN:
    The Dashboard creates a single ``tk.Tk`` root window and
    manages page switching by packing/unpacking ``ttk.Frame``
    instances.  Each page (WorkspacePage, TaskPage, etc.) is a
    self-contained frame that receives manager instances via
    dependency injection.

    ┌──────────────────────────────────────────────────────┐
    │  WORKSPACE AUTOMATION SYSTEM  v3.0     [🎤 Voice]   │
    ├──────────┬───────────────────────────────────────────┤
    │ Sidebar  │  Content Area (swappable pages)           │
    │          │                                           │
    │ ⌂ Home   │  ┌────────┐ ┌────────┐ ┌────────┐       │
    │ ◫ Work.. │  │ Work-  │ │ Pend-  │ │ Comp-  │       │
    │ ☑ Tasks  │  │ spaces │ │ ing    │ │ leted  │       │
    │ ⚡ Auto  │  └────────┘ └────────┘ └────────┘       │
    │          │                                           │
    │ 🎤 Voice │  Recent Activity:                         │
    │ 📋 Logs  │  • Created workspace IronForge            │
    │          │  • Launched Chrome                         │
    ├──────────┴───────────────────────────────────────────┤
    │  Status: Ready                                       │
    └──────────────────────────────────────────────────────┘

FUTURE HOOKS:
    * Replace Tkinter with React/Electron for a modern UI.
    * System tray icon with quick actions.
    * Drag-and-drop workspace item reordering.
============================================================
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import TYPE_CHECKING

from config.settings import (
    GUI_WINDOW_TITLE, GUI_WINDOW_SIZE,
    GUI_MIN_WIDTH, GUI_MIN_HEIGHT, GUI_COLORS,
)
from database.db import get_connection, get_recent_commands
from gui.workspace_page import WorkspacePage
from gui.task_page import TaskPage

if TYPE_CHECKING:
    from core.assistant import Assistant

logger = logging.getLogger("Workspace Automation System")


# ===========================================================
#  Dashboard Application
# ===========================================================

class Dashboard:
    """
    Main application window with sidebar navigation and
    swappable content pages.

    Parameters
    ----------
    assistant : Assistant
        The central orchestrator instance (provides access to
        all managers and subsystems).
    """

    def __init__(self, assistant: Assistant) -> None:
        self.assistant = assistant
        self._conn = get_connection()

        # ── Create the root window ─────────────────────────
        self.root = tk.Tk()
        self.root.title(GUI_WINDOW_TITLE)
        self.root.geometry(GUI_WINDOW_SIZE)
        self.root.minsize(GUI_MIN_WIDTH, GUI_MIN_HEIGHT)
        self.root.configure(bg=GUI_COLORS["content_bg"])

        # ── Style configuration ────────────────────────────
        self._configure_styles()

        # ── Layout: sidebar + content ──────────────────────
        self._build_sidebar()
        self._build_content_area()
        self._build_status_bar()

        # ── Pages ──────────────────────────────────────────
        self._pages: dict[str, ttk.Frame] = {}
        self._current_page: str = ""

        self._create_pages()
        self._show_page("home")

        # ── Wire assistant callbacks ───────────────────────
        self.assistant.on_status(self._update_status)
        self.assistant.on_response(self._on_assistant_response)

        # ── Window close handler ───────────────────────────
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ===========================================================
    #  Style Configuration
    # ===========================================================

    def _configure_styles(self) -> None:
        """Set up ttk styles for a modern appearance."""
        style = ttk.Style()

        # Try to use a modern theme if available.
        available_themes = style.theme_names()
        for theme in ("clam", "vista", "winnative", "default"):
            if theme in available_themes:
                style.theme_use(theme)
                break

        # Custom styles.
        style.configure(
            "Sidebar.TFrame",
            background=GUI_COLORS["sidebar_bg"],
        )
        style.configure(
            "SidebarBtn.TButton",
            font=("Segoe UI", 11),
            padding=(16, 10),
        )
        style.configure(
            "SidebarActive.TButton",
            font=("Segoe UI", 11, "bold"),
            padding=(16, 10),
        )
        style.configure(
            "Card.TFrame",
            background=GUI_COLORS["card_bg"],
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "CardTitle.TLabel",
            font=("Segoe UI", 26, "bold"),
            background=GUI_COLORS["card_bg"],
        )
        style.configure(
            "CardSubtitle.TLabel",
            font=("Segoe UI", 10),
            background=GUI_COLORS["card_bg"],
            foreground=GUI_COLORS["text_secondary"],
        )
        style.configure(
            "PageTitle.TLabel",
            font=("Segoe UI", 18, "bold"),
        )
        style.configure(
            "Status.TLabel",
            font=("Segoe UI", 9),
            foreground=GUI_COLORS["text_secondary"],
        )

    # ===========================================================
    #  Sidebar
    # ===========================================================

    def _build_sidebar(self) -> None:
        """Create the left sidebar with navigation buttons."""
        colors = GUI_COLORS

        self._sidebar = tk.Frame(
            self.root,
            bg=colors["sidebar_bg"],
            width=200,
        )
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        # ── App title ──────────────────────────────────────
        title_frame = tk.Frame(self._sidebar, bg=colors["sidebar_bg"])
        title_frame.pack(fill="x", pady=(20, 24))

        tk.Label(
            title_frame,
            text="⚡ Workspace",
            font=("Segoe UI", 14, "bold"),
            bg=colors["sidebar_bg"],
            fg=colors["sidebar_accent"],
        ).pack(padx=16, anchor="w")

        tk.Label(
            title_frame,
            text="   Automation",
            font=("Segoe UI", 12),
            bg=colors["sidebar_bg"],
            fg=colors["sidebar_fg"],
        ).pack(padx=16, anchor="w")

        # ── Navigation buttons ─────────────────────────────
        self._nav_buttons: dict[str, tk.Button] = {}

        nav_items = [
            ("home",        "⌂  Dashboard"),
            ("workspaces",  "◫  Workspaces"),
            ("tasks",       "☑  Tasks"),
            ("automation",  "⚡  Automation"),
        ]

        for page_name, label in nav_items:
            btn = tk.Button(
                self._sidebar,
                text=label,
                font=("Segoe UI", 11),
                bg=colors["sidebar_bg"],
                fg=colors["sidebar_fg"],
                activebackground=colors["sidebar_active"],
                activeforeground=colors["sidebar_fg"],
                bd=0,
                anchor="w",
                padx=20,
                pady=10,
                cursor="hand2",
                command=lambda p=page_name: self._show_page(p),
            )
            btn.pack(fill="x")
            self._nav_buttons[page_name] = btn

        # ── Spacer ─────────────────────────────────────────
        tk.Frame(self._sidebar, bg=colors["sidebar_bg"]).pack(expand=True, fill="both")

        # ── Bottom actions ─────────────────────────────────
        # Voice toggle.
        self._voice_btn = tk.Button(
            self._sidebar,
            text="🎤  Voice Mode",
            font=("Segoe UI", 10),
            bg=colors["sidebar_bg"],
            fg=colors["sidebar_fg"],
            activebackground=colors["sidebar_active"],
            activeforeground=colors["sidebar_fg"],
            bd=0,
            anchor="w",
            padx=20,
            pady=8,
            cursor="hand2",
            command=self._toggle_voice,
        )
        self._voice_btn.pack(fill="x")

        # Command input button.
        cmd_btn = tk.Button(
            self._sidebar,
            text="⌨  Command Input",
            font=("Segoe UI", 10),
            bg=colors["sidebar_bg"],
            fg=colors["sidebar_fg"],
            activebackground=colors["sidebar_active"],
            activeforeground=colors["sidebar_fg"],
            bd=0,
            anchor="w",
            padx=20,
            pady=8,
            cursor="hand2",
            command=self._open_command_input,
        )
        cmd_btn.pack(fill="x", pady=(0, 16))

    # ===========================================================
    #  Content Area
    # ===========================================================

    def _build_content_area(self) -> None:
        """Create the main content area (right side)."""
        self._content = tk.Frame(
            self.root,
            bg=GUI_COLORS["content_bg"],
        )
        self._content.pack(side="left", fill="both", expand=True)

    # ===========================================================
    #  Status Bar
    # ===========================================================

    def _build_status_bar(self) -> None:
        """Create the bottom status bar."""
        self._status_bar = ttk.Frame(self.root)
        self._status_bar.pack(side="bottom", fill="x")

        self._status_label = ttk.Label(
            self._status_bar,
            text="  Status: Ready",
            style="Status.TLabel",
            anchor="w",
        )
        self._status_label.pack(side="left", padx=8, pady=4)

        self._voice_indicator = ttk.Label(
            self._status_bar,
            text="",
            style="Status.TLabel",
        )
        self._voice_indicator.pack(side="right", padx=8, pady=4)

    # ===========================================================
    #  Page Management
    # ===========================================================

    def _create_pages(self) -> None:
        """Instantiate all content pages."""
        # Home / Dashboard page.
        self._pages["home"] = self._create_home_page()

        # Workspace page.
        self._pages["workspaces"] = WorkspacePage(
            self._content,
            workspace_mgr=self.assistant.workspace_mgr,
        )

        # Task page.
        self._pages["tasks"] = TaskPage(
            self._content,
            task_mgr=self.assistant.task_mgr,
            workspace_mgr=self.assistant.workspace_mgr,
        )

        # Automation page.
        self._pages["automation"] = self._create_automation_page()

    def _show_page(self, page_name: str) -> None:
        """Switch the content area to the named page."""
        if page_name == self._current_page:
            return

        # Hide current page.
        if self._current_page and self._current_page in self._pages:
            self._pages[self._current_page].pack_forget()

        # Show new page.
        if page_name in self._pages:
            self._pages[page_name].pack(fill="both", expand=True)
            self._current_page = page_name

            # Refresh data when switching to a page.
            page = self._pages[page_name]
            if hasattr(page, "refresh_workspaces"):
                page.refresh_workspaces()
            if hasattr(page, "refresh_tasks"):
                page.refresh_tasks()
            if hasattr(page, "refresh"):
                page.refresh()

        # Update sidebar button highlights.
        colors = GUI_COLORS
        for name, btn in self._nav_buttons.items():
            if name == page_name:
                btn.configure(
                    bg=colors["sidebar_active"],
                    fg=colors["sidebar_accent"],
                    font=("Segoe UI", 11, "bold"),
                )
            else:
                btn.configure(
                    bg=colors["sidebar_bg"],
                    fg=colors["sidebar_fg"],
                    font=("Segoe UI", 11),
                )

    # ===========================================================
    #  Home Page
    # ===========================================================

    def _create_home_page(self) -> ttk.Frame:
        """Build the dashboard home page with stat cards and activity."""
        page = ttk.Frame(self._content)

        # ── Header ─────────────────────────────────────────
        header = ttk.Frame(page)
        header.pack(fill="x", padx=24, pady=(24, 16))

        ttk.Label(
            header,
            text="Dashboard",
            style="PageTitle.TLabel",
        ).pack(side="left")

        ttk.Label(
            header,
            text="Welcome to Workspace Automation System",
            style="Status.TLabel",
        ).pack(side="right")

        # ── Stat Cards ─────────────────────────────────────
        cards_frame = ttk.Frame(page)
        cards_frame.pack(fill="x", padx=24, pady=(0, 20))

        # Fetch live stats.
        workspaces = self.assistant.workspace_mgr.list_all()
        all_tasks = self.assistant.task_mgr.list_all()
        pending = [t for t in all_tasks if t["status"] != "completed"]
        completed = [t for t in all_tasks if t["status"] == "completed"]

        cards_data = [
            (str(len(workspaces)), "Workspaces", GUI_COLORS["accent_blue"]),
            (str(len(pending)), "Pending Tasks", GUI_COLORS["accent_yellow"]),
            (str(len(completed)), "Completed", GUI_COLORS["accent_green"]),
            (str(len(all_tasks)), "Total Tasks", GUI_COLORS["sidebar_accent"]),
        ]

        for value, label, accent in cards_data:
            card = tk.Frame(
                cards_frame,
                bg=GUI_COLORS["card_bg"],
                highlightbackground=GUI_COLORS["card_border"],
                highlightthickness=1,
                padx=20,
                pady=16,
            )
            card.pack(side="left", fill="both", expand=True, padx=(0, 12))

            # Accent bar at top.
            accent_bar = tk.Frame(card, bg=accent, height=4)
            accent_bar.pack(fill="x", pady=(0, 8))

            tk.Label(
                card,
                text=value,
                font=("Segoe UI", 28, "bold"),
                bg=GUI_COLORS["card_bg"],
                fg=GUI_COLORS["text_primary"],
            ).pack(anchor="w")

            tk.Label(
                card,
                text=label,
                font=("Segoe UI", 10),
                bg=GUI_COLORS["card_bg"],
                fg=GUI_COLORS["text_secondary"],
            ).pack(anchor="w")

        # ── Recent Activity ────────────────────────────────
        activity_frame = ttk.Frame(page)
        activity_frame.pack(fill="both", expand=True, padx=24, pady=(0, 24))

        ttk.Label(
            activity_frame,
            text="Recent Activity",
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        # Activity list.
        activity_list = tk.Frame(
            activity_frame,
            bg=GUI_COLORS["card_bg"],
            highlightbackground=GUI_COLORS["card_border"],
            highlightthickness=1,
        )
        activity_list.pack(fill="both", expand=True)

        recent = get_recent_commands(self._conn, limit=10)
        if recent:
            for entry in recent:
                row = tk.Frame(activity_list, bg=GUI_COLORS["card_bg"])
                row.pack(fill="x", padx=12, pady=4)

                tk.Label(
                    row,
                    text=f"• {entry['command']}",
                    font=("Segoe UI", 10),
                    bg=GUI_COLORS["card_bg"],
                    fg=GUI_COLORS["text_primary"],
                    anchor="w",
                ).pack(side="left", fill="x", expand=True)

                tk.Label(
                    row,
                    text=entry.get("timestamp", ""),
                    font=("Segoe UI", 9),
                    bg=GUI_COLORS["card_bg"],
                    fg=GUI_COLORS["text_secondary"],
                ).pack(side="right")
        else:
            tk.Label(
                activity_list,
                text="No recent activity.  Try a command!",
                font=("Segoe UI", 10),
                bg=GUI_COLORS["card_bg"],
                fg=GUI_COLORS["text_secondary"],
            ).pack(padx=12, pady=20)

        # Store a reference to refresh later.
        page.refresh = lambda: self._refresh_home(page)  # type: ignore[attr-defined]

        return page

    def _refresh_home(self, page: ttk.Frame) -> None:
        """Rebuild the home page with fresh data."""
        page.pack_forget()
        self._pages["home"] = self._create_home_page()
        if self._current_page == "home":
            self._pages["home"].pack(fill="both", expand=True)

    # ===========================================================
    #  Automation Page
    # ===========================================================

    def _create_automation_page(self) -> ttk.Frame:
        """Build the automation quick-actions page."""
        page = ttk.Frame(self._content)

        # ── Header ─────────────────────────────────────────
        header = ttk.Frame(page)
        header.pack(fill="x", padx=24, pady=(24, 16))

        ttk.Label(
            header,
            text="Automation Tools",
            style="PageTitle.TLabel",
        ).pack(side="left")

        # ── App Launcher Section ───────────────────────────
        app_frame = ttk.LabelFrame(page, text="  Launch Applications  ", padding=16)
        app_frame.pack(fill="x", padx=24, pady=(0, 12))

        apps = self.assistant.app_launcher.list_available()
        app_btn_frame = ttk.Frame(app_frame)
        app_btn_frame.pack(fill="x")

        for i, app_name in enumerate(apps):
            btn = ttk.Button(
                app_btn_frame,
                text=app_name.capitalize(),
                command=lambda a=app_name: self._launch_app(a),
                width=14,
            )
            btn.grid(row=i // 5, column=i % 5, padx=4, pady=4)

        # ── File Operations Section ────────────────────────
        file_frame = ttk.LabelFrame(page, text="  File Operations  ", padding=16)
        file_frame.pack(fill="x", padx=24, pady=(0, 12))

        file_btn_frame = ttk.Frame(file_frame)
        file_btn_frame.pack(fill="x")

        ttk.Button(
            file_btn_frame, text="📂 Organize Downloads",
            command=self._organize_downloads, width=22,
        ).pack(side="left", padx=4, pady=4)

        ttk.Button(
            file_btn_frame, text="📁 Create Folder",
            command=self._create_folder, width=22,
        ).pack(side="left", padx=4, pady=4)

        # ── Browser Section ────────────────────────────────
        browser_frame = ttk.LabelFrame(page, text="  Browser Actions  ", padding=16)
        browser_frame.pack(fill="x", padx=24, pady=(0, 12))

        browser_btn_frame = ttk.Frame(browser_frame)
        browser_btn_frame.pack(fill="x")

        ttk.Button(
            browser_btn_frame, text="🌐 Open URL",
            command=self._open_url, width=22,
        ).pack(side="left", padx=4, pady=4)

        ttk.Button(
            browser_btn_frame, text="🔍 Google Search",
            command=self._google_search, width=22,
        ).pack(side="left", padx=4, pady=4)

        # ── System Controls Section ────────────────────────
        sys_frame = ttk.LabelFrame(page, text="  System Controls  ", padding=16)
        sys_frame.pack(fill="x", padx=24, pady=(0, 12))

        sys_btn_frame = ttk.Frame(sys_frame)
        sys_btn_frame.pack(fill="x")

        ttk.Button(
            sys_btn_frame, text="🔒 Lock Screen",
            command=lambda: self.assistant.system.lock_screen(), width=16,
        ).pack(side="left", padx=4, pady=4)

        ttk.Button(
            sys_btn_frame, text="💤 Sleep Monitor",
            command=lambda: self.assistant.system.sleep_screen(), width=16,
        ).pack(side="left", padx=4, pady=4)

        return page

    # ===========================================================
    #  Action Handlers
    # ===========================================================

    def _launch_app(self, app_name: str) -> None:
        """Launch an application and show result."""
        response = self.assistant.process_text(f"launch {app_name}")
        self._update_status(response)

    def _organize_downloads(self) -> None:
        """Organize downloads folder."""
        response = self.assistant.process_text("organize downloads")
        messagebox.showinfo("Organize Downloads", response)

    def _create_folder(self) -> None:
        """Prompt for path and create folder."""
        path = simpledialog.askstring("Create Folder", "Folder path:")
        if path:
            response = self.assistant.process_text(f"create folder {path}")
            messagebox.showinfo("Create Folder", response)

    def _open_url(self) -> None:
        """Prompt for URL and open it."""
        url = simpledialog.askstring("Open URL", "Enter URL:")
        if url:
            self.assistant.process_text(f"go to {url}")

    def _google_search(self) -> None:
        """Prompt for search query."""
        query = simpledialog.askstring("Google Search", "Search query:")
        if query:
            self.assistant.process_text(f"search {query}")

    def _toggle_voice(self) -> None:
        """Toggle the voice listening loop on/off."""
        if self.assistant.voice_active:
            self.assistant.stop_voice_loop()
            self._voice_btn.configure(text="🎤  Voice Mode")
            self._voice_indicator.configure(text="")
        else:
            if not self.assistant.listener.is_available():
                messagebox.showwarning(
                    "Voice Unavailable",
                    "Speech dependencies are not installed.\n"
                    "Run: pip install SpeechRecognition sounddevice scipy",
                )
                return
            self.assistant.start_voice_loop()
            self._voice_btn.configure(text="🔴  Stop Voice")
            self._voice_indicator.configure(text="🎤 Listening...")

    def _open_command_input(self) -> None:
        """Open a text input dialog for typing commands."""
        command = simpledialog.askstring(
            "Command Input",
            "Type a command (e.g. 'create workspace IronForge'):",
        )
        if command:
            response = self.assistant.process_text(command)
            messagebox.showinfo("Result", response)
            # Refresh home page if visible.
            if self._current_page == "home":
                self._refresh_home(self._pages["home"])

    def _update_status(self, status: str) -> None:
        """Update the status bar text (thread-safe)."""
        try:
            self.root.after(0, lambda: self._status_label.configure(
                text=f"  Status: {status}",
            ))
        except tk.TclError:
            pass  # Window was closed.

    def _on_assistant_response(self, response: str) -> None:
        """Handle assistant response (refresh home if visible)."""
        if self._current_page == "home":
            try:
                self.root.after(100, lambda: self._refresh_home(self._pages["home"]))
            except tk.TclError:
                pass

    def _on_close(self) -> None:
        """Handle window close event."""
        if self.assistant.voice_active:
            self.assistant.stop_voice_loop()
        self.root.destroy()

    # ===========================================================
    #  Run
    # ===========================================================

    def run(self) -> None:
        """Start the Tkinter main loop."""
        logger.info("Dashboard launched.")
        self.root.mainloop()
