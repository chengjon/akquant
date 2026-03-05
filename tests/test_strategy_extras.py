import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pandas as pd
import pytest
from akquant import run_backtest, run_warm_start, save_snapshot
from akquant.akquant import Bar, OrderStatus, StrategyContext, Tick
from akquant.backtest import FunctionalStrategy
from akquant.strategy import Strategy, StrategyRuntimeConfig


class MyStrategy(Strategy):
    """Test strategy."""

    def on_bar(self, bar: Bar) -> None:
        """Handle bar event."""
        self.log(f"Bar {self.symbol} Close: {self.close}")

    def on_tick(self, tick: Tick) -> None:
        """Handle tick event."""
        self.log(f"Tick {self.symbol} Price: {self.close}")


def test_strategy_logging(caplog: Any) -> None:
    """Test logging."""
    strategy = MyStrategy()

    # Mock context
    ctx = MagicMock(spec=StrategyContext)
    ctx.get_position.return_value = 0.0

    # Mock Bar
    ts = pd.Timestamp("2023-01-01 09:30:00", tz="Asia/Shanghai").value
    bar = Bar(
        timestamp=ts,
        open=100.0,
        high=105.0,
        low=95.0,
        close=102.0,
        volume=1000.0,
        symbol="AAPL",
    )

    with caplog.at_level(logging.INFO, logger="akquant"):
        strategy._on_bar_event(bar, ctx)

    assert "Bar AAPL Close: 102.0" in caplog.text
    assert "[2023-01-01 09:30:00]" in caplog.text


def test_strategy_properties() -> None:
    """Test properties."""
    strategy = MyStrategy()
    ctx = MagicMock(spec=StrategyContext)
    ctx.get_position.return_value = 0.0

    # Test Bar Properties
    ts = pd.Timestamp("2023-01-01 09:30:00", tz="Asia/Shanghai").value
    bar = Bar(
        timestamp=ts,
        open=100.0,
        high=105.0,
        low=95.0,
        close=102.0,
        volume=1000.0,
        symbol="AAPL",
    )
    strategy._on_bar_event(bar, ctx)

    assert strategy.symbol == "AAPL"
    assert strategy.close == 102.0
    assert strategy.open == 100.0
    assert strategy.high == 105.0
    assert strategy.low == 95.0
    assert strategy.volume == 1000.0

    # Test Tick Properties
    ts_tick = pd.Timestamp("2023-01-01 09:30:01", tz="Asia/Shanghai").value
    tick = Tick(timestamp=ts_tick, price=103.0, volume=500.0, symbol="GOOG")
    strategy._on_tick_event(tick, ctx)

    assert strategy.symbol == "GOOG"
    assert strategy.close == 103.0  # close maps to price in tick
    assert strategy.volume == 500.0
    # Open/High/Low should be 0.0 or handle gracefully?
    # Current implementation returns 0.0 if not current_bar
    assert strategy.open == 0.0
    assert strategy.high == 0.0
    assert strategy.low == 0.0


class StartCounterStrategy(Strategy):
    """Strategy for lifecycle callback counting."""

    def __init__(self) -> None:
        """Initialize counters."""
        self.start_calls = 0
        self.resume_calls = 0

    def on_start(self) -> None:
        """Count start callbacks."""
        self.start_calls += 1

    def on_resume(self) -> None:
        """Count resume callbacks."""
        self.resume_calls += 1


class WarmStartSequenceStrategy(Strategy):
    """Strategy for warm start callback ordering tests."""

    def __init__(self) -> None:
        """Initialize callback sequence container."""
        self.events: list[str] = []

    def on_resume(self) -> None:
        """Record resume callback."""
        self.events.append("on_resume")

    def on_start(self) -> None:
        """Record start callback."""
        self.events.append("on_start")


def test_on_start_internal_idempotent() -> None:
    """Start callback should run once when internal start is called repeatedly."""
    strategy = StartCounterStrategy()
    strategy._on_start_internal()
    strategy._on_start_internal()
    assert strategy.start_calls == 1
    assert strategy.resume_calls == 0


def test_on_resume_runs_once_before_on_start() -> None:
    """Resume callback should run once before start in restored mode."""
    strategy = StartCounterStrategy()
    strategy._is_restored = True
    strategy._on_start_internal()
    strategy._on_start_internal()
    assert strategy.resume_calls == 1
    assert strategy.start_calls == 1


def test_warm_start_callback_sequence() -> None:
    """Warm start should call on_resume before on_start once."""
    strategy = WarmStartSequenceStrategy()
    strategy._is_restored = True
    strategy._on_start_internal()
    strategy._on_start_internal()
    assert strategy.events == ["on_resume", "on_start"]


class EventCounterStrategy(Strategy):
    """Strategy for event callback counting."""

    def __init__(self) -> None:
        """Initialize counters."""
        self.trade_count = 0
        self.tick_count = 0
        self.timer_count = 0

    def on_bar(self, bar: Bar) -> None:
        """Ignore bar events."""
        return

    def on_tick(self, tick: Tick) -> None:
        """Count tick callbacks."""
        self.tick_count += 1

    def on_timer(self, payload: str) -> None:
        """Count timer callbacks."""
        self.timer_count += 1

    def on_trade(self, trade: Any) -> None:
        """Count trade callbacks."""
        self.trade_count += 1


class TradeDedupeLimitStrategy(Strategy):
    """Strategy for trade de-duplication cache limit tests."""

    trade_dedupe_cache_size = 2

    def __init__(self) -> None:
        """Initialize trade callbacks counter."""
        self.trade_count = 0

    def on_trade(self, trade: Any) -> None:
        """Count trade callbacks."""
        self.trade_count += 1


def test_trade_callback_not_duplicated_on_bar() -> None:
    """Trade callback should be triggered once per bar event."""
    strategy = EventCounterStrategy()
    ctx = MagicMock(spec=StrategyContext)
    ctx.get_position.return_value = 0.0
    ctx.canceled_order_ids = []
    ctx.active_orders = []
    ctx.recent_trades = [SimpleNamespace(order_id="o1")]

    ts = pd.Timestamp("2023-01-01 09:30:00", tz="Asia/Shanghai").value
    bar = Bar(
        timestamp=ts,
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1000.0,
        symbol="AAPL",
    )
    strategy._on_bar_event(bar, ctx)
    assert strategy.trade_count == 1


def test_tick_and_timer_process_order_events() -> None:
    """Tick and timer events should process trade callbacks."""
    strategy = EventCounterStrategy()
    ctx = MagicMock(spec=StrategyContext)
    ctx.get_position.return_value = 0.0
    ctx.canceled_order_ids = []
    ctx.active_orders = []
    ctx.recent_trades = [SimpleNamespace(order_id="o1")]

    ts_tick = pd.Timestamp("2023-01-01 09:30:01", tz="Asia/Shanghai").value
    tick = Tick(timestamp=ts_tick, price=103.0, volume=500.0, symbol="GOOG")
    strategy._on_tick_event(tick, ctx)

    assert strategy.tick_count == 1
    assert strategy.trade_count == 1

    ctx.recent_trades = [SimpleNamespace(order_id="o2")]
    strategy._on_timer_event("rebalance", ctx)
    assert strategy.timer_count == 1
    assert strategy.trade_count == 2


def test_trade_callback_not_replayed_across_events() -> None:
    """Repeated recent_trades entries should not replay on_trade callback."""
    strategy = EventCounterStrategy()
    ctx = MagicMock(spec=StrategyContext)
    ctx.get_position.return_value = 0.0
    ctx.canceled_order_ids = []
    ctx.active_orders = []
    ctx.recent_trades = [SimpleNamespace(order_id="o1")]

    ts_tick = pd.Timestamp("2023-01-01 09:30:01", tz="Asia/Shanghai").value
    tick = Tick(timestamp=ts_tick, price=103.0, volume=500.0, symbol="GOOG")
    strategy._on_tick_event(tick, ctx)
    assert strategy.trade_count == 1

    strategy._on_timer_event("rebalance", ctx)
    assert strategy.trade_count == 1
    assert strategy.timer_count == 1


