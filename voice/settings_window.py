"""
============================================================
  settings_window.py — Voice Assistant Settings GUI
============================================================

PURPOSE:
    Tkinter Toplevel window with a tabbed notebook for
    configuring all voice assistant settings.  Changes are
    applied immediately via SettingsManager.

TABS:
    1. Speech Engine — engine selector, language, timeout
    2. Wake Word — enable/disable, word text
    3. Microphone — device dropdown
    4. Overlay — transparency, animation speed, theme
    5. Hotkey — hotkey binding
    6. Logging — enable/disable, clear history
    7. AI — enable/disable AI fallback
    8. Startup — auto-startup toggle
    9. Plugins — list loaded plugins
============================================================
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from voice.settings_manager import SettingsManager

_log: logging.Logger = logging.getLogger(__name__)


# ── Color Palette ──────────────────────────────────────────

class _C:
    BG = "#1e1e2e"
    BG2 = "#313244"
    FG = "#cdd6f4"
    FG_DIM = "#6c7086"
    ACCENT = "#89b4fa"
    ACCENT2 = "#a6e3a1"
    INPUT_BG = "#45475a"
    INPUT_FG = "#cdd6f4"
    BTN_BG = "#89b4fa"
    BTN_FG = "#1e1e2e"


class SettingsWindow:
    """
    Settings GUI for the voice assistant.

    Opens a Toplevel Tkinter window with tabbed sections for
    all configurable settings.

    Parameters
    ----------
    parent : tk.Tk | None
        Parent window (the overlay root).
    settings : SettingsManager
        Settings manager instance for reading/writing values.
    """

    def __init__(
        self,
        parent: tk.Tk | None,
        settings: SettingsManager,
    ) -> None:
        self._settings: SettingsManager = settings
        self._vars: dict[str, tk.Variable] = {}

        # Create the window.
        self._win = tk.Toplevel(parent) if parent else tk.Tk()
        self._win.title("Voice Assistant — Settings")
        self._win.geometry("520x550")
        self._win.configure(bg=_C.BG)
        self._win.resizable(False, False)
        self._win.attributes("-topmost", True)

        # Style the ttk notebook.
        self._style_notebook()

        # Build tabs.
        self._notebook = ttk.Notebook(self._win)
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))

        self._build_speech_tab()
        self._build_wake_tab()
        self._build_mic_tab()
        self._build_overlay_tab()
        self._build_hotkey_tab()
        self._build_logging_tab()
        self._build_ai_tab()
        self._build_startup_tab()

        # Bottom buttons.
        self._build_bottom_bar()

    # ── Style ──────────────────────────────────────────────

    def _style_notebook(self) -> None:
        """Configure ttk styles for the dark theme."""
        style = ttk.Style()
        style.theme_use("default")

        style.configure("TNotebook", background=_C.BG, borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=_C.BG2,
            foreground=_C.FG,
            padding=[10, 4],
            font=("Segoe UI", 9),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", _C.ACCENT)],
            foreground=[("selected", _C.BTN_FG)],
        )
        style.configure(
            "TFrame", background=_C.BG,
        )

    # ── Helper: create labelled control ────────────────────

    def _add_row(
        self,
        parent: tk.Frame,
        label: str,
        row: int,
        widget_type: str = "entry",
        var: tk.Variable | None = None,
        values: list[str] | None = None,
        from_: float = 0,
        to_: float = 100,
    ) -> tk.Widget:
        """Add a labelled control row to a settings tab."""
        lbl = tk.Label(
            parent, text=label,
            bg=_C.BG, fg=_C.FG,
            font=("Segoe UI", 10),
            anchor="w",
        )
        lbl.grid(row=row, column=0, sticky="w", padx=10, pady=6)

        widget: tk.Widget

        if widget_type == "entry":
            widget = tk.Entry(
                parent, textvariable=var,
                bg=_C.INPUT_BG, fg=_C.INPUT_FG,
                insertbackground=_C.FG,
                font=("Segoe UI", 10),
                relief=tk.FLAT, bd=4,
            )
        elif widget_type == "combo":
            widget = ttk.Combobox(
                parent, textvariable=var,
                values=values or [],
                state="readonly",
                font=("Segoe UI", 10),
            )
        elif widget_type == "check":
            widget = tk.Checkbutton(
                parent, variable=var,
                bg=_C.BG, fg=_C.FG,
                selectcolor=_C.INPUT_BG,
                activebackground=_C.BG,
                activeforeground=_C.FG,
                font=("Segoe UI", 10),
            )
        elif widget_type == "scale":
            widget = tk.Scale(
                parent, variable=var,
                from_=from_, to=to_,
                orient=tk.HORIZONTAL,
                bg=_C.BG, fg=_C.FG,
                troughcolor=_C.INPUT_BG,
                activebackground=_C.ACCENT,
                highlightthickness=0,
                font=("Segoe UI", 9),
                length=200,
            )
        else:
            widget = tk.Label(parent, text="", bg=_C.BG)

        widget.grid(row=row, column=1, sticky="ew", padx=10, pady=6)

        parent.columnconfigure(1, weight=1)
        return widget

    def _make_frame(self, tab_name: str) -> tk.Frame:
        """Create and register a tab frame."""
        frame = tk.Frame(self._notebook, bg=_C.BG)
        self._notebook.add(frame, text=f"  {tab_name}  ")
        return frame

    # ── Tab Builders ───────────────────────────────────────

    def _build_speech_tab(self) -> None:
        """Speech Engine settings tab."""
        f = self._make_frame("🔊 Speech")

        self._vars["speech_engine"] = tk.StringVar(
            value=self._settings.get("speech_engine", "auto")
        )
        self._add_row(
            f, "Speech Engine:", 0,
            widget_type="combo",
            var=self._vars["speech_engine"],
            values=["auto", "vosk", "whisper", "google"],
        )

        self._vars["recognition_language"] = tk.StringVar(
            value=self._settings.get("recognition_language", "en-us")
        )
        self._add_row(
            f, "Language:", 1,
            widget_type="entry",
            var=self._vars["recognition_language"],
        )

        self._vars["recognition_timeout"] = tk.DoubleVar(
            value=self._settings.get("recognition_timeout", 5.0)
        )
        self._add_row(
            f, "Timeout (seconds):", 2,
            widget_type="scale",
            var=self._vars["recognition_timeout"],
            from_=2.0, to_=15.0,
        )

        self._vars["voice_sensitivity"] = tk.DoubleVar(
            value=self._settings.get("voice_sensitivity", 0.5)
        )
        self._add_row(
            f, "Sensitivity:", 3,
            widget_type="scale",
            var=self._vars["voice_sensitivity"],
            from_=0.0, to_=1.0,
        )

        self._vars["offline_mode"] = tk.BooleanVar(
            value=self._settings.get("offline_mode", True)
        )
        self._add_row(
            f, "Offline Mode:", 4,
            widget_type="check",
            var=self._vars["offline_mode"],
        )

        # Show available engines.
        try:
            from voice.engines.engine_factory import EngineFactory
            available = EngineFactory.list_available()
            info = f"Available engines: {', '.join(available) if available else 'none'}"
        except Exception:
            info = "Could not detect available engines."

        info_label = tk.Label(
            f, text=info,
            bg=_C.BG, fg=_C.FG_DIM,
            font=("Segoe UI", 9),
        )
        info_label.grid(row=5, column=0, columnspan=2, sticky="w", padx=10, pady=10)

    def _build_wake_tab(self) -> None:
        """Wake Word settings tab."""
        f = self._make_frame("🎙 Wake Word")

        self._vars["wake_word_enabled"] = tk.BooleanVar(
            value=self._settings.get("wake_word_enabled", True)
        )
        self._add_row(
            f, "Enable Wake Word:", 0,
            widget_type="check",
            var=self._vars["wake_word_enabled"],
        )

        self._vars["wake_word"] = tk.StringVar(
            value=self._settings.get("wake_word", "jarvis")
        )
        self._add_row(
            f, "Wake Word:", 1,
            widget_type="entry",
            var=self._vars["wake_word"],
        )

        # Info.
        info = tk.Label(
            f,
            text='Say your wake word to activate the assistant.\n'
                 'Example: "Jarvis, open dashboard"',
            bg=_C.BG, fg=_C.FG_DIM,
            font=("Segoe UI", 9),
            justify=tk.LEFT,
        )
        info.grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=20)

    def _build_mic_tab(self) -> None:
        """Microphone settings tab."""
        f = self._make_frame("🎤 Mic")

        # Enumerate audio devices.
        devices = ["System Default"]
        try:
            import sounddevice as sd
            dev_list = sd.query_devices()
            for i, dev in enumerate(dev_list):
                if dev.get("max_input_channels", 0) > 0:
                    devices.append(f"{i}: {dev['name']}")
        except Exception:
            pass

        self._vars["mic_device"] = tk.StringVar(value=devices[0])
        self._add_row(
            f, "Microphone:", 0,
            widget_type="combo",
            var=self._vars["mic_device"],
            values=devices,
        )

        info = tk.Label(
            f,
            text="Select the microphone device for voice input.",
            bg=_C.BG, fg=_C.FG_DIM,
            font=("Segoe UI", 9),
        )
        info.grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=20)

    def _build_overlay_tab(self) -> None:
        """Overlay appearance settings tab."""
        f = self._make_frame("🖥 Overlay")

        self._vars["theme"] = tk.StringVar(
            value=self._settings.get("theme", "dark")
        )
        self._add_row(
            f, "Theme:", 0,
            widget_type="combo",
            var=self._vars["theme"],
            values=["dark", "light"],
        )

        self._vars["overlay_transparency"] = tk.DoubleVar(
            value=self._settings.get("overlay_transparency", 0.9)
        )
        self._add_row(
            f, "Transparency:", 1,
            widget_type="scale",
            var=self._vars["overlay_transparency"],
            from_=0.3, to_=1.0,
        )

        self._vars["animation_speed"] = tk.DoubleVar(
            value=self._settings.get("animation_speed", 1.0)
        )
        self._add_row(
            f, "Animation Speed:", 2,
            widget_type="scale",
            var=self._vars["animation_speed"],
            from_=0.5, to_=2.0,
        )

    def _build_hotkey_tab(self) -> None:
        """Hotkey settings tab."""
        f = self._make_frame("⌨ Hotkey")

        self._vars["hotkey"] = tk.StringVar(
            value=self._settings.get("hotkey", "ctrl+shift+m")
        )
        self._add_row(
            f, "Activation Hotkey:", 0,
            widget_type="entry",
            var=self._vars["hotkey"],
        )

        info = tk.Label(
            f,
            text='Press this hotkey combination to activate the microphone.\n'
                 'Examples: "ctrl+shift+m", "alt+space", "f1"',
            bg=_C.BG, fg=_C.FG_DIM,
            font=("Segoe UI", 9),
            justify=tk.LEFT,
        )
        info.grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=20)

    def _build_logging_tab(self) -> None:
        """Logging settings tab."""
        f = self._make_frame("📋 Logging")

        self._vars["logging_enabled"] = tk.BooleanVar(
            value=self._settings.get("logging_enabled", True)
        )
        self._add_row(
            f, "Enable Logging:", 0,
            widget_type="check",
            var=self._vars["logging_enabled"],
        )

        self._vars["command_history_enabled"] = tk.BooleanVar(
            value=self._settings.get("command_history_enabled", True)
        )
        self._add_row(
            f, "Enable Command History:", 1,
            widget_type="check",
            var=self._vars["command_history_enabled"],
        )

        self._vars["fuzzy_threshold"] = tk.IntVar(
            value=self._settings.get("fuzzy_threshold", 75)
        )
        self._add_row(
            f, "Fuzzy Match Threshold:", 2,
            widget_type="scale",
            var=self._vars["fuzzy_threshold"],
            from_=50, to_=100,
        )

        # Clear history button.
        clear_btn = tk.Button(
            f, text="🗑  Clear Command History",
            bg=_C.INPUT_BG, fg=_C.FG,
            activebackground="#f38ba8",
            activeforeground="white",
            font=("Segoe UI", 10),
            relief=tk.FLAT, bd=4,
            command=self._clear_history,
        )
        clear_btn.grid(row=3, column=0, columnspan=2, padx=10, pady=20)

    def _build_ai_tab(self) -> None:
        """AI Fallback settings tab."""
        f = self._make_frame("🤖 AI")

        self._vars["ai_fallback_enabled"] = tk.BooleanVar(
            value=self._settings.get("ai_fallback_enabled", True)
        )
        self._add_row(
            f, "Enable AI Fallback:", 0,
            widget_type="check",
            var=self._vars["ai_fallback_enabled"],
        )

        info = tk.Label(
            f,
            text="When enabled, unrecognised commands are forwarded\n"
                 "to the AI assistant for a freeform response.\n\n"
                 'Examples:\n'
                 '  • "Explain Laplace Transform"\n'
                 '  • "What should I eat?"\n'
                 '  • "Write Python code for a linked list"',
            bg=_C.BG, fg=_C.FG_DIM,
            font=("Segoe UI", 9),
            justify=tk.LEFT,
        )
        info.grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=10)

    def _build_startup_tab(self) -> None:
        """Startup settings tab."""
        f = self._make_frame("🚀 Startup")

        self._vars["auto_startup"] = tk.BooleanVar(
            value=self._settings.get("auto_startup", False)
        )
        self._add_row(
            f, "Start with Windows:", 0,
            widget_type="check",
            var=self._vars["auto_startup"],
        )

        info = tk.Label(
            f,
            text="When enabled, the voice overlay starts\n"
                 "automatically when Windows starts.\n\n"
                 "Uses the Windows Registry to add a startup entry.",
            bg=_C.BG, fg=_C.FG_DIM,
            font=("Segoe UI", 9),
            justify=tk.LEFT,
        )
        info.grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=20)

    # ── Bottom Bar ─────────────────────────────────────────

    def _build_bottom_bar(self) -> None:
        """Build Save / Reset / Cancel buttons."""
        bar = tk.Frame(self._win, bg=_C.BG)
        bar.pack(fill=tk.X, padx=10, pady=(5, 10))

        tk.Button(
            bar, text="💾  Save",
            bg=_C.BTN_BG, fg=_C.BTN_FG,
            activebackground=_C.ACCENT2,
            font=("Segoe UI", 10, "bold"),
            relief=tk.FLAT, bd=6,
            command=self._save_settings,
        ).pack(side=tk.RIGHT, padx=4)

        tk.Button(
            bar, text="🔄  Reset Defaults",
            bg=_C.INPUT_BG, fg=_C.FG,
            activebackground=_C.INPUT_BG,
            font=("Segoe UI", 10),
            relief=tk.FLAT, bd=6,
            command=self._reset_defaults,
        ).pack(side=tk.RIGHT, padx=4)

        tk.Button(
            bar, text="Cancel",
            bg=_C.INPUT_BG, fg=_C.FG,
            activebackground=_C.INPUT_BG,
            font=("Segoe UI", 10),
            relief=tk.FLAT, bd=6,
            command=self._win.destroy,
        ).pack(side=tk.RIGHT, padx=4)

    # ── Actions ────────────────────────────────────────────

    def _save_settings(self) -> None:
        """Save all settings from the GUI."""
        for key, var in self._vars.items():
            try:
                value = var.get()

                # Special handling for mic device index.
                if key == "mic_device":
                    if value == "System Default":
                        self._settings.set("mic_device_index", None)
                    else:
                        # Extract device index from "0: Device Name".
                        idx = int(value.split(":")[0])
                        self._settings.set("mic_device_index", idx)
                    continue

                self._settings.set(key, value)
            except Exception as exc:
                _log.debug("Failed to save setting '%s': %s", key, exc)

        self._settings.save()
        messagebox.showinfo(
            "Settings Saved",
            "Settings have been saved successfully.\n"
            "Some changes may require a restart.",
            parent=self._win,
        )

    def _reset_defaults(self) -> None:
        """Reset all settings to defaults."""
        confirm = messagebox.askyesno(
            "Reset Settings",
            "Reset all settings to defaults?",
            parent=self._win,
        )
        if confirm:
            self._settings.reset_defaults()
            self._win.destroy()

    def _clear_history(self) -> None:
        """Clear the voice command history."""
        confirm = messagebox.askyesno(
            "Clear History",
            "Delete all voice command history?",
            parent=self._win,
        )
        if confirm:
            try:
                from voice.command_history import CommandHistory
                history = CommandHistory()
                history.clear()
                messagebox.showinfo(
                    "History Cleared",
                    "Voice command history has been cleared.",
                    parent=self._win,
                )
            except Exception as exc:
                _log.error("Clear history error: %s", exc)
