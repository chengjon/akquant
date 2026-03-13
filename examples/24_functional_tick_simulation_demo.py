#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Function-style tick callback simulation demo."""

from types import SimpleNamespace
from typing import Any, cast

import pandas as pd
from akquant.akquant import StrategyContext, Tick
from akquant.backtest import FunctionalStrategy


class DemoContext:
    """Minimal context object for simulating tick callback dispatch."""

    def __init__(self) -> None:
        """Initialize required context fields."""
        self.canceled_order_ids: list[str] = []
        self.active_orders: list[Any] = []
        self.recent_trades: list[Any] = []
        self.cash = 100000.0
        self.positions: dict[str, float] = {}
        self.available_positions: dict[str, float] = {}
        self.session = "normal"
        self.current_time = 0

    def get_position(self, symbol: str) -> float:
        """Return mocked position."""
        return float(self.positions.get(symbol, 0.0))


def initialize(ctx: Any) -> None:
    """Initialize state for function-style strategy."""
    ctx.events = []


def on_bar(ctx: Any, bar: Any) -> None:
    """Unused in this tick simulation."""
    ctx.events.append("bar")


def on_tick(ctx: Any, tick: Tick) -> None:
    """Record tick callback."""
    ctx.events.append(f"tick:{tick.symbol}")


def on_order(ctx: Any, order: Any) -> None:
    """Record order callback."""
    ctx.events.append(f"order:{order.id}")


def on_trade(ctx: Any, trade: Any) -> None:
    """Record trade callback."""
    ctx.events.append(f"trade:{trade.order_id}")


def on_timer(ctx: Any, payload: str) -> None:
    """Record timer callback."""
    ctx.events.append(f"timer:{payload}")


def main() -> None:
    """Run tick callback simulation with internal event dispatch."""
    strategy = FunctionalStrategy(
        initialize=initialize,
        on_bar=on_bar,
        on_tick=on_tick,
        on_order=on_order,
        on_trade=on_trade,
        on_timer=on_timer,
    )
    ctx = cast(StrategyContext, DemoContext())

    ts1 = int(pd.Timestamp("2023-01-01 09:30:01", tz="Asia/Shanghai").value)
    ctx.current_time = ts1
    ctx.active_orders = cast(
        Any, [SimpleNamespace(id="o1", status="Submitted", filled_quantity=0.0)]
    )
    ctx.recent_trades = cast(Any, [SimpleNamespace(order_id="o1")])
    tick1 = Tick(timestamp=ts1, price=101.0, volume=200.0, symbol="TEST")
    strategy._on_tick_event(tick1, ctx)

    ts2 = int(pd.Timestamp("2023-01-01 09:31:01", tz="Asia/Shanghai").value)
    ctx.current_time = ts2
    ctx.active_orders = cast(
        Any, [SimpleNamespace(id="o2", status="Submitted", filled_quantity=0.0)]
    )
    ctx.recent_trades = cast(Any, [SimpleNamespace(order_id="o2")])
    tick2 = Tick(timestamp=ts2, price=101.5, volume=220.0, symbol="TEST")
    strategy._on_tick_event(tick2, ctx)

    ctx.active_orders = []
    ctx.recent_trades = []
    strategy._on_timer_event("rebalance", ctx)

    events = getattr(strategy, "events", [])
    print(f"events_total={len(events)}")
    print(f"ticks={sum(1 for x in events if x.startswith('tick:'))}")
    print(f"orders={sum(1 for x in events if x.startswith('order:'))}")
    print(f"trades={sum(1 for x in events if x.startswith('trade:'))}")
    print(f"timers={sum(1 for x in events if x.startswith('timer:'))}")
    print("done_functional_tick_simulation_demo")


if __name__ == "__main__":
    main()
