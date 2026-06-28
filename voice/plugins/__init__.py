"""
============================================================
  voice/plugins/ — Auto-Discovered Voice Command Plugins
============================================================

Each plugin is a Python file in this directory that defines a
class with a ``register(registry)`` method.  The CommandRegistry
auto-discovers and loads all plugins at startup.

CREATING A NEW PLUGIN:
    1. Create a new file in this directory (e.g. ``weather_plugin.py``).
    2. Define a class that inherits from ``BasePlugin``.
    3. Implement ``register(registry)`` to register commands.
    4. That's it — the plugin loads automatically.

EXAMPLE:
    class WeatherPlugin(BasePlugin):
        @property
        def name(self) -> str:
            return "Weather"

        def register(self, registry: CommandRegistry) -> None:
            registry.register(
                intent="weather.current",
                phrases=["what's the weather", "weather today"],
                handler=self._get_weather,
                description="Get current weather",
            )

        def _get_weather(self, text: str, args: dict) -> str:
            return "It's sunny and 25°C."
============================================================
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from voice.command_registry import CommandRegistry


class BasePlugin(ABC):
    """
    Abstract base class for voice command plugins.

    All plugins must inherit from this class and implement
    ``register()`` and ``name``.
    """

    @abstractmethod
    def register(self, registry: CommandRegistry) -> None:
        """
        Register all commands this plugin provides.

        Parameters
        ----------
        registry : CommandRegistry
            The central command registry to register commands with.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable plugin name."""
        ...

    @property
    def description(self) -> str:
        """Optional plugin description."""
        return ""

    @property
    def version(self) -> str:
        """Plugin version string."""
        return "1.0.0"