def test_trade_dedupe_cache_limit_eviction_allows_replay() -> None:
    """Dedupe cache should evict old keys once limit reached."""
    strategy = TradeDedupeLimitStrategy()
    ctx = MagicMock(spec=StrategyContext)
    ctx.get_position.return_value = 0.0
    ctx.canceled_order_ids = []
    ctx.active_orders = []

    ctx.recent_trades = [SimpleNamespace(order_id="o1")]
    ts_tick = pd.Timestamp("2023-01-01 09:30:01", tz="Asia/Shanghai").value
    tick = Tick(timestamp=ts_tick, price=103.0, volume=500.0, symbol="GOOG")
    strategy._on_tick_event(tick, ctx)
    assert strategy.trade_count == 1

    ctx.recent_trades = [SimpleNamespace(order_id="o2")]
    strategy._on_timer_event("t2", ctx)
    assert strategy.trade_count == 2

    ctx.recent_trades = [SimpleNamespace(order_id="o3")]
    strategy._on_timer_event("t3", ctx)
    assert strategy.trade_count == 3

    ctx.recent_trades = [SimpleNamespace(order_id="o1")]
    strategy._on_timer_event("t4", ctx)
    assert strategy.trade_count == 4


class SequenceStrategy(Strategy):
    """Strategy for callback sequence assertions."""

    def __init__(self) -> None:
        """Initialize callback record list."""
        self.events: list[str] = []

    def on_bar(self, bar: Bar) -> None:
        """Record bar callback."""
        self.events.append("on_bar")

    def on_tick(self, tick: Tick) -> None:
        """Record tick callback."""
        self.events.append("on_tick")

    def on_timer(self, payload: str) -> None:
        """Record timer callback."""
        self.events.append(f"on_timer:{payload}")

    def on_order(self, order: Any) -> None:
        """Record order callback."""
        self.events.append(f"on_order:{order.id}")

    def on_trade(self, trade: Any) -> None:
        """Record trade callback."""
        self.events.append(f"on_trade:{trade.order_id}")


def _build_ctx_with_order_and_trade(order_id: str = "o1") -> MagicMock:
    """Build a mocked strategy context with one active order and one trade."""
    ctx = MagicMock(spec=StrategyContext)
    ctx.get_position.return_value = 0.0
    ctx.canceled_order_ids = []
    ctx.active_orders = [
        SimpleNamespace(id=order_id, status="Submitted", filled_quantity=0.0)
    ]
    ctx.recent_trades = [SimpleNamespace(order_id=order_id)]
    return ctx


def test_functional_strategy_supports_extended_callbacks() -> None:
    """FunctionalStrategy should delegate tick/order/trade/timer callbacks."""
    events: list[str] = []

    def initialize(ctx: Any) -> None:
        events.append("initialize")

    def on_bar(ctx: Any, bar: Bar) -> None:
        events.append("bar")

    def on_tick(ctx: Any, tick: Tick) -> None:
        events.append("tick")

    def on_order(ctx: Any, order: Any) -> None:
        events.append(f"order:{order.id}")

    def on_trade(ctx: Any, trade: Any) -> None:
        events.append(f"trade:{trade.order_id}")

    def on_timer(ctx: Any, payload: str) -> None:
        events.append(f"timer:{payload}")

    strategy = FunctionalStrategy(
        initialize=initialize,
        on_bar=on_bar,
        on_tick=on_tick,
        on_order=on_order,
        on_trade=on_trade,
        on_timer=on_timer,
    )

    ts_bar = pd.Timestamp("2023-01-01 09:30:00", tz="Asia/Shanghai").value
    bar = Bar(
        timestamp=ts_bar,
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1000.0,
        symbol="AAPL",
    )
    strategy._on_bar_event(bar, _build_ctx_with_order_and_trade("bar_order"))

    ts_tick = pd.Timestamp("2023-01-01 09:30:01", tz="Asia/Shanghai").value
    tick = Tick(timestamp=ts_tick, price=103.0, volume=500.0, symbol="AAPL")
    strategy._on_tick_event(tick, _build_ctx_with_order_and_trade("tick_order"))
    strategy._on_timer_event(
        "rebalance", _build_ctx_with_order_and_trade("timer_order")
    )

    assert events[0] == "initialize"
    assert "order:bar_order" in events
    assert "trade:bar_order" in events
    assert "bar" in events
    assert "order:tick_order" in events
    assert "trade:tick_order" in events
    assert "tick" in events
    assert "order:timer_order" in events
    assert "trade:timer_order" in events
    assert "timer:rebalance" in events


def test_functional_strategy_callback_sequence_contract() -> None:
    """Function-style callbacks should follow framework callback ordering."""
    events: list[str] = []

    def on_bar(ctx: Any, bar: Bar) -> None:
        events.append("bar")

    def on_tick(ctx: Any, tick: Tick) -> None:
        events.append("tick")

    def on_order(ctx: Any, order: Any) -> None:
        events.append(f"order:{order.id}")

    def on_trade(ctx: Any, trade: Any) -> None:
        events.append(f"trade:{trade.order_id}")

    def on_timer(ctx: Any, payload: str) -> None:
        events.append(f"timer:{payload}")

    strategy = FunctionalStrategy(
        initialize=None,
        on_bar=on_bar,
        on_tick=on_tick,
        on_order=on_order,
        on_trade=on_trade,
        on_timer=on_timer,
    )

    ts_bar = pd.Timestamp("2023-01-01 09:30:00", tz="Asia/Shanghai").value
    bar = Bar(
        timestamp=ts_bar,
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1000.0,
        symbol="AAPL",
    )
    strategy._on_bar_event(bar, _build_ctx_with_order_and_trade("bar_order"))

    ts_tick = pd.Timestamp("2023-01-01 09:30:01", tz="Asia/Shanghai").value
    tick = Tick(timestamp=ts_tick, price=103.0, volume=500.0, symbol="AAPL")
    strategy._on_tick_event(tick, _build_ctx_with_order_and_trade("tick_order"))
    strategy._on_timer_event(
        "rebalance", _build_ctx_with_order_and_trade("timer_order")
    )

    assert events == [
        "order:bar_order",
        "trade:bar_order",
        "bar",
        "order:tick_order",
        "trade:tick_order",
        "tick",
        "order:timer_order",
        "trade:timer_order",
        "timer:rebalance",
    ]


def test_callback_sequence_on_bar() -> None:
    """Order/trade callbacks should run before bar callback."""
    strategy = SequenceStrategy()
    ctx = _build_ctx_with_order_and_trade("bar_order")
    ts = pd.Timestamp("2023-01-01 09:30:00", tz="Asia/Shanghai").value
    bar = Bar(
        timestamp=ts,
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1000.0,
        symbol="AAPL",
    )

    strategy._on_bar_event(bar, ctx)
    assert strategy.events == ["on_order:bar_order", "on_trade:bar_order", "on_bar"]


def test_callback_sequence_on_tick() -> None:
    """Order/trade callbacks should run before tick callback."""
    strategy = SequenceStrategy()
    ctx = _build_ctx_with_order_and_trade("tick_order")
    ts_tick = pd.Timestamp("2023-01-01 09:30:01", tz="Asia/Shanghai").value
    tick = Tick(timestamp=ts_tick, price=103.0, volume=500.0, symbol="GOOG")

    strategy._on_tick_event(tick, ctx)
    assert strategy.events == ["on_order:tick_order", "on_trade:tick_order", "on_tick"]


def test_callback_sequence_on_timer() -> None:
    """Order/trade callbacks should run before timer callback."""
    strategy = SequenceStrategy()
    ctx = _build_ctx_with_order_and_trade("timer_order")

    strategy._on_timer_event("rebalance", ctx)
    assert strategy.events == [
        "on_order:timer_order",
        "on_trade:timer_order",
        "on_timer:rebalance",
    ]


class WarmStartE2EStrategy(Strategy):
    """Strategy for warm start end-to-end test."""

    def __init__(self) -> None:
        """Initialize strategy state."""
        self.events: list[str] = []
        self.bar_seen = 0

    def on_resume(self) -> None:
        """Record resume callback."""
        self.events.append("on_resume")

    def on_start(self) -> None:
        """Record start callback."""
        self.events.append("on_start")

    def on_bar(self, bar: Bar) -> None:
        """Record bar callback and mutate state."""
        self.bar_seen += 1
        self.events.append(f"on_bar:{self.bar_seen}")


class RuntimeConfigWarmStartStrategy(Strategy):
    """Strategy for warm start runtime config injection test."""

    def __init__(self) -> None:
        """Initialize records."""
        self.errors: list[str] = []
        self.bar_seen = 0

    def on_bar(self, bar: Bar) -> None:
        """Raise only after restored to test warm-start injection."""
        self.bar_seen += 1
        if self.is_restored:
            raise ValueError("warm_boom")

    def on_error(self, error: Exception, source: str, payload: Any = None) -> None:
        """Record callback source."""
        self.errors.append(source)


