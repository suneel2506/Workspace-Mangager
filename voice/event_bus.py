"""
============================================================
  event_bus.py — Decoupled Pub/Sub Event System
============================================================

PURPOSE:
    The backbone of the voice assistant architecture.  Modules
    publish events on named topics and other modules subscribe
    to those topics — **no module ever imports another**.

    This keeps the codebase modular, testable, and extensible:
    adding a new feature only means subscribing to existing
    events or emitting new ones.

DESIGN:
    * Thread-safe — all operations protected by a lock.
    * Async emission — ``emit_async`` dispatches callbacks in a
      daemon thread so publishers are never blocked.
    * Wildcard subscriptions — ``subscribe("command.*", fn)``
      receives ``command.matched``, ``command.success``, etc.
    * Type-safe events via string topic constants.

TOPICS:
    speech.listening_start   — engine started recording
    speech.listening_stop    — engine stopped recording
    speech.result            — transcription result available
    speech.error             — recognition error occurred
    command.matched          — registry found a matching command
    command.executing        — handler is being called
    command.success          — handler completed successfully
    command.error            — handler raised an error
    command.ai_fallback      — no match; forwarded to AI
    dashboard.open           — dashboard was opened
    dashboard.close          — dashboard was closed
    dashboard.hide           — dashboard was hidden
    dashboard.show           — dashboard was shown
    overlay.state_change     — overlay transitioned to a new state
    wake.detected            — wake word was spoken
    settings.changed         — a setting was modified

USAGE:
    from voice.event_bus import EventBus

    bus = EventBus()
    bus.subscribe("speech.result", lambda data: print(data["text"]))
    bus.emit("speech.result", {"text": "open dashboard", "confidence": 0.95})
============================================================
"""

from __future__ import annotations

import fnmatch
import logging
import threading
from typing import Any, Callable

_log: logging.Logger = logging.getLogger(__name__)


# ── Topic Constants ────────────────────────────────────────
# Centralised here so typos are caught at import time.

class Topics:
    """String constants for all event bus topics."""

    # Speech events
    SPEECH_LISTENING_START = "speech.listening_start"
    SPEECH_LISTENING_STOP = "speech.listening_stop"
    SPEECH_RESULT = "speech.result"
    SPEECH_ERROR = "speech.error"

    # Command events
    COMMAND_MATCHED = "command.matched"
    COMMAND_EXECUTING = "command.executing"
    COMMAND_SUCCESS = "command.success"
    COMMAND_ERROR = "command.error"
    COMMAND_AI_FALLBACK = "command.ai_fallback"

    # Dashboard events
    DASHBOARD_OPEN = "dashboard.open"
    DASHBOARD_CLOSE = "dashboard.close"
    DASHBOARD_HIDE = "dashboard.hide"
    DASHBOARD_SHOW = "dashboard.show"

    # Overlay events
    OVERLAY_STATE_CHANGE = "overlay.state_change"

    # Wake word events
    WAKE_DETECTED = "wake.detected"

    # Settings events
    SETTINGS_CHANGED = "settings.changed"


# ── Subscription Entry ────────────────────────────────────

class _Subscription:
    """Internal subscription record."""

    __slots__ = ("pattern", "callback", "is_wildcard")

    def __init__(self, pattern: str, callback: Callable[..., None]) -> None:
        self.pattern: str = pattern
        self.callback: Callable[..., None] = callback
        self.is_wildcard: bool = "*" in pattern


# ── Event Bus ──────────────────────────────────────────────

