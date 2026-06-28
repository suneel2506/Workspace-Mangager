"""
============================================================
  voice/ package — Voice-Controlled Desktop Assistant
============================================================

This package implements the voice control overlay system for
the Workspace Automation System.  It is fully independent of
the existing GUI dashboard and communicates via an event bus.

Subpackages
-----------
engines/
    Speech-to-text engine implementations (Vosk, Whisper, Google).
plugins/
    Auto-discovered command plugins.

Modules
-------
event_bus.py
    Pub/sub event bus for decoupled communication.
overlay.py
    Floating microphone widget (always-on-top Tkinter window).
speech_engine.py
    Abstract base class for speech engines (Strategy pattern).
command_registry.py
    Fuzzy-matched command registry with plugin support.
command_executor.py
    Command execution engine with AI fallback.
command_history.py
    Searchable command history (SQLite-backed).
wake_word.py
    Low-power wake word detection manager.
settings_manager.py
    JSON-persisted voice assistant settings.
settings_window.py
    Tkinter settings GUI.
voice_logger.py
    Separated, rotating log system.
============================================================
"""

from __future__ import annotations

__all__: list[str] = [
    "EventBus",
    "CommandRegistry",
    "CommandExecutor",
    "SettingsManager",
    "VoiceOverlay",
]
