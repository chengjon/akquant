from typing import Any

import numpy as np
import pandas as pd

from .akquant import Bar, StrategyContext, Tick
from .strategy_framework_hooks import (
    call_user_callback,
    dispatch_boundary_timer,
    dispatch_portfolio_update,
    dispatch_time_hooks,
    ensure_framework_state,
    mark_portfolio_dirty,
    register_boundary_timers,
)
from .strategy_scheduler import flush_pending_schedules


def _flush_deferred_target_value_orders(strategy: Any, event_symbol: str) -> None:
    deferred_orders = getattr(strategy, "_deferred_target_value_orders", None)
    if not deferred_orders:
        return
    remaining_orders = []
    from .strategy_trading_api import order_target_value

    for symbol, target_value, price, kwargs in deferred_orders:
        if symbol == event_symbol:
            order_target_value(strategy, target_value, symbol, price, **kwargs)
        else:
            remaining_orders.append((symbol, target_value, price, kwargs))
    setattr(strategy, "_deferred_target_value_orders", remaining_orders)
    strategy._check_order_events()


def on_bar_event(strategy: Any, bar: Bar, ctx: StrategyContext) -> None:
    """引擎调用的 Bar 回调 (Internal)."""
    ensure_framework_state(strategy)
    strategy.ctx = ctx
    flush_pending_schedules(strategy)
    register_boundary_timers(strategy)
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

    previous_price = strategy._last_prices.get(bar.symbol)
    strategy.current_bar = bar
    strategy.current_tick = None
    if hasattr(strategy, "_update_incremental_indicators"):
        strategy._update_incremental_indicators(bar)
    strategy._last_prices[bar.symbol] = bar.close
    if current_pos != 0 and previous_price is not None and previous_price != bar.close:
        mark_portfolio_dirty(strategy)
    dispatch_time_hooks(strategy)
    dispatch_portfolio_update(strategy)
    _flush_deferred_target_value_orders(strategy, bar.symbol)

    strategy._bar_count += 1

    if strategy._bar_count < strategy.warmup_period:
        return

    if strategy._rolling_step > 0 and strategy._bar_count % strategy._rolling_step == 0:
        call_user_callback(strategy, "on_train_signal", strategy, payload=strategy)

    call_user_callback(strategy, "on_bar", bar, payload=bar)
    analyzer_manager = getattr(strategy, "_analyzer_manager", None)
    if analyzer_manager is not None:
        try:
            analyzer_manager.on_bar(
                {
                    "strategy": strategy,
                    "bar": bar,
                    "engine": getattr(strategy, "_engine", None),
                    "ctx": ctx,
                    "owner_strategy_id": str(
                        getattr(ctx, "strategy_id", None)
                        or getattr(strategy, "_owner_strategy_id", "_default")
                    ),
                }
            )
        except Exception:
            pass


def on_tick_event(strategy: Any, tick: Tick, ctx: StrategyContext) -> None:
    """引擎调用的 Tick 回调 (Internal)."""
    ensure_framework_state(strategy)
    strategy.ctx = ctx
    flush_pending_schedules(strategy)
    register_boundary_timers(strategy)
    strategy._last_event_type = "tick"
    strategy._check_order_events()
    previous_price = strategy._last_prices.get(tick.symbol)
    strategy.current_tick = tick
    strategy.current_bar = None
    strategy._last_prices[tick.symbol] = tick.price
    current_pos = ctx.get_position(tick.symbol)
    if current_pos != 0 and previous_price is not None and previous_price != tick.price:
        mark_portfolio_dirty(strategy)
    dispatch_time_hooks(strategy)
    dispatch_portfolio_update(strategy)
    _flush_deferred_target_value_orders(strategy, tick.symbol)
    call_user_callback(strategy, "on_tick", tick, payload=tick)


def on_timer_event(strategy: Any, payload: str, ctx: StrategyContext) -> None:
    """引擎调用的 Timer 回调 (Internal)."""
    ensure_framework_state(strategy)
    strategy.ctx = ctx
    flush_pending_schedules(strategy)
    register_boundary_timers(strategy)
    strategy._check_order_events()
    dispatch_time_hooks(strategy)
    dispatch_portfolio_update(strategy)

    if dispatch_boundary_timer(strategy, payload):
        return

    if payload.startswith("__daily__|"):
        parts = payload.split("|", 2)
        if len(parts) == 3:
            _, time_str, user_payload = parts

            call_user_callback(strategy, "on_timer", user_payload, payload=user_payload)

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

    call_user_callback(strategy, "on_timer", payload, payload=payload)
