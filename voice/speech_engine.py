"""
============================================================
  speech_engine.py — Abstract Speech Engine Interface
============================================================

PURPOSE:
    Strategy pattern interface for speech-to-text engines.
    All concrete engines (Vosk, Whisper, Google) implement
    this interface so the rest of the application never knows
    which engine is active.

DESIGN:
    * Abstract base class with ``@abstractmethod`` for all
      public operations.
    * Concrete implementations live in ``voice/engines/``.
    * The ``EngineFactory`` selects the best available engine
      based on user settings.

USAGE:
    # The application only sees SpeechEngine:
    engine: SpeechEngine = EngineFactory.create("auto")
    text = engine.listen(timeout=5.0)
============================================================
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class TranscriptionResult:
    """
    Result from a speech-to-text transcription.

    Attributes
    ----------
    text : str
        The recognised text (empty string if nothing heard).
    confidence : float
        Recognition confidence from 0.0 to 1.0.
    is_partial : bool
        True if this is an intermediate (not-yet-final) result.
    engine_name : str
        Name of the engine that produced this result.
    raw : Any
        Engine-specific raw result data (for debugging).
    """
    text: str = ""
    confidence: float = 0.0
    is_partial: bool = False
    engine_name: str = ""
    raw: Any = None


class SpeechEngine(ABC):
    """
    Abstract base class for speech-to-text engines.

    Concrete implementations must override all ``@abstractmethod``
    members.  The rest of the voice assistant interacts only with
    this interface (Strategy pattern).

    Lifecycle
    ---------
    ::
        engine = SomeEngine(settings)
        if engine.is_available():
            engine.start()
            result = engine.listen(timeout=5.0)
            print(result.text)
            engine.stop()
    """

    # ── Abstract methods ───────────────────────────────────

    @abstractmethod
    def start(self) -> None:
        """
        Prepare the engine for recognition.

        Load models, initialise audio streams, etc.
        Called once before the first ``listen()`` call.
        """
        ...

    @abstractmethod
    def stop(self) -> None:
        """
        Release engine resources.

        Unload models, close audio streams, etc.
        Called when the engine is no longer needed.
        """
        ...

    @abstractmethod
    def listen(self, timeout: float = 5.0) -> TranscriptionResult:
        """
        Record audio and return a transcription.

        Parameters
        ----------
        timeout : float, optional
            Maximum seconds to record.  Default is 5.0.

        Returns
        -------
        TranscriptionResult
            The recognised text and metadata.  If nothing was
            understood, ``text`` will be an empty string.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """
        Return True if this engine can be used.

        Checks that required libraries are installed, models
        are present, and (for online engines) the network is
        reachable.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable engine name (e.g. ``'Vosk'``)."""
        ...

    # ── Optional overrides ─────────────────────────────────

    @property
    def description(self) -> str:
        """Short description of the engine."""
        return f"{self.name} speech engine"

    @property
    def is_offline(self) -> bool:
        """Return True if this engine works without internet."""
        return False