class RuntimeConfigWarmConflictStrategy(Strategy):
    """Strategy for warm-start runtime config conflict behavior tests."""

    def __init__(self) -> None:
        """Initialize with strict runtime config."""
        self.errors: list[str] = []
        self.runtime_config = StrategyRuntimeConfig(error_mode="raise")

    def on_bar(self, bar: Bar) -> None:
        """Raise only after restored."""
        if self.is_restored:
            raise ValueError("warm_conflict_boom")

    def on_error(self, error: Exception, source: str, payload: Any = None) -> None:
        """Record callback source."""
        self.errors.append(source)


def _make_bars(
    start: str,
    periods: int,
    symbol: str = "TEST",
    start_price: float = 100.0,
) -> list[Bar]:
    """Create deterministic bar list."""
    bars: list[Bar] = []
    idx = pd.date_range(start=start, periods=periods, freq="D")
    for i, ts in enumerate(idx):
        price = start_price + float(i)
        bars.append(
            Bar(
                timestamp=ts.value,
                open=price,
                high=price + 1.0,
                low=price - 1.0,
                close=price + 0.5,
                volume=1000.0 + i,
                symbol=symbol,
            )
        )
    return bars


def test_run_warm_start_end_to_end_lifecycle(tmp_path: Path) -> None:
    """Warm start should preserve state and callback lifecycle ordering."""
    checkpoint = tmp_path / "snapshot.pkl"
    phase1 = _make_bars("2023-01-01", 4)
    phase2 = _make_bars("2023-01-05", 3, start_price=104.0)

    result1 = run_backtest(
        data=phase1,
        strategy=WarmStartE2EStrategy,
        symbol="TEST",
        initial_cash=100000.0,
        show_progress=False,
    )

    save_snapshot(result1.engine, result1.strategy, str(checkpoint))  # type: ignore[arg-type]

    result2 = run_warm_start(
        checkpoint_path=str(checkpoint),
        data=phase2,
        symbol="TEST",
        show_progress=False,
    )

    strategy = result2.strategy
    assert strategy is not None
    assert strategy.bar_seen == 7
    assert strategy.events[0] == "on_start"
    assert "on_resume" in strategy.events
    resume_idx = strategy.events.index("on_resume")
    assert strategy.events[resume_idx + 1] == "on_start"
    assert strategy.events[-1] == "on_bar:7"
    assert result2.metrics.initial_market_value == result1.metrics.end_market_value


def test_run_warm_start_accepts_strategy_runtime_config(tmp_path: Path) -> None:
    """run_warm_start should inject runtime config into restored strategy."""
    checkpoint = tmp_path / "snapshot_runtime_config.pkl"
    phase1 = _make_bars("2023-01-01", 2)
    phase2 = _make_bars("2023-01-03", 2, start_price=102.0)

    result1 = run_backtest(
        data=phase1,
        strategy=RuntimeConfigWarmStartStrategy,
        symbol="TEST",
        show_progress=False,
    )
    save_snapshot(result1.engine, result1.strategy, str(checkpoint))  # type: ignore[arg-type]

    result2 = run_warm_start(
        checkpoint_path=str(checkpoint),
        data=phase2,
        symbol="TEST",
        show_progress=False,
        strategy_runtime_config={"error_mode": "continue"},
    )

    strategy = result2.strategy
    assert strategy is not None
    assert strategy.errors == ["on_bar", "on_bar"]


def test_run_warm_start_runtime_config_override_true_by_default(
    tmp_path: Path, caplog: Any
) -> None:
    """run_warm_start should override strategy runtime config by default."""
    checkpoint = tmp_path / "snapshot_runtime_override_true.pkl"
    phase1 = _make_bars("2023-01-01", 2)
    phase2 = _make_bars("2023-01-03", 2, start_price=102.0)

    result1 = run_backtest(
        data=phase1,
        strategy=RuntimeConfigWarmConflictStrategy,
        symbol="TEST",
        show_progress=False,
    )
    save_snapshot(result1.engine, result1.strategy, str(checkpoint))  # type: ignore[arg-type]

    with caplog.at_level(logging.WARNING, logger="akquant"):
        result2 = run_warm_start(
            checkpoint_path=str(checkpoint),
            data=phase2,
            symbol="TEST",
            show_progress=False,
            strategy_runtime_config={"error_mode": "continue"},
        )

    strategy = result2.strategy
    assert strategy is not None
    assert strategy.errors == ["on_bar", "on_bar"]
    assert "overrides strategy runtime_config" in caplog.text
    assert "error_mode: raise -> continue" in caplog.text


def test_run_warm_start_runtime_config_override_false_keeps_strategy_config(
    tmp_path: Path, caplog: Any
) -> None:
    """runtime_config_override=False should keep restored strategy config."""
    checkpoint = tmp_path / "snapshot_runtime_override_false.pkl"
    phase1 = _make_bars("2023-01-01", 2)
    phase2 = _make_bars("2023-01-03", 1, start_price=102.0)

    result1 = run_backtest(
        data=phase1,
        strategy=RuntimeConfigWarmConflictStrategy,
        symbol="TEST",
        show_progress=False,
    )
    save_snapshot(result1.engine, result1.strategy, str(checkpoint))  # type: ignore[arg-type]

    with caplog.at_level(logging.WARNING, logger="akquant"):
        with pytest.raises(ValueError, match="warm_conflict_boom"):
            run_warm_start(
                checkpoint_path=str(checkpoint),
                data=phase2,
                symbol="TEST",
                show_progress=False,
                strategy_runtime_config={"error_mode": "continue"},
                runtime_config_override=False,
            )

    assert "runtime_config_override=False" in caplog.text
    assert "error_mode: raise -> continue" in caplog.text


def test_run_warm_start_rejects_invalid_strategy_runtime_config_type(
    tmp_path: Path,
) -> None:
    """Invalid warm-start runtime config type should fail fast."""
    checkpoint = tmp_path / "snapshot_runtime_invalid_type.pkl"
    phase1 = _make_bars("2023-01-01", 2)
    phase2 = _make_bars("2023-01-03", 1, start_price=102.0)

    result1 = run_backtest(
        data=phase1,
        strategy=RuntimeConfigWarmStartStrategy,
        symbol="TEST",
        show_progress=False,
    )
    save_snapshot(result1.engine, result1.strategy, str(checkpoint))  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="strategy_runtime_config"):
        run_warm_start(
            checkpoint_path=str(checkpoint),
            data=phase2,
            symbol="TEST",
            show_progress=False,
            strategy_runtime_config=cast(Any, "invalid"),
        )


def test_run_warm_start_rejects_invalid_runtime_config_from_forwarded_kwargs(
    tmp_path: Path,
) -> None:
    """Forwarded keyword map should keep strict runtime config validation."""
    checkpoint = tmp_path / "snapshot_runtime_forwarded_kwargs.pkl"
    phase1 = _make_bars("2023-01-01", 2)
    phase2 = _make_bars("2023-01-03", 1, start_price=102.0)

    result1 = run_backtest(
        data=phase1,
        strategy=RuntimeConfigWarmStartStrategy,
        symbol="TEST",
        show_progress=False,
    )
    save_snapshot(result1.engine, result1.strategy, str(checkpoint))  # type: ignore[arg-type]

    forwarded_kwargs = cast(Any, {"strategy_runtime_config": "invalid"})
    with pytest.raises(TypeError, match="strategy_runtime_config"):
        run_warm_start(
            checkpoint_path=str(checkpoint),
            data=phase2,
            symbol="TEST",
            show_progress=False,
            **forwarded_kwargs,
        )


def test_run_warm_start_accepts_runtime_config_from_forwarded_kwargs(
    tmp_path: Path,
) -> None:
    """Forwarded keyword map should support valid runtime config injection."""
    checkpoint = tmp_path / "snapshot_runtime_forwarded_valid.pkl"
    phase1 = _make_bars("2023-01-01", 2)
    phase2 = _make_bars("2023-01-03", 2, start_price=102.0)

    result1 = run_backtest(
        data=phase1,
        strategy=RuntimeConfigWarmStartStrategy,
        symbol="TEST",
        show_progress=False,
    )
    save_snapshot(result1.engine, result1.strategy, str(checkpoint))  # type: ignore[arg-type]

    forwarded_kwargs = cast(
        Any, {"strategy_runtime_config": {"error_mode": "continue"}}
    )
    result2 = run_warm_start(
        checkpoint_path=str(checkpoint),
        data=phase2,
        symbol="TEST",
        show_progress=False,
        **forwarded_kwargs,
    )

    strategy = result2.strategy
    assert strategy is not None
    assert strategy.errors == ["on_bar", "on_bar"]


