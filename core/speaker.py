"""
============================================================
  speaker.py -- Text-to-Speech Output
============================================================

PURPOSE:
    Provides a ``Speaker`` class that converts text to audible
    speech using the ``pyttsx3`` library.  This is used by the
    ``Assistant`` to give verbal feedback after voice commands.

DESIGN:
    * Graceful degradation -- if ``pyttsx3`` is not installed
      the class still instantiates, ``is_available()`` returns
      ``False``, and ``say()`` simply prints the text to stdout.
    * Configurable rate, volume, and voice pulled from
      ``config.settings``.
    * Thread-safe -- ``say()`` can run synchronously (blocking)
      or be dispatched to a background thread.

FUTURE HOOKS:
    * Swap pyttsx3 for a cloud TTS (Google Cloud, Azure Speech).
    * Audio ducking -- lower system volume while speaking.
    * SSML support for emphasis, pauses, and prosody control.
============================================================
"""

from __future__ import annotations

import logging
import threading

# ── Optional dependency import ─────────────────────────────
try:
    import pyttsx3                  # type: ignore[import-untyped]
    _PYTTSX3_AVAILABLE: bool = True
except ImportError:
    _PYTTSX3_AVAILABLE = False

# ── Settings (graceful fallback) ───────────────────────────
try:
    from config.settings import (
        TTS_RATE as _CFG_RATE,
        TTS_VOLUME as _CFG_VOLUME,
        TTS_VOICE_ID as _CFG_VOICE_ID,
    )
except (ImportError, ModuleNotFoundError):
    _CFG_RATE: int = 160
    _CFG_VOLUME: float = 0.9
    _CFG_VOICE_ID: str | None = None

# ── Logger ─────────────────────────────────────────────────
_log: logging.Logger = logging.getLogger(__name__)


class Speaker:
    """
    Text-to-speech wrapper using pyttsx3.

    If ``pyttsx3`` is not installed, all methods are no-ops that
    fall back to ``print()`` so the rest of the application
    continues working silently.

    Attributes
    ----------
    rate : int
        Speech rate in words-per-minute.
    volume : float
        Volume level from 0.0 to 1.0.
    voice_id : str | None
        Explicit voice identifier, or ``None`` for system default.

    Usage
    -----
    ::

        speaker = Speaker()
        if speaker.is_available():
            speaker.say("Workspace created successfully.")
        else:
            print("TTS not available.")
    """

    def __init__(
        self,
        rate: int = _CFG_RATE,
        volume: float = _CFG_VOLUME,
        voice_id: str | None = _CFG_VOICE_ID,
    ) -> None:
        self.rate: int = rate
        self.volume: float = volume
        self.voice_id: str | None = voice_id

        self._engine = None
        self._lock = threading.Lock()

        if _PYTTSX3_AVAILABLE:
            try:
                self._engine = pyttsx3.init()
                self._engine.setProperty("rate", self.rate)
                self._engine.setProperty("volume", self.volume)
                if self.voice_id:
                    self._engine.setProperty("voice", self.voice_id)
                _log.info(
                    "Speaker initialised (rate=%d, volume=%.1f).",
                    self.rate, self.volume,
                )
            except Exception as exc:
                _log.warning("pyttsx3 init failed: %s", exc)
                self._engine = None
        else:
            _log.warning(
                "pyttsx3 is not installed.  Speaker will use print() fallback.  "
                "Install with:  pip install pyttsx3"
            )

    # ── Public API ─────────────────────────────────────────

    def is_available(self) -> bool:
        """Return ``True`` if the TTS engine is ready."""
        return self._engine is not None

    def say(self, text: str, block: bool = True) -> None:
        """
        Speak the given text aloud.

        Parameters
        ----------
        text : str
            The sentence to speak.
        block : bool, optional
            If ``True`` (default), the call blocks until speech
            finishes.  If ``False``, speech runs in a background
            thread.
        """
        if not text or not text.strip():
            return

        _log.debug("Speaker.say: '%s'", text)

        if not self.is_available():
            # Fallback: just print the text.
            print(f"  [🔊] {text}")
            return

        if block:
            self._speak(text)
        else:
            thread = threading.Thread(
                target=self._speak,
                args=(text,),
                daemon=True,
            )
            thread.start()

    # ── Private ────────────────────────────────────────────

    def _speak(self, text: str) -> None:
        """Thread-safe speech execution."""
        with self._lock:
            try:
                self._engine.say(text)       # type: ignore[union-attr]
                self._engine.runAndWait()    # type: ignore[union-attr]
            except Exception as exc:
                _log.error("TTS error: %s", exc)
