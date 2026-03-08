from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class AnalyzerPlugin(Protocol):
    """Protocol for pluggable analyzers."""

    name: str

    def on_start(self, context: dict[str, Any]) -> None:
        """Handle backtest start event."""
        ...

    def on_bar(self, context: dict[str, Any]) -> None:
        """Handle bar event."""
        ...

    def on_trade(self, context: dict[str, Any]) -> None:
        """Handle trade event."""
        ...

    def on_finish(self, context: dict[str, Any]) -> dict[str, Any]:
        """Return final analyzer output."""
        ...


@dataclass
class AnalyzerManager:
    """Dispatch lifecycle events to registered analyzers."""

    plugins: list[AnalyzerPlugin] = field(default_factory=list)

    def register(self, plugin: AnalyzerPlugin) -> None:
        """Register a new analyzer plugin."""
        self.plugins.append(plugin)

    def on_start(self, context: dict[str, Any]) -> None:
        """Broadcast start event to all analyzers."""
        for plugin in self.plugins:
            plugin.on_start(context)

    def on_bar(self, context: dict[str, Any]) -> None:
        """Broadcast bar event to all analyzers."""
        for plugin in self.plugins:
            plugin.on_bar(context)

    def on_trade(self, context: dict[str, Any]) -> None:
        """Broadcast trade event to all analyzers."""
        for plugin in self.plugins:
            plugin.on_trade(context)

    def on_finish(self, context: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Collect analyzer outputs at the end of backtest."""
        result: dict[str, dict[str, Any]] = {}
        for plugin in self.plugins:
            result[plugin.name] = plugin.on_finish(context)
        return result


@dataclass
class AnalyzerTemplate:
    """Minimal analyzer template for plugin authors."""

    name: str = "template"
    seen_trades: int = 0

    def on_start(self, context: dict[str, Any]) -> None:
        """Handle start event."""
        _ = context

    def on_bar(self, context: dict[str, Any]) -> None:
        """Handle bar event."""
        _ = context

    def on_trade(self, context: dict[str, Any]) -> None:
        """Handle trade event."""
        _ = context
        self.seen_trades += 1

    def on_finish(self, context: dict[str, Any]) -> dict[str, Any]:
        """Return template summary output."""
        _ = context
        return {"seen_trades": self.seen_trades}
