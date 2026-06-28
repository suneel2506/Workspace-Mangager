"""
============================================================
  wakeword.py -- Wake Word Detection for MAJA
============================================================

PURPOSE:
    Listens for the wake word "MAJA" using speech_recognition
    as a lightweight fallback. Uses short audio chunks to
    detect the wake word without blocking the GUI.

USAGE:
    from wakeword import WakeWordDetector

    detector = WakeWordDetector()
    detector.start(on_wake=my_callback)
    detector.stop()
============================================================
"""

from __future__ import annotations

import logging
import threading
from typing import Callable

_log: logging.Logger = logging.getLogger(__name__)

# ── Optional dependency imports ────────────────────────────
try:
    import sounddevice as sd
    import numpy as np
    _SD_AVAILABLE: bool = True
except ImportError:
    _SD_AVAILABLE = False

try:
    from scipy.io import wavfile
    _SCIPY_AVAILABLE: bool = True
except ImportError:
    _SCIPY_AVAILABLE = False

try:
    import speech_recognition as sr
    _SR_AVAILABLE: bool = True
except ImportError:
    _SR_AVAILABLE = False

import os
import tempfile

# Wake word constant
WAKE_WORD: str = "hey bro "


def listen_for_wakeword() -> bool:
    """
    Listen for the wake word "MAJA" using speech_recognition.

    Records a short audio clip and checks if the transcribed
    text contains the wake word.

    Returns
    -------
    bool
        True if the wake word was detected, False otherwise.
    """
    if not (_SD_AVAILABLE and _SCIPY_AVAILABLE and _SR_AVAILABLE):
        _log.error(
            "Wake word detection requires sounddevice, scipy, "
            "and SpeechRecognition.  Install them with:  "
            "pip install sounddevice scipy SpeechRecognition"
        )
        return False

    try:
        # Record a short clip (2 seconds) to check for wake word.
        duration = 2.0
        sample_rate = 16000
        audio_data = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
        )
        sd.wait()

        # Save to temp WAV and transcribe.
        tmp_path = ""
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            wavfile.write(tmp_path, sample_rate, audio_data)

            recognizer = sr.Recognizer()
            with sr.AudioFile(tmp_path) as source:
                audio = recognizer.record(source)

            text = recognizer.recognize_google(audio).lower()
            _log.debug("Wake word listener heard: '%s'", text)

            if WAKE_WORD in text:
                _log.info("Wake word '%s' detected!", WAKE_WORD)
                return True

        except sr.UnknownValueError:
            # No speech detected — this is normal, not an error.
            pass
        except sr.RequestError as exc:
            _log.warning("Speech API error during wake word detection: %s", exc)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    except Exception as exc:
        _log.exception("Wake word detection error: %s", exc)

    return False


class WakeWordDetector:
    """
    Background wake word detector that integrates with the Assistant.

    Runs a daemon thread that continuously listens for "MAJA".
    When detected, calls the registered callback.

    Usage
    -----
    ::
        detector = WakeWordDetector()
        detector.start(on_wake=lambda: assistant.process_voice())
        # ... later ...
        detector.stop()
    """

    def __init__(self) -> None:
        self._running: bool = False
        self._thread: threading.Thread | None = None
        self._on_wake: Callable[[], None] | None = None

    @property
    def is_running(self) -> bool:
        """Return True if the wake word detector is active."""
        return self._running

    def start(self, on_wake: Callable[[], None]) -> None:
        """
        Start listening for the wake word in a background thread.

        Parameters
        ----------
        on_wake : Callable
            Function to call when the wake word is detected.
        """
        if self._running:
            _log.warning("Wake word detector is already running.")
            return

        self._on_wake = on_wake
        self._running = True
        self._thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name="WakeWordThread",
        )
        self._thread.start()
        _log.info("Wake word detector started (wake word: '%s').", WAKE_WORD)

    def stop(self) -> None:
        """Stop the wake word detector."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None
        _log.info("Wake word detector stopped.")

    def _listen_loop(self) -> None:
        """Background loop that listens for the wake word."""
        while self._running:
            try:
                if listen_for_wakeword():
                    if self._on_wake and self._running:
                        self._on_wake()
            except Exception as exc:
                _log.exception("Wake word loop error: %s", exc)