def test_run_warm_start_rejects_unknown_strategy_runtime_config_fields(
    tmp_path: Path,
) -> None:
    """Unknown warm-start runtime config fields should fail with field-level error."""
    checkpoint = tmp_path / "snapshot_runtime_unknown_field.pkl"
    phase1 = _make_bars("2023-01-01", 2)
    phase2 = _make_bars("2023-01-03", 1, start_price=102.0)

    result1 = run_backtest(
        data=phase1,
        strategy=RuntimeConfigWarmStartStrategy,
        symbol="TEST",
        show_progress=False,
    )
    save_snapshot(result1.engine, result1.strategy, str(checkpoint))  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="unknown fields: unknown_flag"):
        run_warm_start(
            checkpoint_path=str(checkpoint),
            data=phase2,
            symbol="TEST",
            show_progress=False,
            strategy_runtime_config=cast(Any, {"unknown_flag": True}),
        )


def test_run_warm_start_rejects_invalid_strategy_runtime_config_values(
    tmp_path: Path,
) -> None:
    """Invalid warm-start runtime config values should fail with wrapped error."""
    checkpoint = tmp_path / "snapshot_runtime_invalid_value.pkl"
    phase1 = _make_bars("2023-01-01", 2)
    phase2 = _make_bars("2023-01-03", 1, start_price=102.0)

    result1 = run_backtest(
        data=phase1,
        strategy=RuntimeConfigWarmStartStrategy,
        symbol="TEST",
        show_progress=False,
    )
    save_snapshot(result1.engine, result1.strategy, str(checkpoint))  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="invalid strategy_runtime_config"):
        run_warm_start(
            checkpoint_path=str(checkpoint),
            data=phase2,
            symbol="TEST",
            show_progress=False,
            strategy_runtime_config={"portfolio_update_eps": -1},
        )


class WarmStartMultiSymbolStrategy(Strategy):
    """Strategy for multi-symbol warm start continuity test."""

    def __init__(self) -> None:
        """Initialize per-symbol counters."""
        self.total_bars = 0
        self.by_symbol: dict[str, int] = {}
        self.events: list[str] = []

    def on_resume(self) -> None:
        """Record resume callback."""
        self.events.append("on_resume")

    def on_start(self) -> None:
        """Record start callback."""
        self.events.append("on_start")

    def on_bar(self, bar: Bar) -> None:
        """Track processed bars by symbol."""
        self.total_bars += 1
        self.by_symbol[bar.symbol] = self.by_symbol.get(bar.symbol, 0) + 1


def _make_symbol_df(
    symbol: str,
    start: str,
    periods: int,
    start_price: float,
) -> pd.DataFrame:
    """Create deterministic OHLCV dataframe for a symbol."""
    ts = pd.date_range(start=start, periods=periods, freq="D", tz="UTC")
    prices = [start_price + float(i) for i in range(periods)]
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": prices,
            "high": [p + 1.0 for p in prices],
            "low": [p - 1.0 for p in prices],
            "close": [p + 0.5 for p in prices],
            "volume": [1000.0 + float(i) for i in range(periods)],
            "symbol": [symbol] * periods,
        }
    )


def test_run_warm_start_multi_symbol_continuity(tmp_path: Path) -> None:
    """Warm start should preserve multi-symbol state continuity."""
    checkpoint = tmp_path / "snapshot_multi.pkl"
    phase1 = {
        "AAA": _make_symbol_df("AAA", "2023-01-01", 3, 100.0),
        "BBB": _make_symbol_df("BBB", "2023-01-01", 3, 200.0),
    }
    phase2 = {
        "AAA": _make_symbol_df("AAA", "2023-01-04", 2, 103.0),
        "BBB": _make_symbol_df("BBB", "2023-01-04", 2, 203.0),
    }

    result1 = run_backtest(
        data=phase1,
        strategy=WarmStartMultiSymbolStrategy,
        symbol="BENCHMARK",
        initial_cash=100000.0,
        show_progress=False,
    )

    save_snapshot(result1.engine, result1.strategy, str(checkpoint))  # type: ignore[arg-type]

    result2 = run_warm_start(
        checkpoint_path=str(checkpoint),
        data=phase2,
        symbol="BENCHMARK",
        show_progress=False,
    )

    strategy = result2.strategy
    assert strategy is not None
    assert strategy.total_bars == 10
    assert strategy.by_symbol == {"AAA": 5, "BBB": 5}
    assert "on_resume" in strategy.events
    resume_idx = strategy.events.index("on_resume")
    assert strategy.events[resume_idx + 1] == "on_start"
    assert result2.metrics.initial_market_value == result1.metrics.end_market_value


class WarmStartEventIdempotencyStrategy(Strategy):
    """Strategy for warm-start event idempotency checks."""

    def __init__(self) -> None:
        """Initialize state and duplicate trackers."""
        self.bar_seen_by_symbol: dict[str, int] = {}
        self.trade_callback_total = 0
        self.trade_duplicate_count = 0
        self.order_callback_total = 0
        self.order_duplicate_count = 0
        self.trade_keys: set[tuple[str, int, str, str, float, float]] = set()
        self.order_keys: set[tuple[str, str, float]] = set()
        self.events: list[str] = []

    def on_resume(self) -> None:
        """Record resume callback."""
        self.events.append("on_resume")

    def on_start(self) -> None:
        """Record start callback."""
        self.events.append("on_start")

    def on_bar(self, bar: Bar) -> None:
        """Submit deterministic round-trip orders across two phases."""
        count = self.bar_seen_by_symbol.get(bar.symbol, 0) + 1
        self.bar_seen_by_symbol[bar.symbol] = count
        if count in (1, 3):
            self.buy(bar.symbol, 1)
        elif count in (2, 4):
            self.sell(bar.symbol, 1)

    def on_order(self, order: Any) -> None:
        """Track duplicate order callbacks for identical state transitions."""
        self.order_callback_total += 1
        key = (order.id, str(order.status), float(order.filled_quantity))
        if key in self.order_keys:
            self.order_duplicate_count += 1
        else:
            self.order_keys.add(key)

    def on_trade(self, trade: Any) -> None:
        """Track duplicate trade callbacks."""
        self.trade_callback_total += 1
        key = (
            trade.order_id,
            int(trade.timestamp),
            trade.symbol,
            str(trade.side),
            float(trade.quantity),
            float(trade.price),
        )
        if key in self.trade_keys:
            self.trade_duplicate_count += 1
        else:
            self.trade_keys.add(key)


def test_run_warm_start_multi_symbol_event_idempotency(tmp_path: Path) -> None:
    """Warm start should not duplicate order/trade callbacks."""
    checkpoint = tmp_path / "snapshot_event_idempotency.pkl"
    phase1 = {
        "AAA": _make_symbol_df("AAA", "2023-01-01", 2, 100.0),
        "BBB": _make_symbol_df("BBB", "2023-01-01", 2, 200.0),
    }
    phase2 = {
        "AAA": _make_symbol_df("AAA", "2023-01-03", 2, 102.0),
        "BBB": _make_symbol_df("BBB", "2023-01-03", 2, 202.0),
    }

    result1 = run_backtest(
        data=phase1,
        strategy=WarmStartEventIdempotencyStrategy,
        symbol="BENCHMARK",
        initial_cash=100000.0,
        execution_mode="current_close",
        show_progress=False,
    )
    save_snapshot(result1.engine, result1.strategy, str(checkpoint))  # type: ignore[arg-type]

    result2 = run_warm_start(
        checkpoint_path=str(checkpoint),
        data=phase2,
        symbol="BENCHMARK",
        show_progress=False,
    )

    strategy = result2.strategy
    assert strategy is not None
    assert strategy.bar_seen_by_symbol == {"AAA": 4, "BBB": 4}
    assert strategy.trade_callback_total > 0
    assert strategy.order_callback_total > 0
    assert strategy.trade_duplicate_count == 0
    assert strategy.order_duplicate_count == 0
    assert "on_resume" in strategy.events


class TimerIdempotencyStrategy(Strategy):
    """Strategy for timer registration idempotency tests."""

    def __init__(self) -> None:
        """Initialize counters."""
        self.timer_count = 0
        self.events: list[str] = []

    def on_resume(self) -> None:
        """Record resume callback."""
        self.events.append("on_resume")

    def on_start(self) -> None:
        """Register timers once."""
        self.events.append("on_start")
        self.schedule("2023-01-01 10:00:00", "manual_timer")
        self.add_daily_timer("14:55:00", "daily_timer")

    def on_timer(self, payload: str) -> None:
        """Count timer callbacks."""
        self.timer_count += 1
        self.events.append(f"on_timer:{payload}")