class EventBus:
    """
    Thread-safe publish/subscribe event bus.

    Attributes
    ----------
    _subscriptions : dict[str, list[_Subscription]]
        Exact-topic subscriptions for O(1) lookup.
    _wildcard_subs : list[_Subscription]
        Wildcard subscriptions checked on every emit.
    _lock : threading.Lock
        Protects all mutation and iteration.

    Usage
    -----
    ::
        bus = EventBus()

        # Exact subscription
        bus.subscribe("speech.result", handle_speech)

        # Wildcard subscription
        bus.subscribe("command.*", handle_any_command)

        # Emit synchronously (blocks until all callbacks finish)
        bus.emit("speech.result", {"text": "hello"})

        # Emit asynchronously (returns immediately)
        bus.emit_async("speech.result", {"text": "hello"})
    """

    def __init__(self) -> None:
        self._subscriptions: dict[str, list[_Subscription]] = {}
        self._wildcard_subs: list[_Subscription] = []
        self._lock: threading.Lock = threading.Lock()
        _log.debug("EventBus initialised.")

    # ── Subscribe ──────────────────────────────────────────

    def subscribe(
        self,
        topic: str,
        callback: Callable[..., None],
    ) -> None:
        """
        Register a callback for a topic.

        Parameters
        ----------
        topic : str
            Event topic to listen on.  Supports ``*`` wildcards
            (e.g. ``"command.*"`` matches ``"command.success"``).
        callback : Callable
            Function to call when the event fires.  Receives
            a single ``dict`` argument with event data.
        """
        sub = _Subscription(topic, callback)

        with self._lock:
            if sub.is_wildcard:
                self._wildcard_subs.append(sub)
            else:
                self._subscriptions.setdefault(topic, []).append(sub)

        _log.debug("Subscribed to '%s': %s", topic, callback.__name__)

    # ── Unsubscribe ────────────────────────────────────────

    def unsubscribe(
        self,
        topic: str,
        callback: Callable[..., None],
    ) -> None:
        """
        Remove a previously registered callback.

        Parameters
        ----------
        topic : str
            The exact topic string used during ``subscribe()``.
        callback : Callable
            The same function object that was registered.
        """
        with self._lock:
            if "*" in topic:
                self._wildcard_subs = [
                    s for s in self._wildcard_subs
                    if not (s.pattern == topic and s.callback is callback)
                ]
            else:
                subs = self._subscriptions.get(topic, [])
                self._subscriptions[topic] = [
                    s for s in subs if s.callback is not callback
                ]

        _log.debug("Unsubscribed from '%s': %s", topic, callback.__name__)

    # ── Emit (synchronous) ─────────────────────────────────

    def emit(self, topic: str, data: dict[str, Any] | None = None) -> None:
        """
        Publish an event synchronously.

        All matching callbacks are invoked in the calling thread.
        Exceptions in callbacks are caught and logged (never
        propagated to the publisher).

        Parameters
        ----------
        topic : str
            Event topic to publish.
        data : dict, optional
            Event payload.  Defaults to ``{}``.
        """
        if data is None:
            data = {}

        callbacks = self._collect_callbacks(topic)

        for cb in callbacks:
            try:
                cb(data)
            except Exception as exc:
                _log.error(
                    "EventBus callback error on '%s' (%s): %s",
                    topic, cb.__name__, exc,
                )

    # ── Emit (asynchronous) ────────────────────────────────

    def emit_async(
        self,
        topic: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """
        Publish an event asynchronously.

        Callbacks are invoked in a daemon thread so the publisher
        returns immediately.

        Parameters
        ----------
        topic : str
            Event topic to publish.
        data : dict, optional
            Event payload.  Defaults to ``{}``.
        """
        thread = threading.Thread(
            target=self.emit,
            args=(topic, data),
            daemon=True,
            name=f"EventBus-{topic}",
        )
        thread.start()

    # ── Helpers ─────────────────────────────────────────────

    def _collect_callbacks(
        self,
        topic: str,
    ) -> list[Callable[..., None]]:
        """Gather all callbacks that match a topic."""
        callbacks: list[Callable[..., None]] = []

        with self._lock:
            # Exact matches.
            for sub in self._subscriptions.get(topic, []):
                callbacks.append(sub.callback)

            # Wildcard matches.
            for sub in self._wildcard_subs:
                if fnmatch.fnmatch(topic, sub.pattern):
                    callbacks.append(sub.callback)

        return callbacks

    def has_subscribers(self, topic: str) -> bool:
        """Return True if any callback is registered for the topic."""
        return len(self._collect_callbacks(topic)) > 0

    def clear(self) -> None:
        """Remove all subscriptions."""
        with self._lock:
            self._subscriptions.clear()
            self._wildcard_subs.clear()
        _log.debug("EventBus cleared.")
