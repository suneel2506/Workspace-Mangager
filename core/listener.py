"""
============================================================
  listener.py -- Microphone Audio Capture & Speech-to-Text
============================================================

PURPOSE:
    Records audio from the system microphone and converts the
    spoken words into a text string using Google's free Web
    Speech API.

    This is a CLASS-based wrapper around the same pipeline used
    by ``voice/speech.py``, designed for the new Assistant
    orchestrator in ``core/assistant.py``.

AUDIO PIPELINE:
    1. ``sounddevice.rec()``       -- capture audio as int16 NumPy array
    2. ``sd.wait()``               -- block until recording finishes
    3. ``scipy.io.wavfile.write()``-- save array to a temp WAV file
    4. ``sr.AudioFile()``          -- read WAV into SpeechRecognition
    5. ``recognizer.recognize_google()`` -- transcribe via Google API
    6. ``os.remove()``             -- delete temp WAV in finally block

DEPENDENCIES (PyAudio-FREE):
    pip install SpeechRecognition sounddevice scipy

WHY NOT PyAudio?
    PyAudio requires compiling a C extension against PortAudio
    headers.  On Python 3.12+ this frequently fails.  sounddevice
    bundles PortAudio as a shared library -- zero compiler needed.

FUTURE HOOKS:
    - Continuous listening with wake-word detection.
    - Offline transcription via OpenAI Whisper or Vosk.
    - Voice Activity Detection (VAD) to auto-stop recording.
    - Configurable language (currently English only).
============================================================
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Optional

# ── Optional dependency imports ────────────────────────────
# Each dependency is imported inside a try/except so the rest
# of the application continues working even if speech libs are
# not installed (e.g. on a headless server or in CI).

try:
    import sounddevice as sd          # type: ignore[import-untyped]
    import numpy as np                # comes with sounddevice
    _SD_AVAILABLE: bool = True
except ImportError:
    _SD_AVAILABLE = False

try:
    from scipy.io import wavfile      # type: ignore[import-untyped]
    _SCIPY_AVAILABLE: bool = True
except ImportError:
    _SCIPY_AVAILABLE = False

try:
    import speech_recognition as sr   # type: ignore[import-untyped]
    _SR_AVAILABLE: bool = True
except ImportError:
    _SR_AVAILABLE = False


# ── Recording defaults ─────────────────────────────────────
# Try to import project-level settings; fall back to sensible
# defaults if config.settings has not been created yet.
try:
    from config.settings import (     # type: ignore[import-untyped]
        SAMPLE_RATE as _CFG_SAMPLE_RATE,
        RECORD_DURATION as _CFG_DURATION,
        RECORD_CHANNELS as _CFG_CHANNELS,
    )
except (ImportError, ModuleNotFoundError):
    _CFG_SAMPLE_RATE: int = 16000     # 16 kHz -- speech standard
    _CFG_DURATION: float = 5.0        # seconds per recording
    _CFG_CHANNELS: int = 1            # mono audio


# ── Module-level logger ────────────────────────────────────
_log: logging.Logger = logging.getLogger(__name__)


# ============================================================
#  Listener Class
# ============================================================

class Listener:
    """
    Records audio from the microphone and converts it to text.

    Uses *sounddevice* for capture, *scipy* for WAV I/O, and
    *SpeechRecognition* for transcription -- no PyAudio needed.

    Attributes
    ----------
    duration : float
        How many seconds to record per ``listen()`` call.
    sample_rate : int
        Audio sample rate in Hertz (default 16 000).
    channels : int
        Number of audio channels (1 = mono, 2 = stereo).

    Usage
    -----
    ::

        listener = Listener(duration=5.0)
        if listener.is_available():
            text = listener.listen()
            if text:
                print(f"You said: {text}")
    """

    # ── Constructor ────────────────────────────────────────
    def __init__(
        self,
        duration: float = _CFG_DURATION,
        sample_rate: int = _CFG_SAMPLE_RATE,
        channels: int = _CFG_CHANNELS,
    ) -> None:
        """
        Store recording configuration and log dependency status.

        Parameters
        ----------
        duration : float, optional
            Seconds of audio to record.  Default is pulled from
            ``config.settings.RECORD_DURATION`` (fallback 5.0).
        sample_rate : int, optional
            Sample rate in Hz.  Default is pulled from
            ``config.settings.SAMPLE_RATE`` (fallback 16 000).
        channels : int, optional
            Number of audio channels.  Default is pulled from
            ``config.settings.RECORD_CHANNELS`` (fallback 1).
        """
        self.duration: float = duration
        self.sample_rate: int = sample_rate
        self.channels: int = channels

        # Log which optional dependencies are present.
        _log.info(
            "Listener initialised  --  sounddevice=%s  scipy=%s  "
            "SpeechRecognition=%s",
            _SD_AVAILABLE, _SCIPY_AVAILABLE, _SR_AVAILABLE,
        )

        # Warn early if something is missing.
        if not self.is_available():
            missing: list[str] = []
            if not _SD_AVAILABLE:
                missing.append("sounddevice")
            if not _SCIPY_AVAILABLE:
                missing.append("scipy")
            if not _SR_AVAILABLE:
                missing.append("SpeechRecognition")
            _log.warning(
                "Listener is NOT available.  Missing packages: %s  "
                "Install with:  pip install %s",
                ", ".join(missing),
                " ".join(missing),
            )

    # ── Public: check readiness ────────────────────────────
    def is_available(self) -> bool:
        """
        Return ``True`` if all three speech dependencies are
        installed and importable.

        Returns
        -------
        bool
            ``True``  when sounddevice, scipy, **and**
            SpeechRecognition are all available.
        """
        return _SD_AVAILABLE and _SCIPY_AVAILABLE and _SR_AVAILABLE

    # ── Public: record + transcribe ────────────────────────
    def listen(self) -> str | None:
        """
        Record audio from the microphone and return the
        transcribed text string.

        Pipeline
        --------
        1. ``sounddevice.rec()``  -- capture int16 NumPy array
        2. ``sd.wait()``          -- block until done
        3. ``scipy.io.wavfile.write()`` -- save temp WAV
        4. ``sr.AudioFile()``     -- load WAV into recogniser
        5. ``recognizer.recognize_google()`` -- transcribe
        6. Delete temp WAV in ``finally``

        Returns
        -------
        str or None
            Recognised text, or ``None`` on any failure.

        Error Handling
        --------------
        - ``PermissionError``        -- mic blocked by OS privacy.
        - ``sd.PortAudioError``      -- no microphone hardware.
        - ``sr.UnknownValueError``   -- speech not understood.
        - ``sr.RequestError``        -- no internet / API error.
        """
        # ── Guard: all deps must be present ────────────────
        if not self.is_available():
            _log.error(
                "listen() called but dependencies are missing.  "
                "Run:  pip install sounddevice scipy SpeechRecognition"
            )
            print("  [x] Speech dependencies are not installed.")
            print("      Run:  pip install sounddevice scipy SpeechRecognition")
            return None

        # ── Step 1: Record audio via sounddevice ───────────
        try:
            _log.info(
                "Recording %s seconds at %s Hz (%s channel(s))...",
                self.duration, self.sample_rate, self.channels,
            )
            print(
                f"  [*] Recording for {self.duration:.0f} seconds "
                f"-- speak now!"
            )

            audio_data: np.ndarray = sd.rec(           # type: ignore[union-attr]
                int(self.duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",                         # 16-bit PCM
            )
            sd.wait()  # Block until recording finishes.

        except PermissionError:
            _log.error("Microphone access denied by OS privacy settings.")
            print("  [x] Microphone access denied.")
            print(
                "      Check Settings > Privacy > Microphone on Windows."
            )
            return None

        except sd.PortAudioError as exc:               # type: ignore[union-attr]
            _log.error("PortAudio error (no mic?): %s", exc)
            print(f"  [x] Audio device error: {exc}")
            print("      Make sure a microphone is connected.")
            return None

        except OSError as exc:
            _log.error("OS-level microphone error: %s", exc)
            print(f"  [x] Microphone error: {exc}")
            return None

        # ── Step 2-5: Save WAV -> Transcribe ───────────────
        tmp_path: str = ""
        try:
            # Create a named temp file for the WAV data.
            fd, tmp_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)  # Release the OS file descriptor.

            # Write the NumPy array as a WAV file.
            wavfile.write(tmp_path, self.sample_rate, audio_data)  # type: ignore[possibly-undefined]
            _log.debug("Temp WAV written to %s", tmp_path)

            # Feed the WAV into SpeechRecognition.
            recognizer = sr.Recognizer()               # type: ignore[possibly-undefined]
            with sr.AudioFile(tmp_path) as source:     # type: ignore[possibly-undefined]
                audio = recognizer.record(source)

            # Call Google Web Speech API (free, no key needed).
            text: str = recognizer.recognize_google(audio)
            _log.info("Recognised text: '%s'", text)
            print(f"  [>] You said: \"{text}\"")
            return text

        except sr.UnknownValueError:                   # type: ignore[possibly-undefined]
            # Google could not understand the audio.
            _log.warning("Google could not understand the audio.")
            print("  [!] Could not understand audio. Please try again.")
            return None

        except sr.RequestError as exc:                 # type: ignore[possibly-undefined]
            # Network / API failure.
            _log.error("Google Speech API error: %s", exc)
            print(f"  [x] Speech API error: {exc}")
            print("      Check your internet connection.")
            return None

        except PermissionError:
            _log.error("Permission denied writing temp WAV file.")
            print("  [x] Permission denied while writing temp audio file.")
            return None

        except Exception as exc:
            # Catch-all for truly unexpected failures.
            _log.exception("Unexpected error during transcription: %s", exc)
            print(f"  [x] Unexpected error: {exc}")
            return None

        finally:
            # ── Step 6: Clean up the temp WAV file ─────────
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                    _log.debug("Temp file removed: %s", tmp_path)
                except OSError:
                    # Non-critical -- OS temp dir cleans up eventually.
                    _log.debug(
                        "Could not remove temp file: %s", tmp_path
                    )
