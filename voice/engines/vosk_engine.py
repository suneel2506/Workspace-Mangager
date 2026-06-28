"""
============================================================
  vosk_engine.py — Primary Offline Speech Engine (Vosk)
============================================================

PURPOSE:
    Offline speech-to-text using the Vosk library (Kaldi-based).
    This is the PRIMARY engine — works without internet after
    the model is downloaded once.

MODEL:
    vosk-model-small-en-us-0.15 (~40 MB)
    Auto-downloaded to ``assets/vosk-model/`` on first run.

AUDIO PIPELINE:
    Uses ``sounddevice`` to stream audio directly into Vosk's
    ``KaldiRecognizer`` in real time — no temp WAV files needed.
    Supports partial results for live preview in the overlay.

USAGE:
    engine = VoskEngine(settings)
    if engine.is_available():
        engine.start()
        result = engine.listen(timeout=5.0)
        print(result.text)
        engine.stop()
============================================================
"""

from __future__ import annotations

import json
import logging
import os
import queue
import zipfile
from pathlib import Path
from typing import Any

from voice.speech_engine import SpeechEngine, TranscriptionResult

_log: logging.Logger = logging.getLogger(__name__)

# ── Optional imports ───────────────────────────────────────
try:
    import vosk
    _VOSK_AVAILABLE: bool = True
except ImportError:
    _VOSK_AVAILABLE = False

try:
    import sounddevice as sd
    _SD_AVAILABLE: bool = True
except ImportError:
    _SD_AVAILABLE = False

# ── Model configuration ───────────────────────────────────
_MODEL_NAME: str = "vosk-model-small-en-us-0.15"
_MODEL_URL: str = f"https://alphacephei.com/vosk/models/{_MODEL_NAME}.zip"

try:
    from config.settings import ASSETS_DIR
    _MODEL_DIR: Path = ASSETS_DIR / "vosk-model"
except ImportError:
    _MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "vosk-model"


