"""
============================================================
  engine_factory.py — Speech Engine Factory (Strategy Pattern)
============================================================

PURPOSE:
    Creates the best available speech engine based on user
    settings and installed dependencies.

PRIORITY (auto mode):
    1. Vosk       — offline, fast, low resource
    2. Whisper    — offline, higher accuracy
    3. Google     — online fallback

USAGE:
    from voice.engines.engine_factory import EngineFactory

    engine = EngineFactory.create("auto")
    engine = EngineFactory.create("vosk")
    engine = EngineFactory.create("whisper")
============================================================
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from voice.speech_engine import SpeechEngine

if TYPE_CHECKING:
    from voice.settings_manager import SettingsManager

_log: logging.Logger = logging.getLogger(__name__)


class EngineFactory:
    """
    Factory that creates the best available SpeechEngine.

    Uses the Strategy pattern — the caller receives a
    ``SpeechEngine`` interface without knowing the concrete
    type.

    Methods
    -------
    create(preference, settings)
        Build and return a SpeechEngine instance.
    list_available()
        Return names of engines that can be used.
    """

    @staticmethod
    def create(
        preference: str = "auto",
        settings: SettingsManager | None = None,
    ) -> SpeechEngine:
        """
        Create a speech engine based on preference.

        Parameters
        ----------
        preference : str
            ``"auto"`` — try Vosk → Whisper → Google.
            ``"vosk"`` — force Vosk.
            ``"whisper"`` — force Whisper.
            ``"google"`` — force Google.
        settings : SettingsManager, optional
            Settings instance for engine-specific config.

        Returns
        -------
        SpeechEngine
            A ready-to-use speech engine instance.

        Raises
        ------
        RuntimeError
            If no engine is available.
        """
        # Extract settings.
        sample_rate = 16000
        device_index = None
        if settings is not None:
            device_index = settings.get("mic_device_index")

        preference = preference.lower().strip()

        if preference == "vosk":
            return EngineFactory._create_vosk(sample_rate, device_index)

        if preference == "whisper":
            return EngineFactory._create_whisper(sample_rate, device_index)

        if preference == "google":
            return EngineFactory._create_google(sample_rate, device_index)

        # ── Auto mode: try in priority order ───────────────
        # 1. Vosk (offline, primary)
        try:
            engine = EngineFactory._try_vosk(sample_rate, device_index)
            if engine is not None:
                _log.info("Auto-selected engine: Vosk (offline)")
                return engine
        except Exception as exc:
            _log.debug("Vosk not available: %s", exc)

        # 2. Whisper (offline, high accuracy)
        try:
            engine = EngineFactory._try_whisper(sample_rate, device_index)
            if engine is not None:
                _log.info("Auto-selected engine: Whisper (offline)")
                return engine
        except Exception as exc:
            _log.debug("Whisper not available: %s", exc)

        # 3. Google (online fallback)
        try:
            engine = EngineFactory._try_google(sample_rate, device_index)
            if engine is not None:
                _log.info("Auto-selected engine: Google (online fallback)")
                return engine
        except Exception as exc:
            _log.debug("Google not available: %s", exc)

        raise RuntimeError(
            "No speech engine is available. Install at least one of:\n"
            "  pip install vosk              (recommended, offline)\n"
            "  pip install faster-whisper    (optional, high accuracy)\n"
            "  pip install SpeechRecognition sounddevice scipy  (online fallback)"
        )

    @staticmethod
    def list_available() -> list[str]:
        """Return names of engines that are currently usable."""
        available: list[str] = []

        try:
            from voice.engines.vosk_engine import VoskEngine
            if VoskEngine().is_available():
                available.append("vosk")
        except Exception:
            pass

        try:
            from voice.engines.whisper_engine import WhisperEngine
            if WhisperEngine().is_available():
                available.append("whisper")
        except Exception:
            pass

        try:
            from voice.engines.google_engine import GoogleEngine
            if GoogleEngine().is_available():
                available.append("google")
        except Exception:
            pass

        return available

    # ── Private factory methods ────────────────────────────

    @staticmethod
    def _create_vosk(sample_rate: int, device_index: int | None) -> SpeechEngine:
        from voice.engines.vosk_engine import VoskEngine
        engine = VoskEngine(sample_rate=sample_rate, device_index=device_index)
        if not engine.is_available():
            raise RuntimeError("Vosk is not available.")
        return engine

    @staticmethod
    def _create_whisper(sample_rate: int, device_index: int | None) -> SpeechEngine:
        from voice.engines.whisper_engine import WhisperEngine
        engine = WhisperEngine(sample_rate=sample_rate, device_index=device_index)
        if not engine.is_available():
            raise RuntimeError("Whisper is not available.")
        return engine

    @staticmethod
    def _create_google(sample_rate: int, device_index: int | None) -> SpeechEngine:
        from voice.engines.google_engine import GoogleEngine
        engine = GoogleEngine(sample_rate=sample_rate, device_index=device_index)
        if not engine.is_available():
            raise RuntimeError("Google engine is not available.")
        return engine

    @staticmethod
    def _try_vosk(sample_rate: int, device_index: int | None) -> SpeechEngine | None:
        try:
            from voice.engines.vosk_engine import VoskEngine
            engine = VoskEngine(sample_rate=sample_rate, device_index=device_index)
            if engine.is_available():
                return engine
        except ImportError:
            pass
        return None

    @staticmethod
    def _try_whisper(sample_rate: int, device_index: int | None) -> SpeechEngine | None:
        try:
            from voice.engines.whisper_engine import WhisperEngine
            engine = WhisperEngine(sample_rate=sample_rate, device_index=device_index)
            if engine.is_available():
                return engine
        except ImportError:
            pass
        return None

    @staticmethod
    def _try_google(sample_rate: int, device_index: int | None) -> SpeechEngine | None:
        try:
            from voice.engines.google_engine import GoogleEngine
            engine = GoogleEngine(sample_rate=sample_rate, device_index=device_index)
            if engine.is_available():
                return engine
        except ImportError:
            pass
        return None
