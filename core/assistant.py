"""
============================================================
  assistant.py -- Central Orchestrator
============================================================

PURPOSE:
    The ``Assistant`` is the single entry point that ties every
    subsystem together:

        ┌─────────────┐
        │  Assistant   │
        └──┬──┬──┬──┬─┘
           │  │  │  │
           ▼  ▼  ▼  ▼
        Listener  Speaker  CommandParser  AIManager
           │
           ▼
        ┌────────────────────────────────────┐
        │         Action Dispatch            │
        ├───────┬────────┬──────┬────────────┤
        │ Work- │  Task  │ App  │  Browser   │
        │ space │  Mgr   │ Lnchr│  Tasks     │
        │ Mgr   │        │      ├────────────┤
        │       │        │      │ File Mgr   │
        │       │        │      ├────────────┤
        │       │        │      │ Sys Ctrl   │
        └───────┴────────┴──────┴────────────┘

    Every voice or text command flows through:
        1. Listener → raw text (voice) or direct text (GUI/CLI)
        2. CommandParser → ParsedCommand (intent + arguments)
        3. Assistant._dispatch() → calls the correct handler
        4. Speaker → verbal feedback (optional)
        5. Database → command_log entry

DESIGN:
    * Single Responsibility -- the Assistant only *routes*.  All
      real work happens in the handler methods which delegate to
      the appropriate manager / automation class.
    * Thread-safe voice loop -- ``start_voice_loop()`` runs the
      Listener in a daemon thread so the GUI stays responsive.
    * Observable -- callbacks can be registered to receive
      status updates (used by the GUI status bar).

FUTURE HOOKS:
    * Plugin system for dynamically loading new command handlers.
    * Multi-language support via configurable Listener language.
    * Conversation context for multi-turn interactions.
============================================================
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

from core.listener import Listener
from core.speaker import Speaker
from core.command_parser import CommandParser, ParsedCommand
from core.ai_manager import AIManager

from workspace.workspace_manager import WorkspaceManager
from workspace.task_manager import TaskManager

from automations.app_launcher import AppLauncher
from automations.browser_tasks import BrowserTasks
from automations.file_manager import FileManager
from automations.system_control import SystemControl

from database.db import get_connection, log_command

# ── Logger ─────────────────────────────────────────────────
_log: logging.Logger = logging.getLogger(__name__)


class Assistant:
    """
    Central orchestrator for the Workspace Automation System.

    Coordinates all subsystems: voice I/O, command parsing,
    workspace/task management, automation tools, and AI features.

    Attributes
    ----------
    listener : Listener
        Speech-to-text input.
    speaker : Speaker
        Text-to-speech output.
    parser : CommandParser
        Intent recognition and argument extraction.
    ai : AIManager
        AI-powered responses (stub for now).
    workspace_mgr : WorkspaceManager
        Workspace CRUD + open/launch.
    task_mgr : TaskManager
        Task CRUD + filtering.
    app_launcher : AppLauncher
        Desktop application launcher.
    browser : BrowserTasks
        URL opening and Google search.
    file_mgr : FileManager
        Filesystem operations.
    system : SystemControl
        Power management (shutdown, restart, lock, sleep).

    Usage
    -----
    ::

        assistant = Assistant()

        # Text command (from GUI or CLI):
        response = assistant.process_text("create workspace IronForge")

        # Voice command:
        response = assistant.process_voice()

        # Start continuous voice loop (background thread):
        assistant.start_voice_loop()
    """

    def __init__(self) -> None:
        # ── Core subsystems ────────────────────────────────
        self.listener: Listener = Listener()
        self.speaker: Speaker = Speaker()
        self.parser: CommandParser = CommandParser()
        self.ai: AIManager = AIManager()

        # ── Data managers ──────────────────────────────────
        self.workspace_mgr: WorkspaceManager = WorkspaceManager()
        self.task_mgr: TaskManager = TaskManager()

        # ── Automation tools ───────────────────────────────
        self.app_launcher: AppLauncher = AppLauncher()
        self.browser: BrowserTasks = BrowserTasks()
        self.file_mgr: FileManager = FileManager()
        self.system: SystemControl = SystemControl()

        # ── Database connection for command logging ────────
        self._conn = get_connection()

        # ── Voice loop control ─────────────────────────────
        self._voice_running: bool = False
        self._voice_thread: threading.Thread | None = None

        # ── Observable callbacks ───────────────────────────
        self._on_status: list[Callable[[str], None]] = []
        self._on_response: list[Callable[[str], None]] = []

        # ── Dashboard singleton tracking ───────────────────
        self._dashboard_ref: Any = None
        self._dashboard_lock: threading.Lock = threading.Lock()

        _log.info("Assistant initialised successfully.")

    def open_dashboard(self) -> str:
        """
        Open or focus the singleton GUI dashboard.

        If the dashboard is already open, bring it to the front
        and restore from minimized state.  Never creates duplicate
        dashboard windows.
        """
        with self._dashboard_lock:
            # Check if a dashboard is already running.
            if self._dashboard_ref is not None:
                try:
                    root = self._dashboard_ref.root
                    if root.winfo_exists():
                        root.deiconify()       # Restore if minimized.
                        root.lift()            # Bring to front.
                        root.focus_force()     # Focus.
                        _log.info("Dashboard already open — brought to front.")
                        return "Dashboard is already open."
                except Exception:
                    # Reference stale — clear it and fall through.
                    self._dashboard_ref = None

        def launch_dashboard():
            from gui.dashboard import Dashboard

            dashboard = Dashboard(self)
            with self._dashboard_lock:
                self._dashboard_ref = dashboard
            dashboard.run()
            # After mainloop exits, clear the reference.
            with self._dashboard_lock:
                self._dashboard_ref = None

        threading.Thread(
            target=launch_dashboard,
            daemon=True,
            name="DashboardThread",
        ).start()

        return "Opening dashboard."

    # ===========================================================
    #  Observable Interface
    # ===========================================================

    def on_status(self, callback: Callable[[str], None]) -> None:
        """Register a callback for status updates."""
        self._on_status.append(callback)

    def on_response(self, callback: Callable[[str], None]) -> None:
        """Register a callback for command responses."""
        self._on_response.append(callback)

    def _emit_status(self, status: str) -> None:
        """Notify all status listeners."""
        for cb in self._on_status:
            try:
                cb(status)
            except Exception:
                pass

    def _emit_response(self, response: str) -> None:
        """Notify all response listeners."""
        for cb in self._on_response:
            try:
                cb(response)
            except Exception:
                pass

    # ===========================================================
    #  Public API
    # ===========================================================

    def process_text(self, text: str) -> str:
        """
        Process a text command and return a response string.

        Parameters
        ----------
        text : str
            Raw user input (from GUI, CLI, or voice transcription).

        Returns
        -------
        str
            Human-readable response describing the outcome.
        """
        if not text or not text.strip():
            return "I didn't catch that.  Please try again."

        _log.info("Processing text: '%s'", text)
        self._emit_status(f"Processing: {text}")

        # ── Parse the command ──────────────────────────────
        parsed: ParsedCommand | None = self.parser.parse(text)

        if parsed is None:
            # No command matched — try AI fallback.
            response = self.ai.process(text)
            log_command(self._conn, text, f"AI: {response[:80]}")
            self._emit_response(response)
            return response

        # ── Dispatch to the correct handler ────────────────
        response = self._dispatch(parsed)

        # ── Log the command ────────────────────────────────
        log_command(self._conn, text, response[:120])
        self._emit_response(response)
        self._emit_status("Ready")

        return response

    def process_voice(self) -> str | None:
        """
        Listen for a voice command, parse it, and return a response.

        Returns
        -------
        str | None
            Response text, or ``None`` if the listener failed.
        """
        if not self.listener.is_available():
            return "Voice input is not available.  Check that speech dependencies are installed."

        self._emit_status("Listening...")
        text = self.listener.listen()

        if text is None:
            self._emit_status("Ready")
            return None

        response = self.process_text(text)

        # Speak the response aloud.
        self.speaker.say(response, block=False)

        return response

    # ── Voice Loop (background thread) ─────────────────────

    def start_voice_loop(self) -> None:
        """Start continuous voice listening in a background thread."""
        if self._voice_running:
            _log.warning("Voice loop is already running.")
            return

        self._voice_running = True
        self._voice_thread = threading.Thread(
            target=self._voice_loop_worker,
            daemon=True,
            name="VoiceLoopThread",
        )
        self._voice_thread.start()
        _log.info("Voice loop started.")
        self._emit_status("Voice mode active")

    def stop_voice_loop(self) -> None:
        """Stop the continuous voice loop."""
        self._voice_running = False
        if self._voice_thread and self._voice_thread.is_alive():
            self._voice_thread.join(timeout=2.0)
        self._voice_thread = None
        _log.info("Voice loop stopped.")
        self._emit_status("Ready")

    @property
    def voice_active(self) -> bool:
        """Return ``True`` if the voice loop is currently running."""
        return self._voice_running

    def _voice_loop_worker(self) -> None:
        """Background worker that continuously listens for commands."""
        _log.info("Voice loop worker started.")
        while self._voice_running:
            try:
                self.process_voice()
            except Exception as exc:
                _log.exception("Voice loop error: %s", exc)
                self._emit_status(f"Voice error: {exc}")

    # ===========================================================
    #  Command Dispatch
    # ===========================================================

    def _dispatch(self, cmd: ParsedCommand) -> str:
        """
        Route a parsed command to the correct handler method.

        Parameters
        ----------
        cmd : ParsedCommand
            The parsed command with intent and arguments.

        Returns
        -------
        str
            Human-readable response.
        """
        intent = cmd.intent
        args = cmd.arguments

        # ── Workspace commands ─────────────────────────────
        if intent == "create_workspace":
            return self._handle_create_workspace(args)
        if intent == "open_workspace":
            return self._handle_open_workspace(args)
        if intent == "delete_workspace":
            return self._handle_delete_workspace(args)
        if intent == "rename_workspace":
            return self._handle_rename_workspace(args)
        if intent == "list_workspaces":
            return self._handle_list_workspaces()

        # ── Task commands ──────────────────────────────────
        if intent == "add_task":
            return self._handle_add_task(args)
        if intent == "complete_task":
            return self._handle_complete_task(args)
        if intent == "delete_task":
            return self._handle_delete_task(args)
        if intent == "show_tasks":
            return self._handle_show_tasks()

        # ── Automation commands ────────────────────────────
        if intent == "launch_app":
            return self._handle_launch_app(args)
        if intent == "search_google":
            return self._handle_search_google(args)
        if intent == "open_url":
            return self._handle_open_url(args)
        if intent == "organize_downloads":
            return self._handle_organize_downloads()
        if intent == "create_folder":
            return self._handle_create_folder(args)
        if intent == "open_dashboard":
            return self.open_dashboard()
            
        # ── System commands ────────────────────────────────
        if intent == "shutdown":
            return self._handle_shutdown()
        if intent == "restart":
            return self._handle_restart()
        if intent == "lock_screen":
            return self._handle_lock_screen()

        # ── Meta commands ──────────────────────────────────
        if intent == "help":
            return self.parser.get_help_text()

        # ── Voice overlay commands ─────────────────────────
        if intent == "close_dashboard":
            return self._handle_close_dashboard()
        if intent == "hide_dashboard":
            return self._handle_hide_dashboard()
        if intent == "show_dashboard":
            return self.open_dashboard()
        if intent == "exit_workspace":
            return self._handle_exit_workspace()
        if intent == "restart_workspace":
            return self._handle_restart_workspace()
        if intent == "sleep_computer":
            return self._handle_sleep_computer()
        if intent == "search_youtube":
            return self._handle_search_youtube(args)
        if intent == "open_chatgpt":
            return self._handle_open_chatgpt()

        return f"I understood the command '{intent}' but don't know how to handle it yet."

    # ===========================================================
    #  Handler Methods
    # ===========================================================

    # ── Workspace Handlers ─────────────────────────────────

    def _handle_create_workspace(self, args: dict[str, Any]) -> str:
        name = args.get("name", "")
        if not name:
            return "Please specify a workspace name.  Example: 'create workspace IronForge'"
        try:
            ws_id = self.workspace_mgr.create(name)
            return f"Workspace '{name}' created successfully (id={ws_id})."
        except ValueError as exc:
            return str(exc)

    def _handle_open_workspace(self, args: dict[str, Any]) -> str:
        name = args.get("name", "")
        if not name:
            return "Please specify a workspace name.  Example: 'open workspace IronForge'"
        ws = self.workspace_mgr.get_by_name(name)
        if ws is None:
            return f"Workspace '{name}' not found."
        success = self.workspace_mgr.open(ws["id"])
        if success:
            return f"Workspace '{name}' launched successfully!"
        return f"Workspace '{name}' launched with some errors.  Check logs/app.log."

    def _handle_delete_workspace(self, args: dict[str, Any]) -> str:
        name = args.get("name", "")
        if not name:
            return "Please specify a workspace name.  Example: 'delete workspace IronForge'"
        ws = self.workspace_mgr.get_by_name(name)
        if ws is None:
            return f"Workspace '{name}' not found."
        deleted = self.workspace_mgr.delete(ws["id"])
        if deleted:
            return f"Workspace '{name}' deleted."
        return f"Could not delete workspace '{name}'."

    def _handle_rename_workspace(self, args: dict[str, Any]) -> str:
        name = args.get("name", "")
        if not name:
            return "Please specify the workspace to rename.  Example: 'rename workspace OldName to NewName'"
        # Try to parse "OldName to NewName" pattern.
        parts = name.split(" to ", 1)
        if len(parts) != 2:
            return "Use the format: 'rename workspace OldName to NewName'"
        old_name, new_name = parts[0].strip(), parts[1].strip()
        ws = self.workspace_mgr.get_by_name(old_name)
        if ws is None:
            return f"Workspace '{old_name}' not found."
        self.workspace_mgr.rename(ws["id"], new_name)
        return f"Workspace renamed from '{old_name}' to '{new_name}'."

    def _handle_list_workspaces(self) -> str:
        workspaces = self.workspace_mgr.list_all()
        if not workspaces:
            return "No workspaces found.  Create one with 'create workspace MyProject'."
        lines = [f"  • {ws['name']}" for ws in workspaces]
        return f"Workspaces ({len(workspaces)}):\n" + "\n".join(lines)

    # ── Task Handlers ──────────────────────────────────────

    def _handle_add_task(self, args: dict[str, Any]) -> str:
        title = args.get("title", "")
        if not title:
            return "Please specify a task title.  Example: 'add task finish authentication'"
        task_id = self.task_mgr.add(title)
        return f"Task '{title}' added (id={task_id})."

    def _handle_complete_task(self, args: dict[str, Any]) -> str:
        title = args.get("title", "")
        if not title:
            return "Please specify which task to complete."
        # Search for a task by title (partial match).
        tasks = self.task_mgr.list_pending()
        for t in tasks:
            if title.lower() in t["title"].lower():
                self.task_mgr.complete(t["id"])
                return f"Task '{t['title']}' marked as completed."
        return f"No pending task matching '{title}' found."

    def _handle_delete_task(self, args: dict[str, Any]) -> str:
        title = args.get("title", "")
        if not title:
            return "Please specify which task to delete."
        tasks = self.task_mgr.list_all()
        for t in tasks:
            if title.lower() in t["title"].lower():
                self.task_mgr.delete(t["id"])
                return f"Task '{t['title']}' deleted."
        return f"No task matching '{title}' found."

    def _handle_show_tasks(self) -> str:
        tasks = self.task_mgr.list_pending()
        if not tasks:
            return "No pending tasks.  You're all caught up!"
        lines = []
        for t in tasks:
            priority = t["priority"].upper()
            lines.append(f"  [{priority}] {t['title']}")
        return f"Pending tasks ({len(tasks)}):\n" + "\n".join(lines)

    # ── Automation Handlers ────────────────────────────────

    def _handle_launch_app(self, args: dict[str, Any]) -> str:
        app_name = args.get("app_name", "")
        if not app_name:
            available = ", ".join(self.app_launcher.list_available())
            return f"Please specify an app to launch.  Available: {available}"
        success = self.app_launcher.launch(app_name)
        if success:
            return f"Launched {app_name}."
        return f"Could not launch '{app_name}'.  Check that it's installed."

    def _handle_search_google(self, args: dict[str, Any]) -> str:
        query = args.get("query", "")
        if not query:
            return "Please specify what to search for.  Example: 'search Python tutorials'"
        self.browser.search_google(query)
        return f"Searching Google for '{query}'..."

    def _handle_open_url(self, args: dict[str, Any]) -> str:
        url = args.get("url", "")
        if not url:
            return "Please specify a URL.  Example: 'go to github.com'"
        self.browser.open_url(url)
        return f"Opening {url}..."

    def _handle_organize_downloads(self) -> str:
        summary = self.file_mgr.organize_downloads()
        if not summary:
            return "Downloads folder is already organised (or empty)."
        lines = [f"  {cat}: {count} files" for cat, count in summary.items()]
        return "Downloads organised:\n" + "\n".join(lines)

    def _handle_create_folder(self, args: dict[str, Any]) -> str:
        path = args.get("path", "")
        if not path:
            return "Please specify a folder path.  Example: 'create folder C:/Projects/new'"
        success = self.file_mgr.create_folder(path)
        if success:
            return f"Folder created: {path}"
        return f"Could not create folder: {path}"

    # ── System Handlers ────────────────────────────────────

    def _handle_shutdown(self) -> str:
        return "Shutdown requested.  Please confirm in the system dialog."

    def _handle_restart(self) -> str:
        return "Restart requested.  Please confirm in the system dialog."

    def _handle_lock_screen(self) -> str:
        success = self.system.lock_screen()
        if success:
            return "Screen locked."
        return "Could not lock the screen.  This feature is Windows-only."

    # ── Voice Overlay Handlers (additive) ──────────────────

    def _handle_close_dashboard(self) -> str:
        """Close the dashboard window if it is open."""
        with self._dashboard_lock:
            if self._dashboard_ref is not None:
                try:
                    self._dashboard_ref.root.after(
                        0, self._dashboard_ref.root.destroy
                    )
                    self._dashboard_ref = None
                    _log.info("Dashboard closed via voice command.")
                    return "Dashboard closed."
                except Exception as exc:
                    _log.error("Error closing dashboard: %s", exc)
                    self._dashboard_ref = None
            return "Dashboard is not open."

    def _handle_hide_dashboard(self) -> str:
        """Hide (minimize) the dashboard window."""
        with self._dashboard_lock:
            if self._dashboard_ref is not None:
                try:
                    self._dashboard_ref.root.after(
                        0, self._dashboard_ref.root.withdraw
                    )
                    return "Dashboard hidden."
                except Exception:
                    pass
            return "Dashboard is not open."

    def _handle_exit_workspace(self) -> str:
        """Exit the workspace assistant entirely."""
        import os
        _log.info("Exit workspace requested.")
        threading.Timer(1.5, lambda: os._exit(0)).start()
        return "Goodbye! Exiting workspace assistant."

    def _handle_restart_workspace(self) -> str:
        """Restart the workspace assistant."""
        import os
        import sys
        _log.info("Restart workspace requested.")
        def _do_restart() -> None:
            python = sys.executable
            os.execl(python, python, *sys.argv)
        threading.Timer(1.5, _do_restart).start()
        return "Restarting workspace assistant..."

    def _handle_sleep_computer(self) -> str:
        """Put the computer to sleep."""
        import subprocess
        _log.info("Sleep computer requested.")
        try:
            subprocess.run(
                "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
                shell=True,
                capture_output=True,
                timeout=10,
            )
            return "Computer going to sleep."
        except Exception as exc:
            _log.error("Sleep failed: %s", exc)
            return f"Could not put computer to sleep: {exc}"

    def _handle_search_youtube(self, args: dict[str, Any]) -> str:
        """Search YouTube for a query."""
        import urllib.parse
        import webbrowser
        query = args.get("query", "")
        if not query:
            return "What would you like to search on YouTube?"
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.youtube.com/results?search_query={encoded}"
        webbrowser.open(url)
        return f"Searching YouTube for '{query}'."

    def _handle_open_chatgpt(self) -> str:
        """Open ChatGPT in the default browser."""
        import webbrowser
        webbrowser.open("https://chat.openai.com")
        return "Opening ChatGPT."
