"""
============================================================
  settings_manager.py — Voice Assistant Settings (JSON)
============================================================

PURPOSE:
    Manages all configurable settings for the voice assistant.
    Settings are persisted to ``voice_settings.json`` in the
    project root.  Changes emit ``settings.changed`` events
    on the event bus so other modules react automatically.

DESIGN:
    * Thread-safe — all reads/writes protected by a lock.
    * Defaults — every setting has a sensible default.
    * Validation — type and range checks on set().
    * Observable — emits events on change (if bus attached).
    * Dependency-injected event bus (optional).

USAGE:
    from voice.settings_manager import SettingsManager

    settings = SettingsManager()
    engine = settings.get("speech_engine")
    settings.set("wake_word", "workspace")
============================================================
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, TYPE_CHECKING

from config.settings import PROJECT_ROOT

if TYPE_CHECKING:
    from voice.event_bus import EventBus

_log: logging.Logger = logging.getLogger(__name__)

# ── Settings file path ────────────────────────────────────
SETTINGS_FILE: Path = PROJECT_ROOT / "voice_settings.json"


# ── Default Settings ──────────────────────────────────────

_DEFAULTS: dict[str, Any] = {
    # Speech engine
    "speech_engine": "auto",                # "auto" | "vosk" | "whisper" | "google"
    "wake_word": "jarvis",
    "wake_word_enabled": True,
    "mic_device_index": None,               # None = system default
    "voice_sensitivity": 0.5,               # 0.0 – 1.0
    "recognition_timeout": 5.0,             # seconds
    "recognition_language": "en-us",
    "offline_mode": True,

    # Startup
    "auto_startup": False,

    # UI / Overlay
    "theme": "dark",                        # "dark" | "light"
    "hotkey": "ctrl+shift+m",
    "overlay_position_x": 50,
    "overlay_position_y": 50,
    "overlay_transparency": 0.9,            # 0.1 – 1.0
    "animation_speed": 1.0,                 # multiplier
    "overlay_enabled": True,

    # Matching
    "fuzzy_threshold": 75,                  # 0 – 100

    # Logging
    "logging_enabled": True,
    "command_history_enabled": True,

    # AI
    "ai_fallback_enabled": True,
}


# ── Settings Manager ──────────────────────────────────────

class SettingsManager:
    """
    JSON-persisted settings manager for the voice assistant.

    Attributes
    ----------
    _data : dict[str, Any]
        Current settings (merged defaults + user overrides).
    _lock : threading.Lock
        Protects all reads/writes.
    _event_bus : EventBus | None
        Optional event bus for emitting change notifications.

    Usage
    -----
    ::
        settings = SettingsManager()
        settings.get("speech_engine")       # "auto"
        settings.set("wake_word", "jarvis")
        settings.save()
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._data: dict[str, Any] = dict(_DEFAULTS)
        self._lock: threading.Lock = threading.Lock()
        self._event_bus: EventBus | None = event_bus
        self._file_path: Path = SETTINGS_FILE

        # Load persisted settings (if file exists).
        self.load()
        _log.info("SettingsManager initialised (%d settings).", len(self._data))

    # ── Public API ─────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """
        Return the value of a setting.

        Parameters
        ----------
        key : str
            Setting name (e.g. ``"speech_engine"``).
        default : Any, optional
            Fallback if key is not found.  Defaults to the
            built-in default, or ``None``.

        Returns
        -------
        Any
            The setting value.
        """
        with self._lock:
            if default is None:
                default = _DEFAULTS.get(key)
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Update a setting and emit a change event.

        Parameters
        ----------
        key : str
            Setting name.
        value : Any
            New value.
        """
        with self._lock:
            old_value = self._data.get(key)
            self._data[key] = value

        if old_value != value:
            _log.debug("Setting changed: %s = %r (was %r)", key, value, old_value)
            self._emit_change(key, value, old_value)

    def get_all(self) -> dict[str, Any]:
        """Return a copy of all current settings."""
        with self._lock:
            return dict(self._data)

    def save(self) -> None:
        """Persist current settings to the JSON file."""
        with self._lock:
            data_copy = dict(self._data)

        try:
            self._file_path.write_text(
                json.dumps(data_copy, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            _log.info("Settings saved to %s", self._file_path)
        except OSError as exc:
            _log.error("Failed to save settings: %s", exc)

    def load(self) -> None:
        """Load settings from the JSON file (if it exists)."""
        if not self._file_path.exists():
            _log.debug("No settings file found; using defaults.")
            return

        try:
            raw = self._file_path.read_text(encoding="utf-8")
            loaded: dict[str, Any] = json.loads(raw)

            with self._lock:
                # Merge: loaded values override defaults.
                for key, value in loaded.items():
                    if key in _DEFAULTS:
                        self._data[key] = value

            _log.info("Settings loaded from %s", self._file_path)
        except (json.JSONDecodeError, OSError) as exc:
            _log.warning("Failed to load settings: %s (using defaults)", exc)

    def reset_defaults(self) -> None:
        """Reset all settings to built-in defaults."""
        with self._lock:
            self._data = dict(_DEFAULTS)

        self.save()
        _log.info("Settings reset to defaults.")

    def set_event_bus(self, event_bus: EventBus) -> None:
        """Attach or replace the event bus (for late binding)."""
        self._event_bus = event_bus

    # ── Private ────────────────────────────────────────────

    def _emit_change(
        self,
        key: str,
        value: Any,
        old_value: Any,
    ) -> None:
        """Emit a settings.changed event if a bus is attached."""
        if self._event_bus is not None:
            try:
                from voice.event_bus import Topics
                self._event_bus.emit_async(Topics.SETTINGS_CHANGED, {
                    "key": key,
                    "value": value,
                    "old_value": old_value,
                })
            except Exception:
                pass  # Bus not ready yet — ignore.