class VoskEngine(SpeechEngine):
    """
    Offline speech engine using Vosk (Kaldi).

    Streams audio from the microphone through Vosk's recogniser
    in real time.  Supports partial results for live preview.

    Parameters
    ----------
    sample_rate : int
        Audio sample rate.  16000 Hz is optimal for Vosk.
    device_index : int | None
        Microphone device index.  ``None`` uses system default.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        device_index: int | None = None,
    ) -> None:
        self._sample_rate: int = sample_rate
        self._device_index: int | None = device_index
        self._model: Any = None
        self._recogniser: Any = None
        self._audio_queue: queue.Queue[bytes] = queue.Queue()
        self._started: bool = False

    # ── SpeechEngine interface ─────────────────────────────

    @property
    def name(self) -> str:
        return "Vosk"

    @property
    def description(self) -> str:
        return "Offline speech recognition using Vosk (Kaldi)"

    @property
    def is_offline(self) -> bool:
        return True

    def is_available(self) -> bool:
        """Check that vosk and sounddevice are installed and model exists."""
        if not (_VOSK_AVAILABLE and _SD_AVAILABLE):
            return False
        # Model must exist (or be downloadable).
        return self._model_path().exists() or True  # Allow auto-download

    def start(self) -> None:
        """Load the Vosk model and prepare the recogniser."""
        if self._started:
            return

        if not _VOSK_AVAILABLE:
            raise RuntimeError(
                "Vosk is not installed. Run: pip install vosk"
            )

        model_path = self._model_path()

        # Auto-download model if needed.
        if not model_path.exists():
            _log.info("Vosk model not found. Attempting download...")
            self._download_model()

        if not model_path.exists():
            raise RuntimeError(
                f"Vosk model not found at {model_path}. "
                f"Download it from https://alphacephei.com/vosk/models"
            )

        # Suppress Vosk's own logging (very verbose).
        vosk.SetLogLevel(-1)

        _log.info("Loading Vosk model from %s ...", model_path)
        self._model = vosk.Model(str(model_path))
        self._recogniser = vosk.KaldiRecognizer(
            self._model, self._sample_rate
        )
        self._started = True
        _log.info("Vosk engine started (sample_rate=%d).", self._sample_rate)

    def stop(self) -> None:
        """Release Vosk resources."""
        self._model = None
        self._recogniser = None
        self._started = False
        _log.info("Vosk engine stopped.")

    def listen(self, timeout: float = 5.0) -> TranscriptionResult:
        """
        Record audio and transcribe with Vosk.

        Streams audio directly into the Vosk recogniser without
        writing temp files.  Returns the final transcription.

        Parameters
        ----------
        timeout : float
            Maximum recording duration in seconds.

        Returns
        -------
        TranscriptionResult
            Final transcription with confidence.
        """
        if not self._started or self._recogniser is None:
            self.start()

        # Clear the audio queue.
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

        # Reset the recogniser for a fresh utterance.
        self._recogniser = vosk.KaldiRecognizer(
            self._model, self._sample_rate
        )

        final_text: str = ""
        block_size: int = int(self._sample_rate * 0.1)  # 100ms chunks

        try:
            _log.debug("Vosk: recording for %.1f seconds...", timeout)

            # Use sounddevice's raw stream for real-time audio.
            with sd.RawInputStream(
                samplerate=self._sample_rate,
                blocksize=block_size,
                dtype="int16",
                channels=1,
                device=self._device_index,
                callback=self._audio_callback,
            ):
                import time
                start_time = time.monotonic()
                silence_count: int = 0

                while (time.monotonic() - start_time) < timeout:
                    try:
                        data = self._audio_queue.get(timeout=0.2)
                    except queue.Empty:
                        silence_count += 1
                        if silence_count > 10:  # 2 seconds of silence
                            break
                        continue

                    silence_count = 0

                    if self._recogniser.AcceptWaveform(data):
                        result = json.loads(self._recogniser.Result())
                        text = result.get("text", "").strip()
                        if text:
                            final_text = text
                            break  # Final result found.

            # Get any remaining final result.
            if not final_text:
                result = json.loads(self._recogniser.FinalResult())
                final_text = result.get("text", "").strip()

        except sd.PortAudioError as exc:
            _log.error("Vosk audio error: %s", exc)
            return TranscriptionResult(
                text="",
                confidence=0.0,
                engine_name=self.name,
            )
        except Exception as exc:
            _log.exception("Vosk listen error: %s", exc)
            return TranscriptionResult(
                text="",
                confidence=0.0,
                engine_name=self.name,
            )

        _log.info("Vosk recognised: '%s'", final_text)

        return TranscriptionResult(
            text=final_text,
            confidence=0.85 if final_text else 0.0,
            is_partial=False,
            engine_name=self.name,
        )

    # ── Private helpers ────────────────────────────────────

    def _audio_callback(
        self,
        indata: bytes,
        frames: int,
        time_info: Any,
        status: Any,
    ) -> None:
        """Sounddevice callback — puts audio chunks into the queue."""
        if status:
            _log.debug("Vosk audio status: %s", status)
        self._audio_queue.put(bytes(indata))

    def _model_path(self) -> Path:
        """Return the path to the Vosk model directory."""
        return _MODEL_DIR / _MODEL_NAME

    def _download_model(self) -> None:
        """Download and extract the Vosk model."""
        try:
            import urllib.request

            _MODEL_DIR.mkdir(parents=True, exist_ok=True)
            zip_path = _MODEL_DIR / f"{_MODEL_NAME}.zip"

            _log.info("Downloading Vosk model from %s ...", _MODEL_URL)
            print(f"  [*] Downloading Vosk model ({_MODEL_NAME})...")
            print(f"      This is a one-time download (~40 MB).")

            urllib.request.urlretrieve(_MODEL_URL, str(zip_path))

            _log.info("Extracting model to %s ...", _MODEL_DIR)
            print(f"  [*] Extracting model...")

            with zipfile.ZipFile(str(zip_path), "r") as zf:
                zf.extractall(str(_MODEL_DIR))

            # Clean up zip file.
            if zip_path.exists():
                os.remove(str(zip_path))

            _log.info("Vosk model downloaded and extracted successfully.")
            print(f"  [✓] Vosk model ready.")

        except Exception as exc:
            _log.error("Failed to download Vosk model: %s", exc)
            print(f"  [✗] Model download failed: {exc}")
            print(f"      Please download manually from:")
            print(f"      {_MODEL_URL}")
            print(f"      Extract to: {_MODEL_DIR}")
