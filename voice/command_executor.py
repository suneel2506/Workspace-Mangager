"""
============================================================
  command_executor.py — Command Execution Engine
============================================================

PURPOSE:
    Executes commands matched by the CommandRegistry.  When no
    command matches, falls back to the AI Assistant for a
    freeform response (so the assistant never says "unknown
    command").

FLOW:
    text → CommandRegistry.match(text)
    ├── matched? → call handler → emit command.success
    └── no match → AIManager.process(text) → emit command.ai_fallback

DESIGN:
    * All dependencies injected (Assistant, Registry, EventBus, AI).
    * Emits events at each execution stage.
    * Catches all exceptions (never crashes the overlay).
    * Measures execution time for history logging.

USAGE:
    executor = CommandExecutor(assistant, registry, event_bus, ai)
    result = executor.execute("open dashboard")
============================================================
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from voice.event_bus import EventBus, Topics

if TYPE_CHECKING:
    from core.assistant import Assistant
    from core.ai_manager import AIManager
    from voice.command_registry import CommandRegistry

_log: logging.Logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """
    Result of executing a voice command.

    Attributes
    ----------
    command : str
        The raw speech text.
    intent : str
        The matched intent (or ``"ai_fallback"``).
    result : str
        Human-readable outcome text.
    duration_ms : int
        Execution time in milliseconds.
    confidence : float
        Match confidence (0.0–1.0).
    was_ai_fallback : bool
        True if the AI handled this (no command matched).
    engine_name : str
        Which speech engine produced the transcription.
    """
    command: str = ""
    intent: str = ""
    result: str = ""
    duration_ms: int = 0
    confidence: float = 0.0
    was_ai_fallback: bool = False
    engine_name: str = ""


class CommandExecutor:
    """
    Executes voice commands with AI fallback.

    Parameters
    ----------
    assistant : Assistant
        The existing central orchestrator (for delegation).
    registry : CommandRegistry
        The fuzzy command registry.
    event_bus : EventBus
        For emitting execution events.
    ai_manager : AIManager
        For handling unrecognised speech.
    """

    def __init__(
        self,
        assistant: Assistant,
        registry: CommandRegistry,
        event_bus: EventBus,
        ai_manager: AIManager,
    ) -> None:
        self._assistant: Assistant = assistant
        self._registry: CommandRegistry = registry
        self._bus: EventBus = event_bus
        self._ai: AIManager = ai_manager

        _log.info("CommandExecutor initialised.")

    def execute(self, text: str, engine_name: str = "") -> ExecutionResult:
        """
        Execute a voice command or fall back to AI.

        Parameters
        ----------
        text : str
            The recognised speech text.
        engine_name : str, optional
            Name of the speech engine that produced this text.

        Returns
        -------
        ExecutionResult
            Execution outcome with timing and metadata.
        """
        if not text or not text.strip():
            return ExecutionResult(
                command=text,
                result="I didn't catch that. Please try again.",
                was_ai_fallback=False,
            )

        text = text.strip()
        start_time = time.monotonic()

        # ── Step 1: Try the voice command registry ─────────
        match = self._registry.match(text)

        if match is not None and match.handler is not None:
            return self._execute_matched(text, match, start_time, engine_name)

        # ── Step 2: Try the existing Assistant parser ──────
        # The existing CommandParser may handle commands that
        # plugins haven't registered.
        try:
            from core.command_parser import ParsedCommand
            parsed = self._assistant.parser.parse(text)
            if parsed is not None:
                _log.info(
                    "Delegating to existing parser: intent='%s'",
                    parsed.intent,
                )
                self._bus.emit(Topics.COMMAND_EXECUTING, {
                    "command": text,
                    "intent": parsed.intent,
                })

                result_text = self._assistant.process_text(text)
                duration = int((time.monotonic() - start_time) * 1000)

                self._bus.emit(Topics.COMMAND_SUCCESS, {
                    "command": text,
                    "intent": parsed.intent,
                    "result": result_text,
                })

                return ExecutionResult(
                    command=text,
                    intent=parsed.intent,
                    result=result_text,
                    duration_ms=duration,
                    confidence=parsed.confidence,
                    was_ai_fallback=False,
                    engine_name=engine_name,
                )
        except Exception as exc:
            _log.debug("Existing parser delegation failed: %s", exc)

        # ── Step 3: AI fallback ────────────────────────────
        return self._execute_ai_fallback(text, start_time, engine_name)

    # ── Private ────────────────────────────────────────────

    def _execute_matched(
        self,
        text: str,
        match: Any,
        start_time: float,
        engine_name: str,
    ) -> ExecutionResult:
        """Execute a matched command via its handler."""
        _log.info(
            "Command matched: intent='%s', phrase='%s', confidence=%.2f",
            match.intent, match.matched_phrase, match.confidence,
        )

        self._bus.emit(Topics.COMMAND_MATCHED, {
            "command": text,
            "intent": match.intent,
            "confidence": match.confidence,
            "matched_phrase": match.matched_phrase,
        })

        self._bus.emit(Topics.COMMAND_EXECUTING, {
            "command": text,
            "intent": match.intent,
        })

        try:
            result_text = match.handler(text, match.arguments)
            duration = int((time.monotonic() - start_time) * 1000)

            self._bus.emit(Topics.COMMAND_SUCCESS, {
                "command": text,
                "intent": match.intent,
                "result": result_text,
                "duration_ms": duration,
            })

            _log.info(
                "Command executed: '%s' → '%s' (%d ms)",
                match.intent, result_text[:80], duration,
            )

            return ExecutionResult(
                command=text,
                intent=match.intent,
                result=result_text or "Done.",
                duration_ms=duration,
                confidence=match.confidence,
                was_ai_fallback=False,
                engine_name=engine_name,
            )

        except Exception as exc:
            duration = int((time.monotonic() - start_time) * 1000)

            self._bus.emit(Topics.COMMAND_ERROR, {
                "command": text,
                "intent": match.intent,
                "error": str(exc),
            })

            _log.error(
                "Command execution error: '%s' — %s",
                match.intent, exc,
            )

            return ExecutionResult(
                command=text,
                intent=match.intent,
                result=f"Error: {exc}",
                duration_ms=duration,
                confidence=match.confidence,
                was_ai_fallback=False,
                engine_name=engine_name,
            )

    def _execute_ai_fallback(
        self,
        text: str,
        start_time: float,
        engine_name: str,
    ) -> ExecutionResult:
        """Forward unrecognised speech to the AI assistant."""
        _log.info("No command matched for '%s' — using AI fallback.", text)

        try:
            ai_response = self._ai.process(text)
            duration = int((time.monotonic() - start_time) * 1000)

            self._bus.emit(Topics.COMMAND_AI_FALLBACK, {
                "text": text,
                "response": ai_response,
                "duration_ms": duration,
            })

            return ExecutionResult(
                command=text,
                intent="ai_fallback",
                result=ai_response,
                duration_ms=duration,
                confidence=0.0,
                was_ai_fallback=True,
                engine_name=engine_name,
            )

        except Exception as exc:
            duration = int((time.monotonic() - start_time) * 1000)
            _log.error("AI fallback error: %s", exc)

            return ExecutionResult(
                command=text,
                intent="ai_fallback",
                result=f"I couldn't process that: {exc}",
                duration_ms=duration,
                was_ai_fallback=True,
                engine_name=engine_name,
            )
