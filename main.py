"""
============================================================
  main.py — Workspace Automation System Entry Point
============================================================

USAGE:
    # 1) Launch the GUI dashboard (default):
    python main.py

    # 2) Open the interactive CLI menu:
    python main.py --cli

    # 3) Start voice-only mode:
    python main.py --voice

    # 4) Execute a single text command:
    python main.py --cmd "create workspace IronForge"

    # 5) Show help:
    python main.py --help

ARCHITECTURE:
    This module is the single entry point that:
      1. Initialises logging and the database schema.
      2. Creates the central ``Assistant`` instance.
      3. Routes to GUI, CLI, or voice mode based on flags.

    ┌──────────────┐
    │   main.py    │
    └──┬───┬───┬───┘
       │   │   │
       ▼   ▼   ▼
     GUI  CLI  Voice
       │   │   │
       ▼   ▼   ▼
    ┌──────────────┐
    │  Assistant   │  ← central orchestrator
    └──────────────┘
============================================================
"""

import sys

from config.settings import setup_logging, APP_NAME, APP_VERSION
from database.db import init_db

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


# ===========================================================
#  Initialization
# ===========================================================

def _init() -> None:
    """Run one-time startup tasks: logging + database."""
    setup_logging()
    init_db()


# ===========================================================
#  GUI MODE — python main.py (default)
# ===========================================================

def gui_mode() -> None:
    """Launch the Tkinter dashboard."""
    from core.assistant import Assistant
    from gui.dashboard import Dashboard

    print_info(f"Starting {APP_NAME} v{APP_VERSION} — GUI Mode")

    assistant = Assistant()
    dashboard = Dashboard(assistant)
    dashboard.run()


# ===========================================================
#  CLI MODE — python main.py --cli
# ===========================================================