def test_timer_registration_not_duplicated_in_warm_start() -> None:
    """Internal start should not double-register timers when called repeatedly."""
    strategy = TimerIdempotencyStrategy()
    strategy._is_restored = True
    ctx = MagicMock(spec=StrategyContext)
    strategy.ctx = ctx
    strategy._trading_days = [
        pd.Timestamp("2023-01-01").tz_localize("Asia/Shanghai"),
        pd.Timestamp("2023-01-02").tz_localize("Asia/Shanghai"),
    ]

    strategy._on_start_internal()
    strategy._on_start_internal()

    calls = strategy.ctx.schedule.call_args_list
    assert len(calls) == 3
    payloads = [c.args[1] for c in calls]
    assert payloads.count("manual_timer") == 1
    assert payloads.count("__daily__|14:55:00|daily_timer") == 2


def test_daily_timer_payload_processed_once_per_event() -> None:
    """Daily wrapped payload should trigger one timer callback per event."""
    strategy = TimerIdempotencyStrategy()
    ctx = MagicMock(spec=StrategyContext)
    ctx.canceled_order_ids = []
    ctx.active_orders = []
    ctx.recent_trades = []
    strategy.ctx = ctx
    strategy._trading_days = [
        pd.Timestamp("2023-01-01").tz_localize("Asia/Shanghai"),
    ]

    strategy._on_timer_event("__daily__|14:55:00|daily_timer", ctx)
    assert strategy.timer_count == 1
    assert strategy.events[-1] == "on_timer:daily_timer"


def test_live_mode_timer_registration_not_duplicated() -> None:
    """Live mode timer registration should run once in internal start."""
    strategy = TimerIdempotencyStrategy()
    strategy._is_restored = True
    ctx = MagicMock(spec=StrategyContext)
    strategy.ctx = ctx
    strategy._trading_days = []

    strategy._on_start_internal()
    strategy._on_start_internal()

    calls = strategy.ctx.schedule.call_args_list
    assert len(calls) == 2
    payloads = [c.args[1] for c in calls]
    assert payloads.count("manual_timer") == 1
    assert payloads.count("__daily__|14:55:00|daily_timer") == 1


def test_live_mode_daily_timer_reschedules_once_per_trigger() -> None:
    """Live mode daily timer should reschedule once per single trigger."""
    strategy = TimerIdempotencyStrategy()
    ctx = MagicMock(spec=StrategyContext)
    ctx.canceled_order_ids = []
    ctx.active_orders = []
    ctx.recent_trades = []
    strategy.ctx = ctx
    strategy._trading_days = []

    strategy._on_timer_event("__daily__|14:55:00|daily_timer", ctx)

    assert strategy.timer_count == 1
    assert strategy.events[-1] == "on_timer:daily_timer"
    assert strategy.ctx.schedule.call_count == 1
    schedule_call = strategy.ctx.schedule.call_args
    assert schedule_call is not None
    assert isinstance(schedule_call.args[0], int)
    assert schedule_call.args[1] == "__daily__|14:55:00|daily_timer"


class TimerOrderTradeMixedStrategy(Strategy):
    """Strategy for mixed timer/order/trade event ordering tests."""

    def __init__(self) -> None:
        """Initialize counters."""
        self.order_count = 0
        self.trade_count = 0
        self.timer_count = 0
        self.events: list[str] = []

    def on_order(self, order: Any) -> None:
        """Record order callback."""
        self.order_count += 1
        self.events.append(f"on_order:{order.id}")

    def on_trade(self, trade: Any) -> None:
        """Record trade callback."""
        self.trade_count += 1
        self.events.append(f"on_trade:{trade.order_id}")

    def on_timer(self, payload: str) -> None:
        """Record timer callback."""
        self.timer_count += 1
        self.events.append(f"on_timer:{payload}")


def test_mixed_events_order_on_daily_timer_in_live_mode() -> None:
    """Daily timer should process order/trade first, then timer, and reschedule once."""
    strategy = TimerOrderTradeMixedStrategy()
    ctx = MagicMock(spec=StrategyContext)
    ctx.canceled_order_ids = []
    ctx.active_orders = [
        SimpleNamespace(id="o1", status="Submitted", filled_quantity=0.0)
    ]
    ctx.recent_trades = [SimpleNamespace(order_id="o1")]
    strategy.ctx = ctx
    strategy._trading_days = []

    strategy._on_timer_event("__daily__|14:55:00|mixed_timer", ctx)

    assert strategy.order_count == 1
    assert strategy.trade_count == 1
    assert strategy.timer_count == 1
    assert strategy.events == ["on_order:o1", "on_trade:o1", "on_timer:mixed_timer"]
    assert strategy.ctx.schedule.call_count == 1
    schedule_call = strategy.ctx.schedule.call_args
    assert schedule_call is not None
    assert schedule_call.args[1] == "__daily__|14:55:00|mixed_timer"


def test_mixed_events_partial_fill_then_cancel_sequence() -> None:
    """Partial fill and cancel should emit deterministic callbacks."""
    strategy = TimerOrderTradeMixedStrategy()
    ctx = MagicMock(spec=StrategyContext)
    ctx.canceled_order_ids = []
    ctx.active_orders = [
        SimpleNamespace(id="o2", status="Submitted", filled_quantity=0.0)
    ]
    ctx.recent_trades = []
    strategy.ctx = ctx
    strategy._trading_days = []

    strategy._on_timer_event("__daily__|14:55:00|mixed_timer2", ctx)

    ctx.canceled_order_ids = []
    ctx.active_orders = [
        SimpleNamespace(id="o2", status="Submitted", filled_quantity=1.0)
    ]
    ctx.recent_trades = [SimpleNamespace(order_id="o2")]
    strategy._on_timer_event("__daily__|14:55:00|mixed_timer2", ctx)

    ctx.canceled_order_ids = ["o2"]
    ctx.active_orders = []
    ctx.recent_trades = []
    strategy._on_timer_event("__daily__|14:55:00|mixed_timer2", ctx)

    assert strategy.order_count == 3
    assert strategy.trade_count == 1
    assert strategy.timer_count == 3
    assert strategy.events == [
        "on_order:o2",
        "on_timer:mixed_timer2",
        "on_order:o2",
        "on_trade:o2",
        "on_timer:mixed_timer2",
        "on_order:o2",
        "on_timer:mixed_timer2",
    ]
    assert strategy.ctx.schedule.call_count == 3


def test_daily_timer_malformed_payload_falls_back_to_raw_timer() -> None:
    """Malformed daily payload should fallback to raw timer callback."""
    strategy = TimerOrderTradeMixedStrategy()
    ctx = MagicMock(spec=StrategyContext)
    ctx.canceled_order_ids = []
    ctx.active_orders = []
    ctx.recent_trades = []
    strategy.ctx = ctx
    strategy._trading_days = []

    strategy._on_timer_event("__daily__|bad_payload", ctx)

    assert strategy.order_count == 0
    assert strategy.trade_count == 0
    assert strategy.timer_count == 1
    assert strategy.events == ["on_timer:__daily__|bad_payload"]
    assert strategy.ctx.schedule.call_count == 0


def test_daily_timer_invalid_time_fires_once_without_raw_fallback() -> None:
    """Invalid daily time should not duplicate timer callback."""
    strategy = TimerOrderTradeMixedStrategy()
    ctx = MagicMock(spec=StrategyContext)
    ctx.canceled_order_ids = []
    ctx.active_orders = []
    ctx.recent_trades = []
    strategy.ctx = ctx
    strategy._trading_days = []

    strategy._on_timer_event("__daily__|not_a_time|mixed_timer3", ctx)

    assert strategy.order_count == 0
    assert strategy.trade_count == 0
    assert strategy.timer_count == 1
    assert strategy.events == ["on_timer:mixed_timer3"]
    assert strategy.ctx.schedule.call_count == 0


def test_unknown_canceled_order_does_not_emit_order_callback() -> None:
    """Unknown canceled order id should not trigger on_order callback."""
    strategy = TimerOrderTradeMixedStrategy()
    ctx = MagicMock(spec=StrategyContext)
    ctx.canceled_order_ids = ["ghost_order"]
    ctx.active_orders = []
    ctx.recent_trades = []
    strategy.ctx = ctx
    strategy._trading_days = []

    strategy._on_timer_event("plain_timer", ctx)

    assert strategy.order_count == 0
    assert strategy.trade_count == 0
    assert strategy.timer_count == 1
    assert strategy.events == ["on_timer:plain_timer"]


