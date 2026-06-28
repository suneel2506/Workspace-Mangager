"""
voice/engines/ — Speech-to-text engine implementations.

Concrete SpeechEngine subclasses:
    vosk_engine.py      — Primary offline engine (Vosk/Kaldi)
    whisper_engine.py   — Optional high-accuracy (faster-whisper)
    google_engine.py    — Fallback online engine (Google Web Speech)
    engine_factory.py   — Factory that creates the best available engine
"""

from __future__ import annotations
