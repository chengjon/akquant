# -*- coding: utf-8 -*-
"""Helper utilities for live trading.

Extracted from ``live.py`` to keep the ``LiveRunner`` class focused on
orchestration while reusable broker-bridge helpers live here.
"""

from typing import Any, List

# ---------------------------------------------------------------------------
# Strategy callback fan-out
# ---------------------------------------------------------------------------


class _StrategyCallbackFanout:
    """Fan-out strategy callbacks to multiple strategy instances.

    Dispatches on_order, on_trade, on_execution_report while isolating
    each callback's errors.
    """

    def __init__(self, strategies: List[Any]) -> None:
        self._strategies = strategies

    def on_order(self, order: Any) -> None:
        for strategy in self._strategies:
            callback = getattr(strategy, "on_order", None)
            if callback is None:
                continue
            try:
                callback(order)
            except Exception as exc:
                on_error = getattr(strategy, "on_error", None)
                if on_error is not None:
                    try:
                        on_error(exc, "on_order", order)
                    except Exception:
                        pass

    def on_trade(self, trade: Any) -> None:
        for strategy in self._strategies:
            callback = getattr(strategy, "on_trade", None)
            if callback is None:
                continue
            try:
                callback(trade)
            except Exception as exc:
                on_error = getattr(strategy, "on_error", None)
                if on_error is not None:
                    try:
                        on_error(exc, "on_trade", trade)
                    except Exception:
                        pass

    def on_execution_report(self, report: Any) -> None:
        for strategy in self._strategies:
            callback = getattr(strategy, "on_execution_report", None)
            if callback is None:
                continue
            try:
                callback(report)
            except Exception as exc:
                on_error = getattr(strategy, "on_error", None)
                if on_error is not None:
                    try:
                        on_error(exc, "on_execution_report", report)
                    except Exception:
                        pass


# ---------------------------------------------------------------------------
# Broker payload helpers (module-level so they can be reused without self)
# ---------------------------------------------------------------------------


def is_terminal_status(status: Any) -> bool:
    """Return ``True`` when *status* represents a terminal order state."""
    status_text = str(status).strip().lower()
    return status_text in {"filled", "cancelled", "canceled", "rejected"}


def payload_field(payload: Any, field: str) -> Any:
    """Read a field from a dict-like or attrs-like *payload*."""
    if isinstance(payload, dict):
        return payload.get(field, "")
    return getattr(payload, field, "")


def payload_to_dict(payload: Any) -> dict[str, Any]:
    """Convert a broker event *payload* into a plain ``dict``."""
    if isinstance(payload, dict):
        return dict(payload)
    if hasattr(payload, "__dict__"):
        return dict(getattr(payload, "__dict__"))
    return {}
