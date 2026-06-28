"""
============================================================
  overlay.py — Floating Microphone Widget (Voice Overlay)
============================================================

PURPOSE:
    A tiny, always-on-top, draggable, frameless Tkinter window
    that acts as the primary voice assistant interface.  Shows a
    microphone icon and animates through 6 states.

STATES:
    Idle      — Static mic icon, subtle breathing glow
    Listening — Pulsing blue rings, "Listening..." text
    Thinking  — Spinning dots, "Processing..." text
    Executing — Yellow glow, matched command text
    Success   — Green flash, result text (2s auto-fade)
    Error     — Red flash, error text (3s auto-fade)

FEATURES:
    * Always-on-top frameless window (overrideredirect)
    * Draggable via mouse press+drag
    * Click to activate listening
    * Right-click for context menu
    * Smooth fade in/out for status popup
    * Event-bus driven (subscribes to speech/command events)
    * All animations via tkinter .after() — no threads for UI
    * Near-zero CPU when idle

USAGE:
    from voice.overlay import VoiceOverlay
    overlay = VoiceOverlay()
    overlay.run()
============================================================
"""

from __future__ import annotations

import logging
import math
import sys
import threading
import tkinter as tk
from enum import Enum, auto
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from voice.event_bus import EventBus
    from voice.settings_manager import SettingsManager
    from voice.command_registry import CommandRegistry
    from voice.command_executor import CommandExecutor
    from voice.command_history import CommandHistory
    from voice.wake_word import WakeWordManager

_log: logging.Logger = logging.getLogger(__name__)


# ── Overlay States ─────────────────────────────────────────

class OverlayState(Enum):
    """Visual states of the floating overlay."""
    IDLE = auto()
    LISTENING = auto()
    THINKING = auto()
    EXECUTING = auto()
    SUCCESS = auto()
    ERROR = auto()


# ── Color Palette ──────────────────────────────────────────

class _Colors:
    """Dark theme color constants for the overlay."""
    BG = "#1e1e2e"
    MIC_IDLE = "#89b4fa"
    MIC_LISTENING = "#74c7ec"
    MIC_THINKING = "#f9e2af"
    MIC_EXECUTING = "#fab387"
    MIC_SUCCESS = "#a6e3a1"
    MIC_ERROR = "#f38ba8"
    RING = "#89b4fa"
    TEXT = "#cdd6f4"
    TEXT_DIM = "#6c7086"
    POPUP_BG = "#313244"
    POPUP_BORDER = "#45475a"
    TRANSPARENT = "#010101"


# ── Main Overlay Class ────────────────────────────────────

