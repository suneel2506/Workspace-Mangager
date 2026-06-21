"""
============================================================
  automations/ package -- System Automation Modules
============================================================

This package contains self-contained automation classes that
the Workspace Automation System can invoke from the CLI, the
interactive menu, or (eventually) a GUI / voice interface.

Modules
-------
app_launcher.py
    Launch desktop applications by friendly name or direct path.

browser_tasks.py
    Open URLs and perform Google searches in the default browser.

file_manager.py
    Create, delete, and move folders / files; auto-organise the
    user's Downloads folder by file type.

system_control.py
    Shutdown, restart, lock, and sleep the workstation (with
    mandatory confirmation for destructive actions).
============================================================
"""

from __future__ import annotations

# Re-export public classes so callers can write:
#   from automations import AppLauncher, BrowserTasks, ...
from automations.app_launcher import AppLauncher
from automations.browser_tasks import BrowserTasks
from automations.file_manager import FileManager
from automations.system_control import SystemControl

__all__: list[str] = [
    "AppLauncher",
    "BrowserTasks",
    "FileManager",
    "SystemControl",
]