class FrameworkHooksStrategy(Strategy):
    """Strategy for framework-level hooks tests."""

    def __init__(self) -> None:
        """Initialize records."""
        self.events: list[str] = []
        self.errors: list[tuple[str, str]] = []
        self.portfolio_updates = 0

    def on_session_start(self, session: Any, timestamp: int) -> None:
        """Record session start."""
        self.events.append(f"session_start:{session}:{timestamp}")

    def on_session_end(self, session: Any, timestamp: int) -> None:
        """Record session end."""
        self.events.append(f"session_end:{session}:{timestamp}")

    def before_trading(self, trading_date: Any, timestamp: int) -> None:
        """Record before trading hook."""
        self.events.append(f"before:{trading_date}:{timestamp}")

    def after_trading(self, trading_date: Any, timestamp: int) -> None:
        """Record after trading hook."""
        self.events.append(f"after:{trading_date}:{timestamp}")

    def on_portfolio_update(self, snapshot: dict[str, Any]) -> None:
        """Record portfolio update."""
        self.portfolio_updates += 1
        self.events.append(f"portfolio:{snapshot['cash']}:{snapshot['equity']}")

    def on_reject(self, order: Any) -> None:
        """Record reject callback."""
        self.events.append(f"reject:{order.id}")

    def on_order(self, order: Any) -> None:
        """Record order callback."""
        self.events.append(f"order:{order.id}")

    def on_tick(self, tick: Tick) -> None:
        """Record tick callback."""
        self.events.append("tick")

    def on_error(self, error: Exception, source: str, payload: Any = None) -> None:
        """Record error callback."""
        self.errors.append((source, type(error).__name__))

    def on_stop(self) -> None:
        """Record stop callback."""
        self.events.append("stop")


def test_framework_hooks_session_day_reject_and_portfolio() -> None:
    """Framework hooks should fire with expected transitions."""
    strategy = FrameworkHooksStrategy()
    ctx = MagicMock(spec=StrategyContext)
    ctx.get_position.return_value = 0.0
    ctx.canceled_order_ids = []
    ctx.recent_trades = []
    ctx.positions = {"AAPL": 1.0}
    ctx.available_positions = {"AAPL": 1.0}
    rejected = SimpleNamespace(
        id="rej1",
        status=OrderStatus.Rejected,
        filled_quantity=0.0,
        average_filled_price=None,
    )
    ctx.active_orders = [rejected]
    ctx.cash = 1000.0
    ctx.session = "normal"
    ctx.current_time = pd.Timestamp("2023-01-01 09:30:00", tz="Asia/Shanghai").value

    tick1 = Tick(timestamp=ctx.current_time, price=100.0, volume=1.0, symbol="AAPL")
    strategy._on_tick_event(tick1, ctx)

    assert any(e.startswith("session_start:") for e in strategy.events)
    assert any(e.startswith("before:") for e in strategy.events)
    assert "order:rej1" in strategy.events
    assert "reject:rej1" in strategy.events
    assert strategy.events.index("order:rej1") < strategy.events.index("reject:rej1")
    assert strategy.events.index("reject:rej1") < strategy.events.index("tick")
    assert strategy.portfolio_updates == 1

    ctx.current_time = pd.Timestamp("2023-01-01 15:10:00", tz="Asia/Shanghai").value
    ctx.session = "postmarket"
    tick2 = Tick(timestamp=ctx.current_time, price=101.0, volume=1.0, symbol="AAPL")
    strategy._on_tick_event(tick2, ctx)
    assert any(e.startswith("session_end:") for e in strategy.events)
    assert any(e.startswith("after:") for e in strategy.events)

    before_count = len([e for e in strategy.events if e.startswith("before:")])
    ctx.current_time = pd.Timestamp("2023-01-02 09:31:00", tz="Asia/Shanghai").value
    ctx.session = "normal"
    tick3 = Tick(timestamp=ctx.current_time, price=102.0, volume=1.0, symbol="AAPL")
    strategy._on_tick_event(tick3, ctx)
    after_count = len([e for e in strategy.events if e.startswith("before:")])
    assert after_count == before_count + 1


def test_portfolio_update_skips_clean_tick_without_changes() -> None:
    """Clean tick without price/position/order changes should not emit update."""
    strategy = FrameworkHooksStrategy()
    ctx = MagicMock(spec=StrategyContext)
    ctx.get_position.return_value = 0.0
    ctx.canceled_order_ids = []
    ctx.active_orders = []
    ctx.recent_trades = []
    ctx.positions = {}
    ctx.available_positions = {}
    ctx.cash = 1000.0
    ctx.session = "normal"
    ts1 = pd.Timestamp("2023-01-01 09:30:00", tz="Asia/Shanghai").value
    ts2 = pd.Timestamp("2023-01-01 09:30:01", tz="Asia/Shanghai").value
    tick1 = Tick(timestamp=ts1, price=100.0, volume=1.0, symbol="AAPL")
    tick2 = Tick(timestamp=ts2, price=100.0, volume=1.0, symbol="AAPL")

    ctx.current_time = ts1
    strategy._on_tick_event(tick1, ctx)
    assert strategy.portfolio_updates == 1

    ctx.current_time = ts2
    strategy._on_tick_event(tick2, ctx)
    assert strategy.portfolio_updates == 1


def test_portfolio_update_emits_on_price_change_with_position() -> None:
    """Price move with open position should emit portfolio update."""
    strategy = FrameworkHooksStrategy()
    ctx = MagicMock(spec=StrategyContext)
    ctx.get_position.return_value = 1.0
    ctx.canceled_order_ids = []
    ctx.active_orders = []
    ctx.recent_trades = []
    ctx.positions = {"AAPL": 1.0}
    ctx.available_positions = {"AAPL": 1.0}
    ctx.cash = 1000.0
    ctx.session = "normal"
    ts1 = pd.Timestamp("2023-01-01 09:30:00", tz="Asia/Shanghai").value
    ts2 = pd.Timestamp("2023-01-01 09:30:01", tz="Asia/Shanghai").value
    tick1 = Tick(timestamp=ts1, price=100.0, volume=1.0, symbol="AAPL")
    tick2 = Tick(timestamp=ts2, price=101.0, volume=1.0, symbol="AAPL")

    ctx.current_time = ts1
    strategy._on_tick_event(tick1, ctx)
    assert strategy.portfolio_updates == 1

    ctx.current_time = ts2
    strategy._on_tick_event(tick2, ctx)
    assert strategy.portfolio_updates == 2


def test_portfolio_update_respects_eps_threshold() -> None:
    """Small equity changes under eps should not emit updates."""
    strategy = FrameworkHooksStrategy()
    strategy.portfolio_update_eps = 5.0
    ctx = MagicMock(spec=StrategyContext)
    ctx.get_position.return_value = 1.0
    ctx.canceled_order_ids = []
    ctx.active_orders = []
    ctx.recent_trades = []
    ctx.positions = {"AAPL": 1.0}
    ctx.available_positions = {"AAPL": 1.0}
    ctx.cash = 1000.0
    ctx.session = "normal"
    ts1 = pd.Timestamp("2023-01-01 09:30:00", tz="Asia/Shanghai").value
    ts2 = pd.Timestamp("2023-01-01 09:30:01", tz="Asia/Shanghai").value
    tick1 = Tick(timestamp=ts1, price=100.0, volume=1.0, symbol="AAPL")
    tick2 = Tick(timestamp=ts2, price=101.0, volume=1.0, symbol="AAPL")

    ctx.current_time = ts1
    strategy._on_tick_event(tick1, ctx)
    assert strategy.portfolio_updates == 1

    ctx.current_time = ts2
    strategy._on_tick_event(tick2, ctx)
    assert strategy.portfolio_updates == 1


class ErrorHookStrategy(Strategy):
    """Strategy for on_error hook tests."""

    def __init__(self) -> None:
        """Initialize captured errors."""
        self.captured: list[tuple[str, str]] = []

    def on_tick(self, tick: Tick) -> None:
        """Raise an exception for testing."""
        raise ValueError("boom")

    def on_error(self, error: Exception, source: str, payload: Any = None) -> None:
        """Capture on_error callback."""
        self.captured.append((source, str(error)))


