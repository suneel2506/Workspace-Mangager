"""
============================================================
  google_engine.py — Fallback Online Speech Engine
============================================================

PURPOSE:
    Online speech-to-text using Google Web Speech API via the
    existing ``Listener`` class in ``core/listener.py``.

    This is the FALLBACK engine — used only when both Vosk and
    Whisper are unavailable.  Requires internet.

DESIGN:
    Wraps the existing ``Listener`` class (no code duplication).
    The ``Listener`` handles recording, temp WAV, and Google API.

USAGE:
    engine = GoogleEngine()
    if engine.is_available():
        engine.start()
        result = engine.listen(timeout=5.0)
        engine.stop()
============================================================
"""

from __future__ import annotations

import logging

from voice.speech_engine import SpeechEngine, TranscriptionResult

_log: logging.Logger = logging.getLogger(__name__)

# ── Import the existing Listener ──────────────────────────
try:
    from core.listener import Listener
    _LISTENER_AVAILABLE: bool = True
except ImportError:
    _LISTENER_AVAILABLE = False


class GoogleEngine(SpeechEngine):
    """
    Online speech engine wrapping the existing ``Listener`` class.

    Delegates all audio capture and Google Web Speech API calls
    to ``core.listener.Listener`` — no code duplication.

    Parameters
    ----------
    sample_rate : int
        Audio sample rate (passed to Listener).
    device_index : int | None
        Microphone device index (currently unused by Listener,
        but reserved for future enhancement).
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        device_index: int | None = None,
    ) -> None:
        self._sample_rate: int = sample_rate
        self._device_index: int | None = device_index
        self._listener: Listener | None = None
        self._started: bool = False

    # ── SpeechEngine interface ─────────────────────────────

    @property
    def name(self) -> str:
        return "Google"

    @property
    def description(self) -> str:
        return "Online speech recognition via Google Web Speech API"

    @property
    def is_offline(self) -> bool:
        return False

    def is_available(self) -> bool:
        """Check that the Listener's dependencies are installed."""
        if not _LISTENER_AVAILABLE:
            return False
        # Create a temporary Listener to check availability.
        try:
            test_listener = Listener()
            return test_listener.is_available()
        except Exception:
            return False

    def start(self) -> None:
        """Initialise the Listener."""
        if self._started:
            return

        if not _LISTENER_AVAILABLE:
            raise RuntimeError(
                "Google engine requires core.listener.Listener. "
                "Ensure SpeechRecognition, sounddevice, and scipy "
                "are installed."
            )

        self._listener = Listener(
            sample_rate=self._sample_rate,
        )

        if not self._listener.is_available():
            raise RuntimeError(
                "Speech dependencies are not installed. "
                "Run: pip install SpeechRecognition sounddevice scipy"
            )

        self._started = True
        _log.info("Google speech engine started.")

    def stop(self) -> None:
        """Release Listener resources."""
        self._listener = None
        self._started = False
        _log.info("Google speech engine stopped.")

    def listen(self, timeout: float = 5.0) -> TranscriptionResult:
        """
        Record audio and transcribe via Google Web Speech API.

        Delegates to the existing ``Listener.listen()`` method.

        Parameters
        ----------
        timeout : float
            Recording duration in seconds.

        Returns
        -------
        TranscriptionResult
            Transcription result.
        """
        if not self._started or self._listener is None:
            self.start()

        assert self._listener is not None

        # Temporarily set the listener's duration.
        original_duration = self._listener.duration
        self._listener.duration = timeout

        try:
            text = self._listener.listen()

            if text is None:
                return TranscriptionResult(
                    text="",
                    confidence=0.0,
                    engine_name=self.name,
                )

            _log.info("Google recognised: '%s'", text)

            return TranscriptionResult(
                text=text,
                confidence=0.80,  # Google doesn't return confidence.
                is_partial=False,
                engine_name=self.name,
            )

        except Exception as exc:
            _log.exception("Google listen error: %s", exc)
            return TranscriptionResult(
                text="",
                confidence=0.0,
                engine_name=self.name,
            )

        finally:
            self._listener.duration = original_duration
