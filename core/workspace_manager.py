"""
============================================================
  workspace_manager.py — Workspace Configuration Loader
============================================================

PURPOSE:
    Reads ``workspaces.json``, validates its structure, and
    provides a clean Python API to query available workspaces.

    This module *only* deals with data — it never opens apps
    or URLs.  That responsibility belongs to ``launcher.py``.

DATA MODEL:
    Each workspace is a list of *items*.  An item is a dict
    with the following shape:

        { "type": "app", "path": "code", "name": "VS Code" }
        { "type": "url", "value": "https://...", "name": "..." }

    • "type"  — either ``"app"`` or ``"url"``.
    • "path"  — (apps only) command or absolute path to the exe.
    • "value" — (URLs only) the web address to open.
    • "name"  — (optional) a human-friendly display name.

FUTURE HOOKS:
    • Add / remove workspaces from the JSON via CLI.
    • Import/export workspace definitions.
    • Workspace tagging and search.
============================================================
"""

import json
from pathlib import Path
from typing import Any


# ── Default path to the workspace config ───────────────────
DEFAULT_CONFIG: Path = Path(__file__).resolve().parent.parent / "workspaces.json"


class WorkspaceManager:
    """
    Loads and queries workspace definitions from a JSON file.

    Attributes
    ----------
    config_path : Path
        Absolute path to the JSON configuration file.
    workspaces : dict[str, list[dict[str, str]]]
        Parsed workspace data, keyed by workspace name.

    Raises
    ------
    FileNotFoundError
        If the JSON file does not exist.
    json.JSONDecodeError
        If the JSON file contains invalid syntax.

    Usage
    -----
        wm = WorkspaceManager()
        items = wm.get_workspace("coding")
    """

    def __init__(self, config_path: Path = DEFAULT_CONFIG) -> None:
        """
        Parameters
        ----------
        config_path : Path, optional
            Path to ``workspaces.json``.  Defaults to the file in
            the project root.
        """
        self.config_path: Path = config_path
        self.workspaces: dict[str, list[dict[str, str]]] = self._load()

    # ── Private helpers ────────────────────────────────────
    def _load(self) -> dict[str, list[dict[str, str]]]:
        """
        Read and parse the JSON config file.

        Returns
        -------
        dict
            The parsed workspace definitions.

        Raises
        ------
        FileNotFoundError
            When the config file is missing.
        ValueError
            When the JSON root is not a dict.
        """
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Config file not found: {self.config_path}\n"
                "Create a 'workspaces.json' in the project root."
            )

        with open(self.config_path, "r", encoding="utf-8") as f:
            data: Any = json.load(f)

        if not isinstance(data, dict):
            raise ValueError(
                "workspaces.json must contain a JSON object (dict) "
                "at the top level."
            )

        return data

    # ── Public API ─────────────────────────────────────────
    def get_workspace(self, name: str) -> list[dict[str, str]]:
        """
        Return the list of items for a workspace.

        Parameters
        ----------
        name : str
            Workspace name (case-insensitive).

        Returns
        -------
        list[dict[str, str]]
            The items defined in that workspace.

        Raises
        ------
        KeyError
            If the workspace name is not found.
        """
        # Case-insensitive lookup.
        key: str = name.strip().lower()
        for ws_name, ws_items in self.workspaces.items():
            if ws_name.lower() == key:
                return ws_items

        raise KeyError(
            f"Workspace '{name}' not found.\n"
            f"Available: {', '.join(self.list_workspaces())}"
        )

    def list_workspaces(self) -> list[str]:
        """
        Return a sorted list of all workspace names.

        Returns
        -------
        list[str]
            Workspace names exactly as they appear in JSON.
        """
        return sorted(self.workspaces.keys())

    def workspace_exists(self, name: str) -> bool:
        """
        Check if a workspace exists (case-insensitive).

        Parameters
        ----------
        name : str
            Workspace name to look up.

        Returns
        -------
        bool
        """
        key: str = name.strip().lower()
        return any(ws.lower() == key for ws in self.workspaces)

    def reload(self) -> None:
        """
        Re-read the JSON file from disk.

        Useful if the user edited ``workspaces.json`` while the
        program is running.
        """
        self.workspaces = self._load()
