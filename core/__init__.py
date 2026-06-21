"""
============================================================
  core/ package -- Central Business Logic
============================================================

Modules
-------
assistant.py
    Central orchestrator that ties all subsystems together.
listener.py
    Microphone capture + Google Speech-to-Text.
speaker.py
    Text-to-speech output via pyttsx3.
command_parser.py
    Expandable rule-based command router.
ai_manager.py
    Future AI integration stub (local fallback for now).
============================================================
"""

from __future__ import annotations

from core.assistant import Assistant
from core.listener import Listener
from core.speaker import Speaker
from core.command_parser import CommandParser, ParsedCommand
from core.ai_manager import AIManager

__all__: list[str] = [
    "Assistant",
    "Listener",
    "Speaker",
    "CommandParser",
    "ParsedCommand",
    "AIManager",
]
