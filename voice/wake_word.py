"""
============================================================
  wake_word.py — Low-Power Wake Word Detection Manager
============================================================

PURPOSE:
    Manages wake word detection in a low-power mode.  When
    idle, only a lightweight wake-word thread runs, consuming
    near-zero CPU.  Upon detection, the full speech engine
    activates for one command, then returns to idle.

LIFECYCLE:
    Idle (near-zero CPU)
        ↓
    Wake word detected → emit ``wake.detected``
        ↓
    Full speech engine activates
        ↓
    Command processed
        ↓
    Return to idle

DESIGN:
    * Wraps the existing ``WakeWordDetector`` from ``wakeword.py``.
    * Configurable wake word via ``SettingsManager``.
    * Emits ``wake.detected`` event on the EventBus.
    * Background daemon thread (no polling in main thread).

USAGE:
    manager = WakeWordManager(event_bus, settings)
    manager.start()
    # ... wait for events ...
    manager.stop()
============================================================
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from voice.event_bus import EventBus
    from voice.settings_manager import SettingsManager

_log: logging.Logger = logging.getLogger(__name__)


class WakeWordManager:
    """
    Low-power wake word detector.

    Runs a background thread that listens for the configured
    wake word.  When detected, emits a ``wake.detected`` event
    and pauses until the command cycle completes.

    Parameters
    ----------
    event_bus : EventBus
        For emitting ``wake.detected`` events.
    settings : SettingsManager
        For reading wake word configuration.
    """

    def __init__(
        self,
        event_bus: EventBus,
        settings: SettingsManager,
    ) -> None:
        self._bus: EventBus = event_bus
        self._settings: SettingsManager = settings
        self._thread: threading.Thread | None = None
        self._running: bool = False
        self._paused: bool = False
        self._pause_event: threading.Event = threading.Event()
        self._pause_event.set()  # Not paused initially.

        _log.info("WakeWordManager initialised.")

    # ── Public API ─────────────────────────────────────────

    def start(self) -> None:
        """Start the wake word detection thread."""
        if self._running:
            return

        if not self._settings.get("wake_word_enabled", True):
            _log.info("Wake word detection is disabled in settings.")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._detection_loop,
            daemon=True,
            name="WakeWordThread",
        )
        self._thread.start()
        _log.info("Wake word detection started.")

    def stop(self) -> None:
        """Stop the wake word detection thread."""
        self._running = False
        self._pause_event.set()  # Unblock if paused.
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        _log.info("Wake word detection stopped.")

    def pause(self) -> None:
        """Pause detection (e.g. during active command listening)."""
        self._paused = True
        self._pause_event.clear()
        _log.debug("Wake word detection paused.")

    def resume(self) -> None:
        """Resume detection after a command cycle."""
        self._paused = False
        self._pause_event.set()
        _log.debug("Wake word detection resumed.")

    @property
    def is_running(self) -> bool:
        """True if the detection thread is active."""
        return self._running

    # ── Detection Loop ─────────────────────────────────────

    def _detection_loop(self) -> None:
        """Background loop that listens for the wake word."""
        wake_word = self._settings.get("wake_word", "jarvis")
        _log.info("Listening for wake word: '%s'", wake_word)

        # Try to use the existing WakeWordDetector.
        detector = self._create_detector(wake_word)

        while self._running:
            # Wait if paused (near-zero CPU).
            self._pause_event.wait()

            if not self._running:
                break

            try:
                detected = False

                if detector is not None:
                    # Use the existing WakeWordDetector.
                    detected = detector.listen_once(timeout=2.0)
                else:
                    # Fallback: simple speech recognition check.
                    detected = self._simple_detect(wake_word)

                if detected:
                    _log.info("Wake word detected: '%s'", wake_word)
                    from voice.event_bus import Topics
                    self._bus.emit(Topics.WAKE_DETECTED, {
                        "word": wake_word,
                    })
                    # Pause while command is processed.
                    self.pause()

                    # Auto-resume after a timeout (in case the
                    # overlay doesn't resume us).
                    threading.Timer(
                        15.0,
                        self.resume,
                    ).start()

            except Exception as exc:
                _log.error("Wake word detection error: %s", exc)
                time.sleep(1.0)  # Prevent rapid error loops.

    # ── Detector Creation ──────────────────────────────────

    def _create_detector(self, wake_word: str) -> Any:
        """Try to create a WakeWordDetector instance."""
        try:
            from wakeword import WakeWordDetector
            detector = WakeWordDetector(wake_word=wake_word)
            _log.info("Using existing WakeWordDetector.")
            return detector
        except ImportError:
            _log.debug("WakeWordDetector not available.")
        except Exception as exc:
            _log.debug("Could not create WakeWordDetector: %s", exc)
        return None

    def _simple_detect(self, wake_word: str) -> bool:
        """
        Fallback wake word detection using SpeechRecognition.

        Records a short audio clip and checks if the wake word
        appears in the transcription.
        """
        try:
            import speech_recognition as sr

            recogniser = sr.Recognizer()
            with sr.Microphone() as source:
                recogniser.adjust_for_ambient_noise(source, duration=0.5)
                try:
                    audio = recogniser.listen(source, timeout=2, phrase_time_limit=3)
                except sr.WaitTimeoutError:
                    return False

            try:
                text = recogniser.recognize_google(audio).lower()
                if wake_word.lower() in text:
                    return True
            except (sr.UnknownValueError, sr.RequestError):
                pass

        except Exception:
            pass

        return False
