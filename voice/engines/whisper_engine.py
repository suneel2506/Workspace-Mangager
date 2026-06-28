"""
============================================================
  whisper_engine.py — Optional High-Accuracy Offline Engine
============================================================

PURPOSE:
    Offline speech-to-text using faster-whisper (CTranslate2-
    optimized OpenAI Whisper).  Higher accuracy than Vosk but
    slightly higher latency.

MODEL:
    Uses ``tiny.en`` or ``base.en`` model (~75 MB for base).
    Auto-downloaded on first use by faster-whisper.

USAGE:
    engine = WhisperEngine(settings)
    if engine.is_available():
        engine.start()
        result = engine.listen(timeout=5.0)
        engine.stop()
============================================================
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Any

from voice.speech_engine import SpeechEngine, TranscriptionResult

_log: logging.Logger = logging.getLogger(__name__)

# ── Optional imports ───────────────────────────────────────
try:
    from faster_whisper import WhisperModel
    _WHISPER_AVAILABLE: bool = True
except ImportError:
    _WHISPER_AVAILABLE = False

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


class WhisperEngine(SpeechEngine):
    """
    Offline speech engine using faster-whisper.

    Records audio via sounddevice, saves to a temp WAV, then
    transcribes with the Whisper model locally.

    Parameters
    ----------
    model_size : str
        Whisper model size.  ``"tiny.en"`` or ``"base.en"``.
    sample_rate : int
        Audio sample rate (16000 Hz recommended).
    device_index : int | None
        Microphone device index.
    """

    def __init__(
        self,
        model_size: str = "base.en",
        sample_rate: int = 16000,
        device_index: int | None = None,
    ) -> None:
        self._model_size: str = model_size
        self._sample_rate: int = sample_rate
        self._device_index: int | None = device_index
        self._model: Any = None
        self._started: bool = False

    # ── SpeechEngine interface ─────────────────────────────

    @property
    def name(self) -> str:
        return "Whisper"

    @property
    def description(self) -> str:
        return f"Offline speech recognition using faster-whisper ({self._model_size})"

    @property
    def is_offline(self) -> bool:
        return True

    def is_available(self) -> bool:
        """Check that faster-whisper, sounddevice, scipy are installed."""
        return _WHISPER_AVAILABLE and _SD_AVAILABLE and _SCIPY_AVAILABLE

    def start(self) -> None:
        """Load the Whisper model."""
        if self._started:
            return

        if not _WHISPER_AVAILABLE:
            raise RuntimeError(
                "faster-whisper is not installed. "
                "Run: pip install faster-whisper"
            )

        _log.info(
            "Loading Whisper model '%s' (first run may download ~75 MB)...",
            self._model_size,
        )
        print(f"  [*] Loading Whisper model '{self._model_size}'...")

        self._model = WhisperModel(
            self._model_size,
            device="cpu",
            compute_type="int8",
        )

        self._started = True
        _log.info("Whisper engine started (model=%s).", self._model_size)

    def stop(self) -> None:
        """Release the Whisper model."""
        self._model = None
        self._started = False
        _log.info("Whisper engine stopped.")

    def listen(self, timeout: float = 5.0) -> TranscriptionResult:
        """
        Record audio and transcribe with Whisper.

        Records a fixed-duration audio clip, saves it to a temp
        WAV file, and runs Whisper inference locally.

        Parameters
        ----------
        timeout : float
            Recording duration in seconds.

        Returns
        -------
        TranscriptionResult
            Transcription with confidence score.
        """
        if not self._started or self._model is None:
            self.start()

        tmp_path: str = ""

        try:
            # Record audio.
            _log.debug("Whisper: recording %.1f seconds...", timeout)
            audio_data = sd.rec(
                int(timeout * self._sample_rate),
                samplerate=self._sample_rate,
                channels=1,
                dtype="float32",
                device=self._device_index,
            )
            sd.wait()

            # Save to temp WAV.
            fd, tmp_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)

            # Convert to int16 for WAV file.
            audio_int16 = (audio_data * 32767).astype(np.int16)
            wavfile.write(tmp_path, self._sample_rate, audio_int16)

            # Transcribe with Whisper.
            segments, info = self._model.transcribe(
                tmp_path,
                language="en",
                beam_size=3,
                vad_filter=True,
            )

            text_parts: list[str] = []
            total_confidence: float = 0.0
            segment_count: int = 0

            for segment in segments:
                text_parts.append(segment.text.strip())
                # avg_logprob is negative; convert to 0–1 range.
                prob = max(0.0, min(1.0, 1.0 + segment.avg_logprob))
                total_confidence += prob
                segment_count += 1

            final_text = " ".join(text_parts).strip()
            avg_confidence = (
                total_confidence / segment_count
                if segment_count > 0
                else 0.0
            )

            _log.info("Whisper recognised: '%s' (confidence=%.2f)", final_text, avg_confidence)

            return TranscriptionResult(
                text=final_text,
                confidence=avg_confidence,
                is_partial=False,
                engine_name=self.name,
            )

        except Exception as exc:
            _log.exception("Whisper listen error: %s", exc)
            return TranscriptionResult(
                text="",
                confidence=0.0,
                engine_name=self.name,
            )

        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