class RuntimeConfigBarErrorStrategy(Strategy):
    """Strategy for runtime config injection test via run_backtest."""

    def __init__(self) -> None:
        """Initialize error counter."""
        self.errors: list[str] = []

    def on_bar(self, bar: Bar) -> None:
        """Raise error on each bar."""
        raise ValueError("bar_boom")

    def on_error(self, error: Exception, source: str, payload: Any = None) -> None:
        """Record callback source."""
        self.errors.append(source)


class RuntimeConfigConflictStrategy(Strategy):
    """Strategy for runtime config conflict behavior tests."""

    def __init__(self) -> None:
        """Initialize with strict default config."""
        self.errors: list[str] = []
        self.runtime_config = StrategyRuntimeConfig(error_mode="raise")

    def on_bar(self, bar: Bar) -> None:
        """Raise on every bar."""
        raise ValueError("conflict_boom")

    def on_error(self, error: Exception, source: str, payload: Any = None) -> None:
        """Record callback source."""
        self.errors.append(source)


def test_runtime_config_validation_rejects_invalid_values() -> None:
    """Runtime config should validate mode and eps."""
    with pytest.raises(ValueError, match="portfolio_update_eps"):
        StrategyRuntimeConfig(portfolio_update_eps=-1)
    with pytest.raises(ValueError, match="error_mode"):
        StrategyRuntimeConfig(error_mode=cast(Any, "bad"))


def test_runtime_alias_properties_sync_to_runtime_config() -> None:
    """Legacy alias fields should update runtime_config."""
    strategy = ErrorHookStrategy()
    strategy.enable_precise_day_boundary_hooks = True
    strategy.portfolio_update_eps = 1.5
    strategy.error_mode = "continue"
    strategy.re_raise_on_error = False

    cfg = strategy.runtime_config
    assert cfg.enable_precise_day_boundary_hooks is True
    assert cfg.portfolio_update_eps == 1.5
    assert cfg.error_mode == "continue"
    assert cfg.re_raise_on_error is False


def test_runtime_config_assignment_syncs_alias_properties() -> None:
    """runtime_config assignment should reflect on alias property getters."""
    strategy = ErrorHookStrategy()
    strategy.runtime_config = StrategyRuntimeConfig(
        enable_precise_day_boundary_hooks=True,
        portfolio_update_eps=2.0,
        error_mode="legacy",
        re_raise_on_error=False,
    )

    assert strategy.enable_precise_day_boundary_hooks is True
    assert strategy.portfolio_update_eps == 2.0
    assert strategy.error_mode == "legacy"
    assert strategy.re_raise_on_error is False


def test_on_error_hook_called_and_exception_re_raised() -> None:
    """Errors in user callback should call on_error then re-raise."""
    strategy = ErrorHookStrategy()
    ctx = MagicMock(spec=StrategyContext)
    ctx.canceled_order_ids = []
    ctx.active_orders = []
    ctx.recent_trades = []
    ctx.cash = 1000.0
    ctx.positions = {}
    ctx.available_positions = {}
    ctx.session = "normal"
    ctx.current_time = pd.Timestamp("2023-01-01 09:30:00", tz="Asia/Shanghai").value

    tick = Tick(timestamp=ctx.current_time, price=100.0, volume=1.0, symbol="AAPL")
    with pytest.raises(ValueError, match="boom"):
        strategy._on_tick_event(tick, ctx)

    assert strategy.captured == [("on_tick", "boom")]


def test_on_error_hook_can_swallow_user_callback_exception() -> None:
    """Errors can be swallowed when re_raise_on_error is disabled."""
    strategy = ErrorHookStrategy()
    strategy.error_mode = "legacy"
    strategy.re_raise_on_error = False
    ctx = MagicMock(spec=StrategyContext)
    ctx.canceled_order_ids = []
    ctx.active_orders = []
    ctx.recent_trades = []
    ctx.cash = 1000.0
    ctx.positions = {}
    ctx.available_positions = {}
    ctx.session = "normal"
    ctx.current_time = pd.Timestamp("2023-01-01 09:30:00", tz="Asia/Shanghai").value

    tick = Tick(timestamp=ctx.current_time, price=100.0, volume=1.0, symbol="AAPL")
    strategy._on_tick_event(tick, ctx)

    assert strategy.captured == [("on_tick", "boom")]


def test_error_mode_continue_overrides_re_raise_flag() -> None:
    """error_mode=continue should swallow even when re_raise_on_error=True."""
    strategy = ErrorHookStrategy()
    strategy.error_mode = "continue"
    strategy.re_raise_on_error = True
    ctx = MagicMock(spec=StrategyContext)
    ctx.canceled_order_ids = []
    ctx.active_orders = []
    ctx.recent_trades = []
    ctx.cash = 1000.0
    ctx.positions = {}
    ctx.available_positions = {}
    ctx.session = "normal"
    ctx.current_time = pd.Timestamp("2023-01-01 09:30:00", tz="Asia/Shanghai").value

    tick = Tick(timestamp=ctx.current_time, price=100.0, volume=1.0, symbol="AAPL")
    strategy._on_tick_event(tick, ctx)

    assert strategy.captured == [("on_tick", "boom")]


def test_error_mode_raise_overrides_re_raise_flag() -> None:
    """error_mode=raise should re-raise even when re_raise_on_error=False."""
    strategy = ErrorHookStrategy()
    strategy.error_mode = "raise"
    strategy.re_raise_on_error = False
    ctx = MagicMock(spec=StrategyContext)
    ctx.canceled_order_ids = []
    ctx.active_orders = []
    ctx.recent_trades = []
    ctx.cash = 1000.0
    ctx.positions = {}
    ctx.available_positions = {}
    ctx.session = "normal"
    ctx.current_time = pd.Timestamp("2023-01-01 09:30:00", tz="Asia/Shanghai").value

    tick = Tick(timestamp=ctx.current_time, price=100.0, volume=1.0, symbol="AAPL")
    with pytest.raises(ValueError, match="boom"):
        strategy._on_tick_event(tick, ctx)

    assert strategy.captured == [("on_tick", "boom")]


def test_runtime_config_continue_mode_swallow_exception() -> None:
    """runtime_config should drive error handling when legacy fields stay default."""
    strategy = ErrorHookStrategy()
    strategy.runtime_config = StrategyRuntimeConfig(error_mode="continue")
    ctx = MagicMock(spec=StrategyContext)
    ctx.canceled_order_ids = []
    ctx.active_orders = []
    ctx.recent_trades = []
    ctx.cash = 1000.0
    ctx.positions = {}
    ctx.available_positions = {}
    ctx.session = "normal"
    ctx.current_time = pd.Timestamp("2023-01-01 09:30:00", tz="Asia/Shanghai").value

    tick = Tick(timestamp=ctx.current_time, price=100.0, volume=1.0, symbol="AAPL")
    strategy._on_tick_event(tick, ctx)

    assert strategy.captured == [("on_tick", "boom")]


def test_legacy_error_mode_overrides_runtime_config() -> None:
    """Legacy fields should override runtime_config for compatibility."""
    strategy = ErrorHookStrategy()
    strategy.runtime_config = StrategyRuntimeConfig(error_mode="raise")
    strategy.error_mode = "continue"
    ctx = MagicMock(spec=StrategyContext)
    ctx.canceled_order_ids = []
    ctx.active_orders = []
    ctx.recent_trades = []
    ctx.cash = 1000.0
    ctx.positions = {}
    ctx.available_positions = {}
    ctx.session = "normal"
    ctx.current_time = pd.Timestamp("2023-01-01 09:30:00", tz="Asia/Shanghai").value

    tick = Tick(timestamp=ctx.current_time, price=100.0, volume=1.0, symbol="AAPL")
    strategy._on_tick_event(tick, ctx)

    assert strategy.captured == [("on_tick", "boom")]


def test_run_backtest_accepts_strategy_runtime_config() -> None:
    """run_backtest should inject runtime config into strategy instance."""
    bars = _make_bars("2023-01-01", 3, symbol="TEST")
    result = run_backtest(
        data=bars,
        strategy=RuntimeConfigBarErrorStrategy,
        symbol="TEST",
        show_progress=False,
        strategy_runtime_config={"error_mode": "continue"},
    )

    strategy = result.strategy
    assert strategy is not None
    assert strategy.errors == ["on_bar", "on_bar", "on_bar"]


def test_run_backtest_rejects_invalid_strategy_runtime_config_type() -> None:
    """Invalid runtime config type should fail fast."""
    bars = _make_bars("2023-01-01", 1, symbol="TEST")
    with pytest.raises(TypeError, match="strategy_runtime_config"):
        run_backtest(
            data=bars,
            strategy=RuntimeConfigBarErrorStrategy,
            symbol="TEST",
            show_progress=False,
            strategy_runtime_config=cast(Any, "invalid"),
        )


