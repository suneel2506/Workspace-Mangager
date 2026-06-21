"""
============================================================
  main.py — Workspace Manager Entry Point
============================================================

USAGE:
    # 1) Launch a workspace directly from the command line:
    python main.py coding

    # 2) Open the interactive menu:
    python main.py

    # 3) Start voice mode directly:
    python main.py --voice

DESCRIPTION:
    This is the single entry point for the entire application.
    It parses command-line arguments and delegates to the
    appropriate module:

        ┌──────────────┐
        │   main.py    │
        └──┬───┬───┬───┘
           │   │   │
           ▼   ▼   ▼
        CLI  Menu  Voice
           │   │   │
           ▼   ▼   ▼
        ┌──────────────┐
        │  Launcher    │  ← opens apps & URLs
        └──────────────┘
           │
           ▼
        ┌──────────────┐
        │   Logger     │  ← writes logs.txt
        └──────────────┘

FUTURE HOOKS:
    • --gui flag to launch a CustomTkinter window.
    • --schedule flag for timed workspace launches.
    • --close flag to terminate a running workspace.
    • --add / --remove flags to edit workspaces.json from CLI.
============================================================
"""

import sys

from core.workspace_manager import WorkspaceManager
from core.launcher import Launcher
from core.logger import Logger
from voice.speech import VoiceController
from utils.helpers import (
    print_banner,
    print_divider,
    print_success,
    print_error,
    print_warning,
    print_info,
    format_workspace_name,
    Colors,
)


# ── Shared instances (created once, reused everywhere) ─────
logger = Logger()
workspace_mgr = WorkspaceManager()
launcher = Launcher(logger=logger)


# ===========================================================
#  CLI MODE — python main.py <workspace_name>
# ===========================================================
def launch_workspace_by_name(name: str) -> None:
    """
    Look up a workspace by name and launch all its items.

    Parameters
    ----------
    name : str
        Workspace name (case-insensitive).
    """
    try:
        items = workspace_mgr.get_workspace(name)
    except KeyError as exc:
        print_error(str(exc))
        return

    display: str = format_workspace_name(name)
    print()
    print_info(f"Launching workspace: {display}")
    print_divider()

    success: bool = launcher.launch(name, items)

    print_divider()
    if success:
        print_success(f"Workspace '{display}' launched successfully!")
    else:
        print_warning(f"Workspace '{display}' launched with errors. Check logs.txt.")
    print()


# ===========================================================
#  VOICE MODE — listen → match → launch
# ===========================================================
def voice_mode() -> None:
    """
    Enter voice recognition mode.  Loops until the user says
    a valid workspace name or decides to quit.
    """
    print_info("Entering Voice Mode")
    print_info("Say 'Open <workspace> workspace' or 'quit' to exit.\n")

    vc = VoiceController(
        workspace_names=workspace_mgr.list_workspaces(),
        logger=logger,
    )

    while True:
        name = vc.listen_for_workspace()

        if name:
            launch_workspace_by_name(name)
            # Ask if the user wants to continue listening.
            again: str = input("  Listen again? [y/N]: ").strip().lower()
            if again not in ("y", "yes"):
                break
        else:
            retry: str = input("  Try again? [y/N]: ").strip().lower()
            if retry not in ("y", "yes"):
                break

    print_info("Exiting Voice Mode.\n")


# ===========================================================
#  INTERACTIVE MENU — python main.py (no arguments)
# ===========================================================
def interactive_menu() -> None:
    """
    Display a numbered menu of all workspaces + Voice Mode
    and wait for the user to choose.
    """
    while True:
        print_banner()

        workspaces: list[str] = workspace_mgr.list_workspaces()

        # Build the numbered list.
        for i, ws_name in enumerate(workspaces, start=1):
            display: str = format_workspace_name(ws_name)
            print(f"  {Colors.CYAN}{i}.{Colors.RESET} {display}")

        # Extra options after the workspace list.
        voice_option: int = len(workspaces) + 1
        exit_option: int = voice_option + 1

        print(f"  {Colors.MAGENTA}{voice_option}.{Colors.RESET} Voice Mode")
        print(f"  {Colors.RED}{exit_option}.{Colors.RESET} Exit")
        print()

        # Get user choice.
        try:
            choice_str: str = input(f"  {Colors.BOLD}Select an option: {Colors.RESET}").strip()
            if not choice_str:
                continue

            choice: int = int(choice_str)

        except ValueError:
            print_error("Please enter a number.\n")
            continue

        # Route the choice.
        if 1 <= choice <= len(workspaces):
            selected: str = workspaces[choice - 1]
            launch_workspace_by_name(selected)

        elif choice == voice_option:
            voice_mode()

        elif choice == exit_option:
            print_info("Goodbye!\n")
            break

        else:
            print_error(f"Invalid option. Choose 1–{exit_option}.\n")


# ===========================================================
#  ENTRY POINT
# ===========================================================
def main() -> None:
    """
    Parse ``sys.argv`` and decide which mode to run.

    Modes
    -----
    ``python main.py``             → interactive menu
    ``python main.py coding``      → launch "coding" workspace
    ``python main.py --voice``     → voice recognition mode
    ``python main.py --list``      → print all workspaces
    ``python main.py --help``      → usage instructions
    """
    args: list[str] = sys.argv[1:]

    # No arguments → interactive menu.
    if not args:
        interactive_menu()
        return

    first_arg: str = args[0].lower()

    # ── Flags ──────────────────────────────────────────────
    if first_arg in ("--help", "-h"):
        _print_usage()
        return

    if first_arg in ("--voice", "-v"):
        print_banner()
        voice_mode()
        return

    if first_arg in ("--list", "-l"):
        print_banner()
        print_info("Available workspaces:\n")
        for ws in workspace_mgr.list_workspaces():
            print(f"    • {format_workspace_name(ws)}")
        print()
        return

    # ── Positional argument → workspace name ───────────────
    launch_workspace_by_name(first_arg)


def _print_usage() -> None:
    """Print help text."""
    print(
        """
Usage: python main.py [OPTION | WORKSPACE_NAME]

Options:
  (no argument)      Open the interactive menu
  <workspace_name>   Launch a workspace by name (e.g., 'coding')
  --voice, -v        Start voice recognition mode
  --list,  -l        List all available workspaces
  --help,  -h        Show this help message

Examples:
  python main.py                 # interactive menu
  python main.py coding          # launch 'coding' workspace
  python main.py --voice         # voice mode
  python main.py --list          # list workspaces
"""
    )


# ── Guard: only run when executed directly ─────────────────
if __name__ == "__main__":
    main()
