from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .akquant import Bar, StrategyContext, Tick


def on_bar_event(strategy: Any, bar: Bar, ctx: StrategyContext) -> None:
    """引擎调用的 Bar 回调 (Internal)."""
    strategy.ctx = ctx
    strategy._last_event_type = "bar"

    strategy._check_order_events()

    symbol = bar.symbol
    current_pos = ctx.get_position(symbol)

    if current_pos == 0:
        strategy._hold_bars[symbol] = 0
        strategy._last_position_signs[symbol] = 0.0
    else:
        current_sign = np.sign(current_pos)
        prev_sign = strategy._last_position_signs[symbol]

        if current_sign != prev_sign:
            strategy._hold_bars[symbol] = 1
        else:
            strategy._hold_bars[symbol] += 1

        strategy._last_position_signs[symbol] = current_sign

    if not strategy._model_configured:
        strategy._auto_configure_model()

    strategy.current_bar = bar
    strategy.current_tick = None
    strategy._last_prices[bar.symbol] = bar.close

    strategy._bar_count += 1

    if strategy._bar_count < strategy.warmup_period:
        return

    if strategy._rolling_step > 0 and strategy._bar_count % strategy._rolling_step == 0:
        strategy.on_train_signal(strategy)

    strategy.on_bar(bar)


def on_tick_event(strategy: Any, tick: Tick, ctx: StrategyContext) -> None:
    """引擎调用的 Tick 回调 (Internal)."""
    strategy.ctx = ctx
    strategy._last_event_type = "tick"
    strategy._check_order_events()
    strategy.current_tick = tick
    strategy.current_bar = None
    strategy._last_prices[tick.symbol] = tick.price
    strategy.on_tick(tick)


def on_timer_event(strategy: Any, payload: str, ctx: StrategyContext) -> None:
    """引擎调用的 Timer 回调 (Internal)."""
    strategy.ctx = ctx
    strategy._check_order_events()

    if payload.startswith("__daily__|"):
        parts = payload.split("|", 2)
        if len(parts) == 3:
            _, time_str, user_payload = parts

            strategy.on_timer(user_payload)

            if not strategy._trading_days:
                try:
                    t = pd.to_datetime(time_str).time()
                    now = pd.Timestamp.now(tz=strategy.timezone)
                    target = pd.Timestamp.combine(now.date(), t).tz_localize(
                        strategy.timezone
                    )

                    if target <= now:
                        target += pd.Timedelta(days=1)

                    strategy.schedule(target, payload)
                except Exception as e:
                    print(f"Error processing daily timer: {e}")
            return

    strategy.on_timer(payload)