def cli_mode() -> None:
    """Run the interactive command-line interface."""
    from core.assistant import Assistant

    assistant = Assistant()

    print_banner()
    print_info(f"{APP_NAME} v{APP_VERSION} — CLI Mode")
    print_info("Type 'help' for available commands, or 'quit' to exit.\n")

    while True:
        try:
            user_input = input(f"  {Colors.BOLD}> {Colors.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print_info("Goodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print_info("Goodbye!")
            break

        # Process the command through the assistant.
        response = assistant.process_text(user_input)
        print()
        print(f"  {response}")
        print()


# ===========================================================
#  VOICE MODE — python main.py --voice
# ===========================================================

def voice_mode() -> None:
    """Run continuous voice recognition mode."""
    from core.assistant import Assistant

    assistant = Assistant()

    print_banner()
    print_info(f"{APP_NAME} v{APP_VERSION} — Voice Mode")
    print_info("Say a command or 'quit' to exit.\n")

    if not assistant.listener.is_available():
        print_error("Voice dependencies are not installed.")
        print_error("Run: pip install SpeechRecognition sounddevice scipy")
        return

    while True:
        response = assistant.process_voice()

        if response:
            print()
            print(f"  {response}")
            print()

            # Speak the response.
            assistant.speaker.say(response, block=True)

        # Ask if user wants to continue.
        try:
            again = input(f"  {Colors.DIM}Listen again? [Y/n]: {Colors.RESET}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break

        if again in ("n", "no", "quit", "exit"):
            break

    print_info("Exiting Voice Mode.")


# ===========================================================
#  SINGLE COMMAND — python main.py --cmd "..."
# ===========================================================

def single_command(text: str) -> None:
    """Execute a single text command and exit."""
    from core.assistant import Assistant

    assistant = Assistant()
    response = assistant.process_text(text)
    print(response)



def wakeword_mode() -> None:
    """
    Run MAJA as a background wake-word assistant.
    """

    from core.assistant import Assistant
    from wakeword import listen_for_wakeword

    assistant = Assistant()

    print_info("MAJA Wake Word Mode Started")
    print_info("Say 'MAJA' followed by a command. Press Ctrl+C to exit.\n")

    try:
        while True:
            if listen_for_wakeword():
                print_success("Wake word detected!")

                assistant.speaker.say(
                    "Yes boss",
                    block=True
                )

                response = assistant.process_voice()

                if response:
                    print(f"  {response}")

                    assistant.speaker.say(
                        response,
                        block=True
                    )
    except KeyboardInterrupt:
        print()
        print_info("Exiting Wake Word Mode.")
# ===========================================================
#  OVERLAY MODE (Voice-Controlled Floating Widget)
# ===========================================================

def overlay_mode() -> None:
    """
    Launch the voice-controlled floating overlay.

    Displays a tiny floating microphone button (always-on-top).
    The dashboard does NOT open — only the overlay appears.
    Say 'Open Dashboard' to launch the dashboard via voice.
    """
    print_info(f"{APP_NAME} v{APP_VERSION} — Overlay Mode")
    print("  [*] Starting voice overlay...")

    try:
        from voice.overlay import VoiceOverlay
        overlay = VoiceOverlay()
        overlay.run()
    except ImportError as exc:
        print(f"  [✗] Could not import voice overlay: {exc}")
        print("      Run: pip install vosk rapidfuzz keyboard Pillow")
    except Exception as exc:
        print(f"  [✗] Overlay error: {exc}")

# ===========================================================
#  ENTRY POINT
# ===========================================================

def main() -> None:
    """
    Parse ``sys.argv`` and decide which mode to run.

    Modes
    -----
    ``python main.py``                 → GUI dashboard
    ``python main.py --cli``           → interactive CLI
    ``python main.py --voice``         → voice recognition mode
    ``python main.py --cmd "..."``     → single text command
    ``python main.py --help``          → usage instructions
    """
    # Always run init first.
    _init()

    args: list[str] = sys.argv[1:]

    # No arguments → GUI mode (default).
    if not args:
        gui_mode()
        return

    first_arg: str = args[0].lower()

    # ── Flags ──────────────────────────────────────────────
    if first_arg in ("--help", "-h"):
        _print_usage()
        return

    if first_arg in ("--cli", "-c"):
        cli_mode()
        return

    if first_arg in ("--voice", "-v"):
        voice_mode()
        return

    if first_arg in ("--cmd",) and len(args) > 1:
        single_command(" ".join(args[1:]))
        return
    
    if first_arg in ("--wake", "-w"):
        wakeword_mode()
        return

    if first_arg in ("--overlay", "-o"):
        overlay_mode()
        return

    # ── Legacy: treat positional argument as a command ─────
    single_command(" ".join(args))


def _print_usage() -> None:
    """Print help text."""
    print(
        f"""
{APP_NAME} v{APP_VERSION}
{'=' * 50}

Usage: python main.py [OPTION]

Options:
  (no argument)              Launch the GUI dashboard
  --cli,     -c              Open interactive CLI mode
  --voice,   -v              Start voice recognition mode
  --wake,    -w              Start MAJA wake word mode
  --overlay, -o              Start voice overlay (floating mic)
  --cmd "command text"       Execute a single command and exit
  --help,    -h              Show this help message

Examples:
  python main.py                           # GUI dashboard
  python main.py --cli                     # interactive CLI
  python main.py --voice                   # voice mode
  python main.py --wake                    # MAJA wake word mode
  python main.py --overlay                 # floating mic overlay
  python main.py --cmd "create workspace IronForge"
  python main.py --cmd "show pending tasks"
  python main.py --cmd "launch chrome"

Available Voice / CLI Commands:
  create workspace <name>      Create a new workspace
  open workspace <name>        Launch all workspace items
  delete workspace <name>      Delete a workspace
  list workspaces              Show all workspaces
  add task <title>             Add a new task
  show tasks                   List pending tasks
  complete task <title>        Mark a task as done
  launch <app>                 Open an application
  search <query>               Google search
  go to <url>                  Open a URL
  organize downloads           Sort Downloads folder
  shutdown / restart / lock    System controls
  help                         Show available commands
"""
    )


# ── Guard: only run when executed directly ─────────────────
if __name__ == "__main__":
    main()
