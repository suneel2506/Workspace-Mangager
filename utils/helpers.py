"""
============================================================
  helpers.py — Shared Utility Functions
============================================================

PURPOSE:
    Reusable display helpers used across the project:
      - Banners and dividers for the interactive menu.
      - Colored terminal output (ANSI codes, Windows-safe).
      - Miscellaneous text-formatting utilities.

DESIGN NOTES:
    All functions in this module are pure or side-effect-free
    (except for printing).  They do not import any project
    modules, so they sit at the bottom of the dependency tree.

    ENCODING:
    Windows terminals (cmd, PowerShell) default to cp1252 which
    cannot render Unicode symbols like "═", "✔", "✖".  This
    module forces UTF-8 on stdout/stderr at import time so that
    all Unicode prints work reliably.

FUTURE HOOKS:
    - Terminal color theme configuration.
    - Rich-library integration for advanced TUI.
    - Progress spinners for long-running launches.
============================================================
"""

import io
import os
import sys


# ── Force UTF-8 output on Windows ─────────────────────────
# Without this, print() crashes on cp1252 when using Unicode
# box-drawing characters or emoji.
if sys.platform == "win32":
    # Enable ANSI escape sequences in cmd / PowerShell.
    os.system("")

    # Wrap stdout and stderr to always emit UTF-8.
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True,
        )
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True,
        )


# ── ANSI Color Codes ──────────────────────────────────────
class Colors:
    """
    ANSI escape codes for terminal coloring.

    Usage
    -----
        print(f"{Colors.GREEN}Success!{Colors.RESET}")
    """

    RESET:   str = "\033[0m"
    BOLD:    str = "\033[1m"
    DIM:     str = "\033[2m"

    RED:     str = "\033[91m"
    GREEN:   str = "\033[92m"
    YELLOW:  str = "\033[93m"
    BLUE:    str = "\033[94m"
    MAGENTA: str = "\033[95m"
    CYAN:    str = "\033[96m"
    WHITE:   str = "\033[97m"


# ── Display helpers ────────────────────────────────────────

def print_banner() -> None:
    """Print the application header banner."""
    c = Colors
    print()
    print(f"{c.CYAN}{c.BOLD}{'=' * 40}")
    print(f"{'Workspace Manager':^40}")
    print(f"{'=' * 40}{c.RESET}")
    print()


def print_divider(char: str = "-", width: int = 40) -> None:
    """Print a thin horizontal divider line."""
    print(f"{Colors.DIM}{char * width}{Colors.RESET}")


def print_success(message: str) -> None:
    """Print a green success message."""
    print(f"{Colors.GREEN}  [+] {message}{Colors.RESET}")


def print_error(message: str) -> None:
    """Print a red error message."""
    print(f"{Colors.RED}  [x] {message}{Colors.RESET}")


def print_warning(message: str) -> None:
    """Print a yellow warning message."""
    print(f"{Colors.YELLOW}  [!] {message}{Colors.RESET}")


def print_info(message: str) -> None:
    """Print a blue informational message."""
    print(f"{Colors.BLUE}  [*] {message}{Colors.RESET}")


def format_workspace_name(name: str) -> str:
    """
    Capitalize a workspace name for display.

    Examples
    --------
    >>> format_workspace_name("coding")
    'Coding'
    >>> format_workspace_name("vlsi")
    'VLSI'

    Parameters
    ----------
    name : str
        Raw workspace name from JSON.

    Returns
    -------
    str
        Display-ready name.
    """
    # Common acronyms that should stay uppercase.
    acronyms: set[str] = {"vlsi", "fpga", "pcb", "iot", "ai", "ml"}

    if name.lower() in acronyms:
        return name.upper()

    return name.capitalize()


def confirm_action(prompt: str = "Proceed?") -> bool:
    """
    Ask the user for a yes/no confirmation.

    Parameters
    ----------
    prompt : str
        The question to display.

    Returns
    -------
    bool
        ``True`` if the user answers yes.
    """
    answer: str = input(f"  {prompt} [y/N]: ").strip().lower()
    return answer in ("y", "yes")
