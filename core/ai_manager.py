"""
============================================================
  ai_manager.py -- Future AI Integration Stub
============================================================

PURPOSE:
    Placeholder module for plugging in AI-powered features.
    Currently returns helpful fallback messages.  Designed so
    that later you can swap in:

        * OpenAI GPT (via the openai Python library)
        * Google Gemini (via google-generativeai)
        * A local model (via llama-cpp-python, Ollama, etc.)

    without changing any other module — only this file.

ARCHITECTURE:
    The ``AIManager`` class exposes a single ``process(text)``
    method that other modules call.  The internal implementation
    is hidden behind this interface, making it trivial to swap
    providers.

FUTURE HOOKS:
    * RAG (Retrieval-Augmented Generation) using local docs.
    * Conversation memory / context window management.
    * Function-calling for structured command extraction.
    * Streaming responses for the GUI.
============================================================
"""

from __future__ import annotations

import logging

# ── Logger ─────────────────────────────────────────────────
_log: logging.Logger = logging.getLogger(__name__)


class AIManager:
    """
    AI integration manager with pluggable provider support.

    Currently operates in ``"local"`` mode which returns
    pre-defined responses.  When you're ready to add a real AI
    backend, implement a new provider method and update
    ``process()``.

    Attributes
    ----------
    provider : str
        The AI provider: ``"local"`` (default), ``"openai"``,
        ``"gemini"``, or ``"ollama"``.
    is_configured : bool
        Whether an AI backend is actually connected.

    Usage
    -----
    ::

        ai = AIManager(provider="local")
        response = ai.process("What can you do?")
        print(response)
    """

    def __init__(self, provider: str = "local") -> None:
        """
        Parameters
        ----------
        provider : str, optional
            AI backend to use.  Only ``"local"`` is currently
            implemented.  Future options: ``"openai"``, ``"gemini"``,
            ``"ollama"``.
        """
        self.provider: str = provider.lower()
        self.is_configured: bool = False

        if self.provider == "local":
            self.is_configured = True
            _log.info("AIManager initialised with local fallback provider.")
        else:
            _log.warning(
                "AIManager provider '%s' is not yet implemented.  "
                "Using local fallback.",
                self.provider,
            )
            self.provider = "local"
            self.is_configured = True

    # ── Public API ─────────────────────────────────────────

    def is_available(self) -> bool:
        """Return ``True`` if the AI backend is ready."""
        return self.is_configured

    def process(self, text: str) -> str:
        """
        Process a text query and return an AI-generated response.

        Parameters
        ----------
        text : str
            The user's question or request.

        Returns
        -------
        str
            The AI's response text.
        """
        if not text or not text.strip():
            return "I didn't catch that.  Could you say that again?"

        _log.debug("AIManager.process: '%s' (provider=%s)", text, self.provider)

        if self.provider == "local":
            return self._local_response(text)

        # Future: route to OpenAI, Gemini, Ollama, etc.
        return self._local_response(text)

    # ── Private: Local Fallback ────────────────────────────

    @staticmethod
    def _local_response(text: str) -> str:
        """Generate a helpful response without any AI backend.

        This is a simple keyword-based responder that handles
        common queries and guides the user towards available
        commands.
        """
        text_lower = text.lower()

        # Greeting.
        if any(w in text_lower for w in ("hello", "hi", "hey")):
            return (
                "Hello!  I'm your Workspace Assistant.  "
                "Try saying 'help' to see what I can do."
            )

        # Capability query.
        if any(w in text_lower for w in ("what can you do", "help", "capabilities")):
            return (
                "I can help you with:\n"
                "  • Creating, opening, and managing workspaces\n"
                "  • Adding and tracking tasks\n"
                "  • Launching applications\n"
                "  • Searching Google\n"
                "  • Organising your downloads folder\n"
                "  • System controls (shutdown, restart, lock)\n"
                "\nTry commands like 'create workspace MyProject' or "
                "'add task review pull request'."
            )

        # Time-related.
        if any(w in text_lower for w in ("time", "date", "today")):
            from datetime import datetime
            now = datetime.now()
            return f"It's {now.strftime('%A, %B %d, %Y at %I:%M %p')}."

        # Default.
        return (
            "I'm not sure how to help with that yet.  "
            "Try 'help' to see available commands, or wait for "
            "an AI upgrade to handle freeform questions!"
        )
