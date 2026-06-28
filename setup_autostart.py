"""
============================================================
  setup_autostart.py — Windows Auto-Start Installer
============================================================

Adds or removes the voice overlay from Windows startup via
the ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run``
registry key.

USAGE:
    python setup_autostart.py           # Add to startup
    python setup_autostart.py --remove  # Remove from startup
    python setup_autostart.py --status  # Check current state
============================================================
"""

from __future__ import annotations

import os
import sys
import winreg
from pathlib import Path

# ── Constants ──────────────────────────────────────────────

_APP_NAME: str = "WorkspaceManagerOverlay"
_REG_PATH: str = r"Software\Microsoft\Windows\CurrentVersion\Run"
_PROJECT_ROOT: Path = Path(__file__).resolve().parent
_BAT_PATH: Path = _PROJECT_ROOT / "run_overlay.bat"


def add_to_startup() -> None:
    """Add the overlay to Windows startup."""
    if not _BAT_PATH.exists():
        print(f"  [✗] run_overlay.bat not found at: {_BAT_PATH}")
        print(f"      Create it first, then re-run this script.")
        return

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _REG_PATH,
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(
            key,
            _APP_NAME,
            0,
            winreg.REG_SZ,
            str(_BAT_PATH),
        )
        winreg.CloseKey(key)
        print(f"  [✓] Added to Windows startup.")
        print(f"      Key: HKCU\\{_REG_PATH}\\{_APP_NAME}")
        print(f"      Value: {_BAT_PATH}")
    except OSError as exc:
        print(f"  [✗] Failed to add to startup: {exc}")


def remove_from_startup() -> None:
    """Remove the overlay from Windows startup."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _REG_PATH,
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.DeleteValue(key, _APP_NAME)
        winreg.CloseKey(key)
        print(f"  [✓] Removed from Windows startup.")
    except FileNotFoundError:
        print(f"  [i] Not currently in startup — nothing to remove.")
    except OSError as exc:
        print(f"  [✗] Failed to remove from startup: {exc}")


def check_status() -> None:
    """Check if the overlay is in Windows startup."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _REG_PATH,
            0,
            winreg.KEY_READ,
        )
        value, _ = winreg.QueryValueEx(key, _APP_NAME)
        winreg.CloseKey(key)
        print(f"  [✓] Overlay IS in Windows startup.")
        print(f"      Command: {value}")
    except FileNotFoundError:
        print(f"  [i] Overlay is NOT in Windows startup.")
    except OSError as exc:
        print(f"  [✗] Could not check status: {exc}")


def main() -> None:
    """Parse args and run the appropriate action."""
    print()
    print("  Workspace Manager — Auto-Start Setup")
    print("  " + "=" * 40)
    print()

    args = sys.argv[1:]

    if not args:
        add_to_startup()
    elif args[0] == "--remove":
        remove_from_startup()
    elif args[0] == "--status":
        check_status()
    else:
        print("Usage:")
        print("  python setup_autostart.py           # Add to startup")
        print("  python setup_autostart.py --remove  # Remove from startup")
        print("  python setup_autostart.py --status  # Check current state")

    print()


if __name__ == "__main__":
    main()
