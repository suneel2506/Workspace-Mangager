"""
============================================================
  command_registry.py — Fuzzy-Matched Command Registry
============================================================

PURPOSE:
    Central registry for all voice commands.  Supports:
    * Exact substring matching (fastest path)
    * RapidFuzz fuzzy matching for typo tolerance
    * Auto-discovery of plugins from ``voice/plugins/``
    * Parameterised commands (e.g. "search google for {query}")

DESIGN:
    * Registry pattern — no if-else chains.
    * Adding a command = one ``register()`` call.
    * Plugins auto-discovered via importlib.
    * Fuzzy threshold configurable via SettingsManager.

USAGE:
    registry = CommandRegistry(settings)
    registry.load_plugins()
    match = registry.match("oppen dashbord")
    if match:
        result = match.handler(match.raw_text, match.arguments)
============================================================
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
import re
from dataclasses import dataclass, field
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from voice.settings_manager import SettingsManager

_log: logging.Logger = logging.getLogger(__name__)

# ── Optional import ────────────────────────────────────────
try:
    from rapidfuzz import fuzz
    _RAPIDFUZZ_AVAILABLE: bool = True
except ImportError:
    _RAPIDFUZZ_AVAILABLE = False
    _log.warning(
        "rapidfuzz is not installed — fuzzy matching disabled. "
        "Install with: pip install rapidfuzz"
    )


# ── Data Classes ───────────────────────────────────────────

@dataclass
class MatchResult:
    """
    Result of matching user speech against registered commands.

    Attributes
    ----------
    intent : str
        The matched intent name (e.g. ``"dashboard.open"``).
    handler : Callable
        The function to call for execution.
    arguments : dict[str, Any]
        Extracted arguments from the speech text.
    raw_text : str
        The original user speech.
    confidence : float
        Match confidence from 0.0 to 1.0.
    matched_phrase : str
        Which registered phrase was matched.
    """
    intent: str = ""
    handler: Callable[..., str] | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    confidence: float = 0.0
    matched_phrase: str = ""


@dataclass
class _RegisteredCommand:
    """Internal representation of a registered command."""
    intent: str
    phrases: list[str]
    handler: Callable[..., str]
    description: str
    extractor: Callable[[str, str], dict[str, Any]] | None


# ── Default extractors ────────────────────────────────────

def extract_after_keyword(text: str, keyword: str) -> dict[str, Any]:
    """Extract text after the matched keyword as a 'query' argument."""
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return {}
    remainder = text[idx + len(keyword):].strip()
    # Remove filler words.
    remainder = re.sub(
        r"^(for|about|the)\s+", "", remainder, flags=re.IGNORECASE
    ).strip()
    if remainder:
        return {"query": remainder}
    return {}


def extract_name(text: str, keyword: str) -> dict[str, Any]:
    """Extract text after keyword as a 'name' argument."""
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return {}
    remainder = text[idx + len(keyword):].strip()
    remainder = re.sub(
        r"\b(please|now|for me)\b", "", remainder, flags=re.IGNORECASE
    ).strip()
    if remainder:
        return {"name": remainder}
    return {}


def no_args(text: str, keyword: str) -> dict[str, Any]:
    """Extractor that returns empty arguments."""
    return {}


# ── Command Registry ──────────────────────────────────────

class CommandRegistry:
    """
    Central command registry with fuzzy matching.

    Supports exact matching (fast path), RapidFuzz fuzzy
    matching (typo tolerance), and plugin auto-discovery.

    Parameters
    ----------
    settings : SettingsManager, optional
        For reading fuzzy_threshold.  Defaults to threshold=75.
    """

    def __init__(self, settings: SettingsManager | None = None) -> None:
        self._commands: list[_RegisteredCommand] = []
        self._settings: SettingsManager | None = settings
        self._plugins_loaded: bool = False

        _log.info("CommandRegistry initialised.")

    # ── Public API ─────────────────────────────────────────

    def register(
        self,
        intent: str,
        phrases: list[str],
        handler: Callable[..., str],
        description: str = "",
        extractor: Callable[[str, str], dict[str, Any]] | None = None,
    ) -> None:
        """
        Register a new voice command.

        Parameters
        ----------
        intent : str
            Unique intent identifier (e.g. ``"dashboard.open"``).
        phrases : list[str]
            Trigger phrases (e.g. ``["open dashboard", "show dashboard"]``).
        handler : Callable
            Function to execute.  Signature: ``handler(text, args) -> str``.
        description : str, optional
            Human-readable description for help text.
        extractor : Callable, optional
            Function that extracts arguments from speech text.
            Signature: ``extractor(text, matched_keyword) -> dict``.
            Defaults to ``no_args``.
        """
        cmd = _RegisteredCommand(
            intent=intent,
            phrases=[p.lower().strip() for p in phrases],
            handler=handler,
            description=description,
            extractor=extractor or no_args,
        )
        self._commands.append(cmd)

        _log.debug(
            "Registered command: intent='%s', phrases=%s",
            intent, cmd.phrases,
        )

    def match(self, text: str) -> MatchResult | None:
        """
        Match user speech against registered commands.

        Matching priority:
        1. Exact substring match (fastest)
        2. RapidFuzz fuzzy match (if threshold met)

        Parameters
        ----------
        text : str
            User's spoken text.

        Returns
        -------
        MatchResult | None
            Match details, or None if nothing matched.
        """
        if not text or not text.strip():
            return None

        text_lower = text.strip().lower()

        # ── Step 1: Exact substring match ──────────────────
        best_exact = self._exact_match(text_lower, text.strip())
        if best_exact is not None:
            return best_exact

        # ── Step 2: Fuzzy match ────────────────────────────
        if _RAPIDFUZZ_AVAILABLE:
            best_fuzzy = self._fuzzy_match(text_lower, text.strip())
            if best_fuzzy is not None:
                return best_fuzzy

        return None

    def load_plugins(self) -> None:
        """
        Auto-discover and load all plugins from voice/plugins/.

        Each plugin module must define a class with a
        ``register(registry)`` method.
        """
        if self._plugins_loaded:
            _log.debug("Plugins already loaded — skipping.")
            return

        import voice.plugins as plugins_pkg

        plugin_path = plugins_pkg.__path__
        loaded_count = 0

        for importer, modname, ispkg in pkgutil.iter_modules(plugin_path):
            if modname.startswith("_"):
                continue  # Skip __init__.py etc.

            try:
                module = importlib.import_module(f"voice.plugins.{modname}")

                # Find the plugin class (any class with a register method).
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and hasattr(attr, "register")
                        and attr_name != "BasePlugin"
                    ):
                        plugin_instance = attr()
                        plugin_instance.register(self)
                        loaded_count += 1
                        _log.info(
                            "Loaded plugin: %s (%s)",
                            getattr(plugin_instance, "name", modname),
                            modname,
                        )
                        break

            except Exception as exc:
                _log.error(
                    "Failed to load plugin '%s': %s", modname, exc,
                )

        self._plugins_loaded = True
        _log.info(
            "Plugin loading complete: %d plugins, %d total commands.",
            loaded_count, len(self._commands),
        )

    def get_all_commands(self) -> list[dict[str, Any]]:
        """Return a list of all registered commands (for help text)."""
        result: list[dict[str, Any]] = []
        for cmd in self._commands:
            result.append({
                "intent": cmd.intent,
                "phrases": cmd.phrases,
                "description": cmd.description,
            })
        return result

    def get_help_text(self) -> str:
        """Return formatted help text listing all commands."""
        lines: list[str] = ["Available voice commands:", ""]
        seen_intents: set[str] = set()

        for cmd in self._commands:
            if cmd.intent in seen_intents:
                continue
            seen_intents.add(cmd.intent)

            examples = ", ".join(f'"{p}"' for p in cmd.phrases[:3])
            desc = f" — {cmd.description}" if cmd.description else ""
            lines.append(f"  • {cmd.intent}{desc}")
            lines.append(f"    Trigger: {examples}")

        return "\n".join(lines)

    # ── Private matching ───────────────────────────────────

    def _exact_match(self, text_lower: str, raw_text: str) -> MatchResult | None:
        """Try exact substring matching (longest phrase first)."""
        best_match: MatchResult | None = None
        best_length: int = 0

        for cmd in self._commands:
            for phrase in cmd.phrases:
                if phrase in text_lower and len(phrase) > best_length:
                    # Extract arguments.
                    args = {}
                    if cmd.extractor is not None:
                        try:
                            args = cmd.extractor(raw_text, phrase)
                        except Exception:
                            args = {}

                    confidence = len(phrase) / max(len(text_lower), 1)
                    confidence = min(confidence, 1.0)

                    best_match = MatchResult(
                        intent=cmd.intent,
                        handler=cmd.handler,
                        arguments=args,
                        raw_text=raw_text,
                        confidence=confidence,
                        matched_phrase=phrase,
                    )
                    best_length = len(phrase)

        return best_match

    def _fuzzy_match(self, text_lower: str, raw_text: str) -> MatchResult | None:
        """Try RapidFuzz fuzzy matching."""
        threshold = 75
        if self._settings is not None:
            threshold = self._settings.get("fuzzy_threshold", 75)

        best_score: float = 0.0
        best_match: MatchResult | None = None

        for cmd in self._commands:
            for phrase in cmd.phrases:
                score = fuzz.partial_ratio(text_lower, phrase)

                if score >= threshold and score > best_score:
                    # Extract arguments.
                    args = {}
                    if cmd.extractor is not None:
                        try:
                            args = cmd.extractor(raw_text, phrase)
                        except Exception:
                            args = {}

                    best_score = score
                    best_match = MatchResult(
                        intent=cmd.intent,
                        handler=cmd.handler,
                        arguments=args,
                        raw_text=raw_text,
                        confidence=score / 100.0,
                        matched_phrase=phrase,
                    )

        return best_match