class VoiceOverlay:
    """
    Floating microphone widget for voice-controlled assistant.

    Creates a frameless, always-on-top Tkinter window with a
    circular mic button.  Manages the full voice pipeline:
    wake word → speech engine → command registry → executor.

    Usage
    -----
    ::
        overlay = VoiceOverlay()
        overlay.run()  # Blocks (enters Tk mainloop)
    """

    # Widget dimensions.
    MIC_SIZE: int = 64
    POPUP_WIDTH: int = 300
    POPUP_HEIGHT: int = 60

    def __init__(self) -> None:
        # ── State ──────────────────────────────────────────
        self._state: OverlayState = OverlayState.IDLE
        self._animation_id: str | None = None
        self._pulse_phase: float = 0.0
        self._breathing_phase: float = 0.0
        self._drag_data: dict[str, int] = {"x": 0, "y": 0}
        self._popup_visible: bool = False
        self._popup_after_id: str | None = None

        # ── Core components (created in _init_components) ──
        self._event_bus: EventBus | None = None
        self._settings: SettingsManager | None = None
        self._registry: CommandRegistry | None = None
        self._executor: CommandExecutor | None = None
        self._history: CommandHistory | None = None
        self._wake_manager: WakeWordManager | None = None
        self._engine: Any = None
        self._speaker: Any = None
        self._assistant: Any = None

        # ── Tkinter widgets (created in _build_ui) ─────────
        self._root: tk.Tk | None = None
        self._canvas: tk.Canvas | None = None
        self._popup_frame: tk.Frame | None = None
        self._popup_label: tk.Label | None = None
        self._mic_circle_id: int = 0
        self._mic_icon_id: int = 0
        self._ring_ids: list[int] = []

    # ── Public API ─────────────────────────────────────────

    def run(self) -> None:
        """Build the overlay and enter the main loop."""
        self._build_ui()
        self._init_components()
        self._subscribe_events()
        self._start_breathing()

        _log.info("Voice overlay started.")
        print("  [✓] Voice overlay is running. Click the mic or say your wake word.")

        assert self._root is not None
        self._root.mainloop()

    # ── UI Construction ────────────────────────────────────

    def _build_ui(self) -> None:
        """Create the Tkinter window and canvas."""
        root = tk.Tk()
        root.title("Voice Assistant")
        root.overrideredirect(True)          # No title bar.
        root.attributes("-topmost", True)    # Always on top.
        root.attributes("-alpha", 0.95)      # Slight transparency.

        # Transparent background trick (Windows).
        root.configure(bg=_Colors.TRANSPARENT)
        try:
            root.attributes("-transparentcolor", _Colors.TRANSPARENT)
        except tk.TclError:
            root.configure(bg=_Colors.BG)

        # Position (from settings or default).
        root.geometry(f"{self.MIC_SIZE}x{self.MIC_SIZE}+50+50")

        # ── Mic canvas ─────────────────────────────────────
        canvas = tk.Canvas(
            root,
            width=self.MIC_SIZE,
            height=self.MIC_SIZE,
            bg=_Colors.TRANSPARENT,
            highlightthickness=0,
            bd=0,
        )
        canvas.pack()

        # Draw the mic circle.
        pad = 4
        self._mic_circle_id = canvas.create_oval(
            pad, pad,
            self.MIC_SIZE - pad, self.MIC_SIZE - pad,
            fill=_Colors.MIC_IDLE,
            outline="",
            width=0,
        )

        # Draw the mic icon (Unicode character).
        self._mic_icon_id = canvas.create_text(
            self.MIC_SIZE // 2,
            self.MIC_SIZE // 2,
            text="🎤",
            font=("Segoe UI Emoji", 20),
            fill="white",
        )

        # ── Event bindings ─────────────────────────────────
        canvas.bind("<Button-1>", self._on_click)
        canvas.bind("<Button-3>", self._on_right_click)
        canvas.bind("<ButtonPress-1>", self._on_drag_start)
        canvas.bind("<B1-Motion>", self._on_drag_motion)

        # ── Status popup (hidden by default) ───────────────
        popup = tk.Frame(
            root,
            bg=_Colors.POPUP_BG,
            highlightbackground=_Colors.POPUP_BORDER,
            highlightthickness=1,
            padx=10,
            pady=6,
        )
        popup_label = tk.Label(
            popup,
            text="",
            bg=_Colors.POPUP_BG,
            fg=_Colors.TEXT,
            font=("Segoe UI", 9),
            wraplength=self.POPUP_WIDTH - 30,
            justify=tk.LEFT,
        )
        popup_label.pack()

        self._root = root
        self._canvas = canvas
        self._popup_frame = popup
        self._popup_label = popup_label

    # ── Component Initialisation ───────────────────────────

    def _init_components(self) -> None:
        """Initialise all voice pipeline components."""
        try:
            from voice.event_bus import EventBus
            from voice.settings_manager import SettingsManager
            from voice.command_registry import CommandRegistry
            from voice.command_executor import CommandExecutor
            from voice.command_history import CommandHistory
            from voice.wake_word import WakeWordManager

            # Infrastructure.
            self._event_bus = EventBus()
            self._settings = SettingsManager(event_bus=self._event_bus)
            self._history = CommandHistory()

            # Command system.
            self._registry = CommandRegistry(settings=self._settings)
            self._registry.load_plugins()

            # Speech engine.
            self._init_speech_engine()

            # Assistant and executor.
            self._init_assistant()

            # Inject Assistant into plugins that need it.
            self._inject_plugin_dependencies()

            # Wake word.
            self._wake_manager = WakeWordManager(
                event_bus=self._event_bus,
                settings=self._settings,
            )

            # Start wake word detection if enabled.
            if self._settings.get("wake_word_enabled", True):
                self._wake_manager.start()

            # Register global hotkey if possible.
            self._register_hotkey()

        except Exception as exc:
            _log.exception("Component initialisation error: %s", exc)
            self._show_popup(f"Init error: {exc}", duration=5000)

    def _init_speech_engine(self) -> None:
        """Create the speech engine via the factory."""
        try:
            from voice.engines.engine_factory import EngineFactory

            preference = "auto"
            if self._settings is not None:
                preference = self._settings.get("speech_engine", "auto")

            self._engine = EngineFactory.create(
                preference=preference,
                settings=self._settings,
            )
            _log.info("Speech engine: %s", self._engine.name)
            self._show_popup(f"Engine: {self._engine.name}", duration=2000)
        except RuntimeError as exc:
            _log.error("No speech engine available: %s", exc)
            self._show_popup("No speech engine! Install vosk.", duration=5000)

    def _init_assistant(self) -> None:
        """Create the Assistant and CommandExecutor."""
        try:
            from core.assistant import Assistant
            from core.ai_manager import AIManager
            from voice.command_executor import CommandExecutor

            self._assistant = Assistant()

            ai_manager = getattr(self._assistant, "ai", None)
            if ai_manager is None:
                ai_manager = AIManager()

            assert self._registry is not None
            assert self._event_bus is not None

            self._executor = CommandExecutor(
                assistant=self._assistant,
                registry=self._registry,
                event_bus=self._event_bus,
                ai_manager=ai_manager,
            )
        except Exception as exc:
            _log.error("Assistant init error: %s", exc)

    def _inject_plugin_dependencies(self) -> None:
        """Inject Assistant/SystemControl into plugins that need them."""
        if self._registry is None:
            return

        # Find plugin instances by iterating loaded modules.
        try:
            import voice.plugins.dashboard_plugin as dp
            import voice.plugins.workspace_plugin as wp
            import voice.plugins.utility_plugin as up

            # The plugins register singletons; we need to find them.
            for cmd in self._registry._commands:
                handler_self = getattr(cmd.handler, "__self__", None)
                if handler_self is None:
                    continue

                cls_name = type(handler_self).__name__

                if cls_name == "DashboardPlugin":
                    handler_self.set_assistant(self._assistant)
                elif cls_name == "WorkspacePlugin":
                    handler_self.set_assistant(self._assistant)
                elif cls_name == "UtilityPlugin":
                    handler_self.set_assistant(self._assistant)

        except Exception as exc:
            _log.debug("Plugin dependency injection partial: %s", exc)

    # ── Event Bus Subscriptions ────────────────────────────

    def _subscribe_events(self) -> None:
        """Subscribe to event bus topics."""
        if self._event_bus is None:
            return

        from voice.event_bus import Topics

        self._event_bus.subscribe(Topics.SPEECH_RESULT, self._on_speech_result)
        self._event_bus.subscribe(Topics.SPEECH_ERROR, self._on_speech_error)
        self._event_bus.subscribe(Topics.COMMAND_MATCHED, self._on_command_matched)
        self._event_bus.subscribe(Topics.COMMAND_SUCCESS, self._on_command_success)
        self._event_bus.subscribe(Topics.COMMAND_ERROR, self._on_command_error)
        self._event_bus.subscribe(Topics.COMMAND_AI_FALLBACK, self._on_ai_fallback)
        self._event_bus.subscribe(Topics.WAKE_DETECTED, self._on_wake_detected)

    # ── Event Handlers ─────────────────────────────────────

    def _on_speech_result(self, data: dict[str, Any]) -> None:
        """Handle transcription result."""
        text = data.get("text", "")
        if text and self._root:
            self._root.after(0, lambda: self._show_popup(f'"{text}"', duration=2000))

    def _on_speech_error(self, data: dict[str, Any]) -> None:
        """Handle speech error."""
        error = data.get("error", "Recognition error")
        if self._root:
            self._root.after(0, lambda: self._set_state(OverlayState.ERROR))
            self._root.after(0, lambda: self._show_popup(f"⚠ {error}", duration=3000))

    def _on_command_matched(self, data: dict[str, Any]) -> None:
        """Handle command match."""
        if self._root:
            self._root.after(0, lambda: self._set_state(OverlayState.EXECUTING))

    def _on_command_success(self, data: dict[str, Any]) -> None:
        """Handle command success."""
        result = data.get("result", "Done.")
        if self._root:
            self._root.after(0, lambda: self._set_state(OverlayState.SUCCESS))
            self._root.after(0, lambda: self._show_popup(f"✓ {result}", duration=3000))
            self._root.after(3000, lambda: self._set_state(OverlayState.IDLE))

    def _on_command_error(self, data: dict[str, Any]) -> None:
        """Handle command error."""
        error = data.get("error", "Error")
        if self._root:
            self._root.after(0, lambda: self._set_state(OverlayState.ERROR))
            self._root.after(0, lambda: self._show_popup(f"✗ {error}", duration=4000))
            self._root.after(4000, lambda: self._set_state(OverlayState.IDLE))

    def _on_ai_fallback(self, data: dict[str, Any]) -> None:
        """Handle AI fallback response."""
        response = data.get("response", "")
        if self._root:
            self._root.after(0, lambda: self._set_state(OverlayState.SUCCESS))
            self._root.after(0, lambda: self._show_popup(f"🤖 {response}", duration=5000))
            self._root.after(5000, lambda: self._set_state(OverlayState.IDLE))

    def _on_wake_detected(self, data: dict[str, Any]) -> None:
        """Handle wake word detection."""
        word = data.get("word", "")
        _log.info("Wake word '%s' detected — activating.", word)
        if self._root:
            self._root.after(0, self._activate_listening)

    # ── Click / Drag Handlers ──────────────────────────────

    def _on_click(self, event: tk.Event) -> None:
        """Handle click on the mic button."""
        if self._state == OverlayState.LISTENING:
            # Cancel listening.
            self._set_state(OverlayState.IDLE)
        else:
            self._activate_listening()

    def _on_right_click(self, event: tk.Event) -> None:
        """Show context menu on right-click."""
        menu = tk.Menu(self._root, tearoff=0)
        menu.configure(
            bg=_Colors.POPUP_BG,
            fg=_Colors.TEXT,
            activebackground=_Colors.MIC_IDLE,
            activeforeground="white",
            font=("Segoe UI", 9),
        )
        menu.add_command(label="📊  Open Dashboard", command=self._cmd_open_dashboard)
        menu.add_command(label="⚙️  Settings", command=self._cmd_open_settings)
        menu.add_command(label="📋  Command History", command=self._cmd_show_history)
        menu.add_separator()
        menu.add_command(label="🔄  Restart", command=self._cmd_restart)
        menu.add_command(label="❌  Exit", command=self._cmd_exit)

        assert self._root is not None
        try:
            menu.tk_popup(
                self._root.winfo_rootx() + event.x,
                self._root.winfo_rooty() + event.y,
            )
        finally:
            menu.grab_release()

    def _on_drag_start(self, event: tk.Event) -> None:
        """Record the drag start position."""
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _on_drag_motion(self, event: tk.Event) -> None:
        """Move the overlay window on drag."""
        assert self._root is not None
        x = self._root.winfo_x() + (event.x - self._drag_data["x"])
        y = self._root.winfo_y() + (event.y - self._drag_data["y"])
        self._root.geometry(f"+{x}+{y}")

        # Save position.
        if self._settings is not None:
            self._settings.set("overlay_position_x", x)
            self._settings.set("overlay_position_y", y)

    # ── Voice Pipeline ─────────────────────────────────────

    def _activate_listening(self) -> None:
        """Start the listen → process cycle."""
        if self._state == OverlayState.LISTENING:
            return

        self._set_state(OverlayState.LISTENING)
        self._show_popup("🎤 Listening...", duration=0)

        # Pause wake word during active listening.
        if self._wake_manager is not None:
            self._wake_manager.pause()

        # Run speech recognition in a background thread.
        thread = threading.Thread(
            target=self._listen_and_process,
            daemon=True,
            name="ListenThread",
        )
        thread.start()

    def _listen_and_process(self) -> None:
        """Background: listen → execute → return to idle."""
        try:
            if self._engine is None:
                self._schedule_ui(lambda: self._set_state(OverlayState.ERROR))
                self._schedule_ui(
                    lambda: self._show_popup("No speech engine.", duration=3000)
                )
                return

            # Ensure engine is started.
            if not getattr(self._engine, "_started", False):
                self._engine.start()

            # Listen.
            timeout = 5.0
            if self._settings is not None:
                timeout = self._settings.get("recognition_timeout", 5.0)

            result = self._engine.listen(timeout=timeout)

            if not result.text:
                self._schedule_ui(lambda: self._set_state(OverlayState.IDLE))
                self._schedule_ui(
                    lambda: self._show_popup("Didn't catch that.", duration=2000)
                )
                return

            # Update UI with recognised text.
            text = result.text
            self._schedule_ui(lambda: self._set_state(OverlayState.THINKING))
            self._schedule_ui(lambda: self._show_popup(f'"{text}"', duration=0))

            # Execute.
            if self._executor is not None:
                exec_result = self._executor.execute(
                    text, engine_name=result.engine_name
                )

                # Log to history.
                self._log_to_history(result, exec_result)

                # Speak the result.
                self._speak(exec_result.result)

                # UI updates happen via event bus callbacks.
            else:
                self._schedule_ui(lambda: self._set_state(OverlayState.ERROR))
                self._schedule_ui(
                    lambda: self._show_popup("Executor not ready.", duration=3000)
                )

        except Exception as exc:
            _log.exception("Listen/process error: %s", exc)
            self._schedule_ui(lambda: self._set_state(OverlayState.ERROR))
            err_msg = str(exc)[:100]
            self._schedule_ui(
                lambda: self._show_popup(f"Error: {err_msg}", duration=4000)
            )

        finally:
            # Resume wake word detection.
            if self._wake_manager is not None:
                self._wake_manager.resume()

            # Return to idle after delay.
            self._schedule_ui(
                lambda: self._set_state(OverlayState.IDLE),
                delay=5000,
            )

    def _speak(self, text: str) -> None:
        """Speak the result using the existing Speaker."""
        try:
            if self._speaker is None:
                from core.speaker import Speaker
                self._speaker = Speaker()

            if text and self._speaker.is_available():
                self._speaker.speak(text)
        except Exception as exc:
            _log.debug("TTS error: %s", exc)

    def _log_to_history(self, speech_result: Any, exec_result: Any) -> None:
        """Log the command to history."""
        if self._history is not None:
            try:
                from voice.command_history import HistoryEntry
                entry = HistoryEntry(
                    recognized_speech=speech_result.text,
                    matched_command=exec_result.intent,
                    confidence=exec_result.confidence,
                    execution_time_ms=exec_result.duration_ms,
                    result=exec_result.result[:500],
                    engine=speech_result.engine_name,
                )
                self._history.add(entry)
            except Exception as exc:
                _log.debug("History logging error: %s", exc)

    # ── State Machine ──────────────────────────────────────

    def _set_state(self, new_state: OverlayState) -> None:
        """Transition the overlay to a new visual state."""
        if self._state == new_state:
            return

        old_state = self._state
        self._state = new_state

        # Cancel running animation.
        if self._animation_id is not None and self._root is not None:
            self._root.after_cancel(self._animation_id)
            self._animation_id = None

        # Clear pulse rings.
        self._clear_rings()

        # Update mic circle color.
        color = {
            OverlayState.IDLE: _Colors.MIC_IDLE,
            OverlayState.LISTENING: _Colors.MIC_LISTENING,
            OverlayState.THINKING: _Colors.MIC_THINKING,
            OverlayState.EXECUTING: _Colors.MIC_EXECUTING,
            OverlayState.SUCCESS: _Colors.MIC_SUCCESS,
            OverlayState.ERROR: _Colors.MIC_ERROR,
        }.get(new_state, _Colors.MIC_IDLE)

        if self._canvas is not None:
            self._canvas.itemconfigure(self._mic_circle_id, fill=color)

        # Start state-specific animation.
        if new_state == OverlayState.IDLE:
            self._start_breathing()
        elif new_state == OverlayState.LISTENING:
            self._start_pulse()
        elif new_state == OverlayState.THINKING:
            self._start_thinking()

        # Emit state change event.
        if self._event_bus is not None:
            self._event_bus.emit_async("overlay.state_change", {
                "state": new_state.name.lower(),
                "old_state": old_state.name.lower(),
            })

    # ── Animations ─────────────────────────────────────────

    def _start_breathing(self) -> None:
        """Subtle breathing glow on idle."""
        if self._state != OverlayState.IDLE or self._root is None:
            return

        self._breathing_phase += 0.05
        alpha = 0.85 + 0.1 * math.sin(self._breathing_phase)
        try:
            self._root.attributes("-alpha", alpha)
        except tk.TclError:
            pass

        self._animation_id = self._root.after(60, self._start_breathing)

    def _start_pulse(self) -> None:
        """Pulsing blue rings during listening."""
        if self._state != OverlayState.LISTENING:
            return
        if self._canvas is None or self._root is None:
            return

        self._pulse_phase += 0.15
        cx = self.MIC_SIZE // 2
        cy = self.MIC_SIZE // 2

        # Clear previous rings.
        self._clear_rings()

        # Draw expanding ring.
        radius = 20 + 15 * math.sin(self._pulse_phase)
        alpha_sim = max(0.2, 1.0 - (radius - 20) / 15)

        ring = self._canvas.create_oval(
            cx - radius, cy - radius,
            cx + radius, cy + radius,
            outline=_Colors.RING,
            width=2,
            dash=(4, 4),
        )
        self._ring_ids.append(ring)

        # Ensure mic stays on top.
        self._canvas.tag_raise(self._mic_circle_id)
        self._canvas.tag_raise(self._mic_icon_id)

        self._animation_id = self._root.after(50, self._start_pulse)

    def _start_thinking(self) -> None:
        """Spinning dots during processing."""
        if self._state != OverlayState.THINKING:
            return
        if self._canvas is None or self._root is None:
            return

        self._pulse_phase += 0.2
        cx = self.MIC_SIZE // 2
        cy = self.MIC_SIZE // 2

        self._clear_rings()

        # Draw 3 rotating dots.
        for i in range(3):
            angle = self._pulse_phase + (i * 2.094)  # 120° apart
            dx = cx + 22 * math.cos(angle)
            dy = cy + 22 * math.sin(angle)
            dot = self._canvas.create_oval(
                dx - 3, dy - 3, dx + 3, dy + 3,
                fill=_Colors.MIC_THINKING,
                outline="",
            )
            self._ring_ids.append(dot)

        self._canvas.tag_raise(self._mic_circle_id)
        self._canvas.tag_raise(self._mic_icon_id)

        self._animation_id = self._root.after(50, self._start_thinking)

    def _clear_rings(self) -> None:
        """Remove all animation ring elements from canvas."""
        if self._canvas is not None:
            for ring_id in self._ring_ids:
                try:
                    self._canvas.delete(ring_id)
                except tk.TclError:
                    pass
        self._ring_ids.clear()

    # ── Status Popup ───────────────────────────────────────

    def _show_popup(self, text: str, duration: int = 3000) -> None:
        """
        Show a status popup above the mic button.

        Parameters
        ----------
        text : str
            Text to display.
        duration : int
            Auto-hide after this many milliseconds.
            0 means stay visible until explicitly hidden.
        """
        if self._popup_label is None or self._popup_frame is None:
            return
        if self._root is None:
            return

        # Cancel pending hide.
        if self._popup_after_id is not None:
            self._root.after_cancel(self._popup_after_id)
            self._popup_after_id = None

        self._popup_label.configure(text=text[:200])

        if not self._popup_visible:
            # Position above the mic.
            self._popup_frame.place(
                x=-(self.POPUP_WIDTH - self.MIC_SIZE) // 2,
                y=-(self.POPUP_HEIGHT + 8),
                width=self.POPUP_WIDTH,
            )

            # Resize window to accommodate popup.
            total_w = max(self.MIC_SIZE, self.POPUP_WIDTH)
            total_h = self.MIC_SIZE + self.POPUP_HEIGHT + 16
            x = self._root.winfo_x()
            y = self._root.winfo_y()

            # Re-place canvas lower.
            self._canvas.place(
                x=(total_w - self.MIC_SIZE) // 2,
                y=self.POPUP_HEIGHT + 8,
            )

            # Re-place popup.
            self._popup_frame.place(
                x=(total_w - self.POPUP_WIDTH) // 2,
                y=0,
                width=self.POPUP_WIDTH,
            )

            self._root.geometry(
                f"{total_w}x{total_h}+{x}+{max(0, y - self.POPUP_HEIGHT - 8)}"
            )
            self._popup_visible = True

        if duration > 0:
            self._popup_after_id = self._root.after(duration, self._hide_popup)

    def _hide_popup(self) -> None:
        """Hide the status popup and shrink the window."""
        if self._popup_frame is None or self._root is None:
            return

        self._popup_frame.place_forget()

        # Restore the mic canvas to its normal position.
        if self._canvas is not None:
            self._canvas.place(x=0, y=0)

        # Retrieve saved position.
        saved_x = 50
        saved_y = 50
        if self._settings is not None:
            saved_x = self._settings.get("overlay_position_x", 50)
            saved_y = self._settings.get("overlay_position_y", 50)

        self._root.geometry(f"{self.MIC_SIZE}x{self.MIC_SIZE}+{saved_x}+{saved_y}")
        self._popup_visible = False

    # ── Context Menu Commands ──────────────────────────────

    def _cmd_open_dashboard(self) -> None:
        """Open the dashboard from context menu."""
        if self._executor is not None:
            threading.Thread(
                target=lambda: self._executor.execute("open dashboard"),
                daemon=True,
            ).start()

    def _cmd_open_settings(self) -> None:
        """Open the settings window."""
        try:
            from voice.settings_window import SettingsWindow
            assert self._settings is not None
            SettingsWindow(self._root, self._settings)
        except Exception as exc:
            _log.error("Settings window error: %s", exc)

    def _cmd_show_history(self) -> None:
        """Show command history in a popup."""
        if self._history is not None:
            recent = self._history.get_recent(limit=10)
            if recent:
                lines = [
                    f"• {e['recognized_speech']} → {e['matched_command']}"
                    for e in recent[:5]
                ]
                self._show_popup("\n".join(lines), duration=8000)
            else:
                self._show_popup("No command history yet.", duration=3000)

    def _cmd_restart(self) -> None:
        """Restart the overlay."""
        import os
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def _cmd_exit(self) -> None:
        """Exit the overlay."""
        if self._wake_manager is not None:
            self._wake_manager.stop()
        if self._settings is not None:
            self._settings.save()
        if self._root is not None:
            self._root.destroy()
        sys.exit(0)

    # ── Helpers ────────────────────────────────────────────

    def _schedule_ui(
        self,
        func: Any,
        delay: int = 0,
    ) -> None:
        """Schedule a function call on the Tk main thread."""
        if self._root is not None:
            try:
                self._root.after(delay, func)
            except tk.TclError:
                pass  # Window was destroyed.

    def _register_hotkey(self) -> None:
        """Register the global hotkey for mic activation."""
        try:
            import keyboard

            hotkey = "ctrl+shift+m"
            if self._settings is not None:
                hotkey = self._settings.get("hotkey", "ctrl+shift+m")

            keyboard.add_hotkey(
                hotkey,
                lambda: self._root.after(0, self._activate_listening)
                if self._root else None,
            )
            _log.info("Global hotkey registered: %s", hotkey)
        except ImportError:
            _log.debug("keyboard module not installed — hotkey disabled.")
        except Exception as exc:
            _log.debug("Hotkey registration failed: %s", exc)