def test_run_backtest_rejects_invalid_runtime_config_from_strategy_params() -> None:
    """strategy_params path should validate runtime config strictly."""
    bars = _make_bars("2023-01-01", 1, symbol="TEST")
    with pytest.raises(TypeError, match="strategy_runtime_config"):
        run_backtest(
            data=bars,
            strategy=RuntimeConfigBarErrorStrategy,
            symbol="TEST",
            show_progress=False,
            strategy_params={"strategy_runtime_config": "invalid"},
        )


def test_run_backtest_explicit_runtime_config_has_higher_priority_than_kwargs() -> None:
    """Explicit backtest runtime config should override forwarded values."""
    bars = _make_bars("2023-01-01", 2, symbol="TEST")
    result = run_backtest(
        data=bars,
        strategy=RuntimeConfigBarErrorStrategy,
        symbol="TEST",
        show_progress=False,
        strategy_runtime_config={"error_mode": "continue"},
        strategy_params={"strategy_runtime_config": {"error_mode": "raise"}},
    )

    strategy = result.strategy
    assert strategy is not None
    assert strategy.errors == ["on_bar", "on_bar"]


def test_run_backtest_rejects_unknown_strategy_runtime_config_fields() -> None:
    """Unknown runtime config fields should produce field-level error."""
    bars = _make_bars("2023-01-01", 1, symbol="TEST")
    with pytest.raises(ValueError, match="unknown fields: unknown_flag"):
        run_backtest(
            data=bars,
            strategy=RuntimeConfigBarErrorStrategy,
            symbol="TEST",
            show_progress=False,
            strategy_runtime_config=cast(Any, {"unknown_flag": True}),
        )


def test_run_backtest_rejects_invalid_strategy_runtime_config_values() -> None:
    """Invalid runtime config values should produce wrapped validation error."""
    bars = _make_bars("2023-01-01", 1, symbol="TEST")
    with pytest.raises(ValueError, match="invalid strategy_runtime_config"):
        run_backtest(
            data=bars,
            strategy=RuntimeConfigBarErrorStrategy,
            symbol="TEST",
            show_progress=False,
            strategy_runtime_config={"portfolio_update_eps": -1},
        )


def test_run_backtest_runtime_config_override_true_by_default(
    caplog: Any,
) -> None:
    """run_backtest should override strategy runtime config by default."""
    bars = _make_bars("2023-01-01", 2, symbol="TEST")
    with caplog.at_level(logging.WARNING, logger="akquant"):
        result = run_backtest(
            data=bars,
            strategy=RuntimeConfigConflictStrategy,
            symbol="TEST",
            show_progress=False,
            strategy_runtime_config={"error_mode": "continue"},
        )

    strategy = result.strategy
    assert strategy is not None
    assert strategy.errors == ["on_bar", "on_bar"]
    assert "overrides strategy runtime_config" in caplog.text


def test_runtime_config_conflict_warning_deduplicated_per_strategy_instance(
    caplog: Any,
) -> None:
    """Conflict warning should be emitted once for same strategy instance."""
    strategy = RuntimeConfigConflictStrategy()
    bars = _make_bars("2023-01-01", 1, symbol="TEST")
    with caplog.at_level(logging.WARNING, logger="akquant"):
        run_backtest(
            data=bars,
            strategy=strategy,
            symbol="TEST",
            show_progress=False,
            strategy_runtime_config={"error_mode": "continue"},
        )
        run_backtest(
            data=bars,
            strategy=strategy,
            symbol="TEST",
            show_progress=False,
            strategy_runtime_config={"error_mode": "continue"},
        )

    logs = caplog.text
    assert logs.count("overrides strategy runtime_config") == 1
    assert strategy.errors == ["on_bar", "on_bar"]


def test_run_backtest_runtime_config_override_false_keeps_strategy_config(
    caplog: Any,
) -> None:
    """runtime_config_override=False should keep strategy-side config."""
    bars = _make_bars("2023-01-01", 1, symbol="TEST")
    with caplog.at_level(logging.WARNING, logger="akquant"):
        with pytest.raises(ValueError, match="conflict_boom"):
            run_backtest(
                data=bars,
                strategy=RuntimeConfigConflictStrategy,
                symbol="TEST",
                show_progress=False,
                strategy_runtime_config={"error_mode": "continue"},
                runtime_config_override=False,
            )

    assert "runtime_config_override=False" in caplog.text


def test_stop_internal_flushes_session_and_after_trading_hooks() -> None:
    """Stop phase should flush session_end and after_trading when pending."""
    strategy = FrameworkHooksStrategy()
    ctx = MagicMock(spec=StrategyContext)
    ctx.get_position.return_value = 0.0
    ctx.canceled_order_ids = []
    ctx.active_orders = []
    ctx.recent_trades = []
    ctx.cash = 1000.0
    ctx.positions = {}
    ctx.available_positions = {}
    ctx.session = "normal"
    ctx.current_time = pd.Timestamp("2023-01-01 10:00:00", tz="Asia/Shanghai").value

    tick = Tick(timestamp=ctx.current_time, price=100.0, volume=1.0, symbol="AAPL")
    strategy._on_tick_event(tick, ctx)
    assert any(e.startswith("before:") for e in strategy.events)
    assert not any(e.startswith("after:") for e in strategy.events)
    assert not any(e.startswith("session_end:") for e in strategy.events)

    strategy._on_stop_internal()

    assert any(e.startswith("after:") for e in strategy.events)
    assert any(e.startswith("session_end:") for e in strategy.events)
    assert strategy.events[-1] == "stop"


def test_boundary_timers_register_and_drive_day_hooks() -> None:
    """Boundary timers should register once and trigger day hooks precisely."""
    strategy = FrameworkHooksStrategy()
    strategy.enable_precise_day_boundary_hooks = True
    start_ts = pd.Timestamp("2023-01-03 09:30:00", tz="Asia/Shanghai").value
    end_ts = pd.Timestamp("2023-01-03 15:00:00", tz="Asia/Shanghai").value
    strategy._trading_day_bounds = {"2023-01-03": (start_ts, end_ts)}

    ctx = MagicMock(spec=StrategyContext)
    ctx.get_position.return_value = 0.0
    ctx.canceled_order_ids = []
    ctx.active_orders = []
    ctx.recent_trades = []
    ctx.cash = 1000.0
    ctx.positions = {}
    ctx.available_positions = {}
    ctx.session = "closed"
    ctx.current_time = start_ts

    tick = Tick(timestamp=start_ts, price=100.0, volume=1.0, symbol="AAPL")
    strategy._on_tick_event(tick, ctx)

    scheduled = [call.args for call in ctx.schedule.call_args_list]
    assert (start_ts, "__framework_boundary__|before|2023-01-03") in scheduled
    assert (end_ts + 1, "__framework_boundary__|after|2023-01-03") in scheduled

    strategy._on_timer_event("__framework_boundary__|before|2023-01-03", ctx)
    assert any(e.startswith("before:2023-01-03") for e in strategy.events)

    ctx.current_time = end_ts + 1
    strategy._on_timer_event("__framework_boundary__|after|2023-01-03", ctx)
    assert any(e.startswith("after:2023-01-03") for e in strategy.events)


@pytest.mark.parametrize(
    ("payload", "expected_event", "expected_schedule_calls"),
    [
        ("__daily__|14:55:00|daily_ok", "on_timer:daily_ok", 1),
        ("__daily__|bad_payload", "on_timer:__daily__|bad_payload", 0),
        ("__daily__|not_a_time|daily_bad_time", "on_timer:daily_bad_time", 0),
    ],
)
def test_daily_timer_paths_parameterized(
    payload: str, expected_event: str, expected_schedule_calls: int
) -> None:
    """Daily timer paths should produce stable callback and reschedule behavior."""
    strategy = TimerOrderTradeMixedStrategy()
    ctx = MagicMock(spec=StrategyContext)
    ctx.canceled_order_ids = []
    ctx.active_orders = []
    ctx.recent_trades = []
    strategy.ctx = ctx
    strategy._trading_days = []

    strategy._on_timer_event(payload, ctx)

    assert strategy.order_count == 0
    assert strategy.trade_count == 0
    assert strategy.timer_count == 1
    assert strategy.events == [expected_event]
    assert strategy.ctx.schedule.call_count == expected_schedule_calls
