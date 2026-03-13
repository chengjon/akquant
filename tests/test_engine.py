import time
from datetime import datetime, timezone
from typing import Any, cast

import akquant
import numpy as np
import pandas as pd
import pytest


def test_engine_initialization() -> None:
    """Test Engine initialization defaults."""
    engine = akquant.Engine()
    assert engine.portfolio.cash == 100000.0
    assert len(engine.trades) == 0
    assert len(engine.orders) == 0


class DummyStrategy(akquant.Strategy):
    """A dummy strategy for testing purposes."""


class RegressionStrategy(akquant.Strategy):
    """Regression strategy for baseline checks."""

    def __init__(self) -> None:
        """Initialize the regression strategy."""
        super().__init__()
        self.bar_index = 0

    def on_bar(self, bar: akquant.Bar) -> None:
        """Handle bar events for deterministic trades."""
        if self.bar_index == 0:
            self.buy(symbol=bar.symbol, quantity=10)
        elif self.bar_index == 2:
            self.sell(symbol=bar.symbol, quantity=10)
        self.bar_index += 1


class NoopStrategy(akquant.Strategy):
    """No-op strategy used for performance baselines."""

    def on_bar(self, bar: akquant.Bar) -> None:
        """Handle bar events without generating orders."""
        return


class SingleBuyStrategy(akquant.Strategy):
    """Place a single buy order on first bar only."""

    def __init__(self) -> None:
        """Initialize one-shot state."""
        super().__init__()
        self._submitted = False

    def on_bar(self, bar: akquant.Bar) -> None:
        """Submit first-bar buy only once."""
        if self._submitted:
            return
        self.buy(symbol=bar.symbol, quantity=10)
        self._submitted = True


class DualBuyStrategy(akquant.Strategy):
    """Place two buy orders on first two bars."""

    def __init__(self) -> None:
        """Initialize counter state."""
        super().__init__()
        self._step = 0

    def on_bar(self, bar: akquant.Bar) -> None:
        """Submit a buy order on first two bars."""
        if self._step < 2:
            self.buy(symbol=bar.symbol, quantity=10)
        self._step += 1


class BuyBuySellBuyStrategy(akquant.Strategy):
    """Buy, buy, sell, then buy for reduce-only transition checks."""

    def __init__(self) -> None:
        """Initialize step counter."""
        super().__init__()
        self._step = 0

    def on_bar(self, bar: akquant.Bar) -> None:
        """Submit deterministic sequence for reduce-only verification."""
        if self._step == 0:
            self.buy(symbol=bar.symbol, quantity=10)
        elif self._step == 1:
            self.buy(symbol=bar.symbol, quantity=10)
        elif self._step == 2:
            self.sell(symbol=bar.symbol, quantity=5)
        elif self._step == 3:
            self.buy(symbol=bar.symbol, quantity=5)
        self._step += 1


class ContinuousBuyStrategy(akquant.Strategy):
    """Submit a buy order on every bar."""

    def on_bar(self, bar: akquant.Bar) -> None:
        """Submit deterministic repeated buy orders."""
        self.buy(symbol=bar.symbol, quantity=10)


class ContinuousSmallBuyStrategy(akquant.Strategy):
    """Submit a small buy order on every bar."""

    def on_bar(self, bar: akquant.Bar) -> None:
        """Submit deterministic repeated small buy orders."""
        self.buy(symbol=bar.symbol, quantity=5)


def _ns(dt: datetime) -> int:
    """
    Convert a datetime to nanoseconds since epoch.

    :param dt: Datetime object.
    :return: Nanoseconds since epoch.
    """
    return int(dt.timestamp() * 1e9)


def _build_regression_bars(symbol: str) -> list[akquant.Bar]:
    """
    Build a deterministic 3-bar series for regression verification.

    :param symbol: Symbol for bars.
    :return: List of Bar objects.
    """
    day1 = _ns(datetime(2023, 1, 2, 15, 0, tzinfo=timezone.utc))
    day2 = _ns(datetime(2023, 1, 3, 15, 0, tzinfo=timezone.utc))
    day3 = _ns(datetime(2023, 1, 4, 15, 0, tzinfo=timezone.utc))
    return [
        akquant.Bar(day1, 10.0, 10.0, 10.0, 10.0, 1000.0, symbol),
        akquant.Bar(day2, 12.0, 12.0, 12.0, 12.0, 1000.0, symbol),
        akquant.Bar(day3, 11.0, 11.0, 11.0, 11.0, 1000.0, symbol),
    ]


def _build_daily_loss_bars(symbol: str) -> list[akquant.Bar]:
    """Build bars where the second bar marks down unrealized PnL."""
    day1 = _ns(datetime(2023, 1, 2, 15, 0, tzinfo=timezone.utc))
    day2 = _ns(datetime(2023, 1, 3, 15, 0, tzinfo=timezone.utc))
    day3 = _ns(datetime(2023, 1, 4, 15, 0, tzinfo=timezone.utc))
    return [
        akquant.Bar(day1, 10.0, 10.0, 10.0, 10.0, 1000.0, symbol),
        akquant.Bar(day2, 8.0, 8.0, 8.0, 8.0, 1000.0, symbol),
        akquant.Bar(day3, 8.0, 8.0, 8.0, 8.0, 1000.0, symbol),
    ]


def _build_reduce_only_bars(symbol: str) -> list[akquant.Bar]:
    """Build 4 bars used to validate reduce-only fallback behavior."""
    day1 = _ns(datetime(2023, 1, 2, 15, 0, tzinfo=timezone.utc))
    day2 = _ns(datetime(2023, 1, 3, 15, 0, tzinfo=timezone.utc))
    day3 = _ns(datetime(2023, 1, 4, 15, 0, tzinfo=timezone.utc))
    day4 = _ns(datetime(2023, 1, 5, 15, 0, tzinfo=timezone.utc))
    return [
        akquant.Bar(day1, 10.0, 10.0, 10.0, 10.0, 1000.0, symbol),
        akquant.Bar(day2, 8.0, 8.0, 8.0, 8.0, 1000.0, symbol),
        akquant.Bar(day3, 8.0, 8.0, 8.0, 8.0, 1000.0, symbol),
        akquant.Bar(day4, 8.0, 8.0, 8.0, 8.0, 1000.0, symbol),
    ]


def _build_benchmark_data(n: int, symbol: str) -> pd.DataFrame:
    """
    Build a synthetic minute-level dataset for throughput tests.

    :param n: Number of rows.
    :param symbol: Symbol name.
    :return: DataFrame with OHLCV and symbol columns.
    """
    rng = np.random.default_rng(7)
    dates = pd.date_range("2020-01-01", periods=n, freq="min", tz="UTC")
    returns = rng.normal(0, 0.001, n)
    price = 100 * np.exp(np.cumsum(returns))
    return pd.DataFrame(
        {
            "timestamp": dates,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": np.full(n, 1000.0),
            "symbol": symbol,
        }
    )


def test_run_backtest_accepts_data_feed_adapter() -> None:
    """run_backtest should accept objects implementing DataFeedAdapter.load."""

    class InMemoryAdapter:
        """Simple in-memory adapter for testing."""

        name = "memory"

        def __init__(self, frame: pd.DataFrame) -> None:
            """Store source frame."""
            self.frame = frame
            self.requested_symbols: list[str] = []

        def load(self, request: Any) -> pd.DataFrame:
            """Return filtered frame for requested symbol."""
            self.requested_symbols.append(str(request.symbol))
            data = self.frame[self.frame["symbol"] == str(request.symbol)].copy()
            if request.start_time is not None:
                data = data[data["timestamp"] >= request.start_time]
            if request.end_time is not None:
                data = data[data["timestamp"] <= request.end_time]
            return cast(pd.DataFrame, data)

    symbol = "ADAPTER"
    data = _build_benchmark_data(10, symbol)
    adapter = InMemoryAdapter(data)

    result = akquant.run_backtest(
        data=adapter,
        strategy=SingleBuyStrategy,
        symbol=symbol,
        execution_mode="current_close",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        lot_size=1,
        show_progress=False,
    )

    assert adapter.requested_symbols == [symbol]
    assert not result.orders_df.empty
    assert set(result.orders_df["symbol"].astype(str)) == {symbol}


def test_run_backtest_dataframe_multisymbol_preserves_bar_symbol() -> None:
    """Keep bar.symbol aligned with per-row symbol values in DataFrame mode."""

    class CollectSymbolsStrategy(akquant.Strategy):
        """Collect symbols observed in on_bar callbacks."""

        def __init__(self) -> None:
            """Initialize the collected symbol container."""
            super().__init__()
            self.seen_symbols: list[str] = []

        def on_bar(self, bar: akquant.Bar) -> None:
            """Record callback symbol for later assertions."""
            self.seen_symbols.append(str(bar.symbol))

    rows = [
        {
            "timestamp": "2024-01-02",
            "symbol": "IF2401.CFX",
            "open": 10.0,
            "high": 11.0,
            "low": 9.0,
            "close": 10.5,
            "volume": 1000.0,
        },
        {
            "timestamp": "2024-01-02",
            "symbol": "IF2402.CFX",
            "open": 20.0,
            "high": 21.0,
            "low": 19.0,
            "close": 20.5,
            "volume": 1000.0,
        },
        {
            "timestamp": "2024-01-03",
            "symbol": "IF2401.CFX",
            "open": 11.0,
            "high": 12.0,
            "low": 10.0,
            "close": 11.5,
            "volume": 1000.0,
        },
        {
            "timestamp": "2024-01-03",
            "symbol": "IF2402.CFX",
            "open": 21.0,
            "high": 22.0,
            "low": 20.0,
            "close": 21.5,
            "volume": 1000.0,
        },
    ]
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp")

    result = akquant.run_backtest(
        data=df,
        strategy=CollectSymbolsStrategy,
        symbol=["IF2401.CFX", "IF2402.CFX"],
        start_time="2024-01-02",
        end_time="2024-01-03",
        execution_mode="current_close",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        lot_size=1,
        show_progress=False,
    )

    strategy = cast(CollectSymbolsStrategy, result.strategy)
    assert len(strategy.seen_symbols) == len(df)
    assert set(strategy.seen_symbols) == {"IF2401.CFX", "IF2402.CFX"}
    assert strategy.seen_symbols.count("IF2401.CFX") == 2
    assert strategy.seen_symbols.count("IF2402.CFX") == 2


def test_engine_run_empty() -> None:
    """Test running engine with no data."""
    engine = akquant.Engine()
    strategy = DummyStrategy()
    engine.run(strategy, show_progress=False)
    result = engine.get_results()

    # Result should indicate no trades, 0 return
    # result.metrics.total_return ? Or result.total_return?
    # BacktestResult has 'metrics' and 'trade_metrics' fields.
    assert result.trade_metrics.total_closed_trades == 0
    assert abs(result.metrics.total_return - 0.0) < 1e-9


def test_engine_set_cash() -> None:
    """Test setting initial cash."""
    engine = akquant.Engine()
    engine.set_cash(50000.0)
    assert engine.portfolio.cash == 50000.0


def test_engine_single_strategy_slot_defaults_and_update() -> None:
    """Engine should keep single-slot metadata consistent in phase 1."""
    engine = akquant.Engine()
    if not hasattr(engine, "get_strategy_slot_ids"):
        pytest.skip("Engine binary does not expose slot metadata methods")
    slot_ids = cast(list[str], cast(Any, engine).get_strategy_slot_ids())
    assert slot_ids == ["_default"]
    assert cast(int, cast(Any, engine).get_active_strategy_slot()) == 0

    cast(Any, engine).set_default_strategy_id("alpha_slot")
    updated_slot_ids = cast(list[str], cast(Any, engine).get_strategy_slot_ids())
    assert updated_slot_ids == ["alpha_slot"]
    assert cast(str, cast(Any, engine).get_default_strategy_id()) == "alpha_slot"


def test_engine_strategy_slot_configuration_api() -> None:
    """Engine should support configuring multi-slot metadata."""
    engine = akquant.Engine()
    if not hasattr(engine, "set_strategy_slots"):
        pytest.skip("Engine binary does not expose slot configuration methods")

    cast(Any, engine).set_strategy_slots(["alpha", "beta"])
    slot_ids = cast(list[str], cast(Any, engine).get_strategy_slot_ids())
    assert slot_ids == ["alpha", "beta"]
    assert cast(str, cast(Any, engine).get_default_strategy_id()) == "alpha"


def test_engine_run_with_configured_slot_strategy() -> None:
    """Engine should run when secondary slot strategy is configured."""
    engine = akquant.Engine()
    if not hasattr(engine, "set_strategy_for_slot"):
        pytest.skip("Engine binary does not expose slot strategy methods")

    symbol = "SLOT_RUN"
    engine.use_simple_market(0.0)
    engine.set_force_session_continuous(True)
    engine.set_execution_mode(akquant.ExecutionMode.CurrentClose)
    engine.set_cash(100000.0)
    engine.set_stock_fee_rules(0.0, 0.0, 0.0, 0.0)

    instr = akquant.Instrument(
        symbol=symbol,
        asset_type=akquant.AssetType.Stock,
        multiplier=1.0,
        margin_ratio=1.0,
        tick_size=0.01,
        lot_size=1.0,
    )
    engine.add_instrument(instr)
    engine.add_bars(_build_regression_bars(symbol))

    cast(Any, engine).set_strategy_slots(["slot_0", "slot_1"])
    cast(Any, engine).set_strategy_for_slot(1, NoopStrategy())
    engine.run(NoopStrategy(), show_progress=False)
    result = engine.get_results()
    assert result.metrics.initial_market_value == pytest.approx(100000.0, rel=1e-9)


def test_backtest_regression_baseline() -> None:
    """Verify baseline equity curve and trade sequence."""
    symbol = "REGRESS"
    engine = akquant.Engine()
    engine.use_simple_market(0.0)
    engine.set_force_session_continuous(True)
    engine.set_execution_mode(akquant.ExecutionMode.CurrentClose)
    engine.set_cash(100000.0)
    engine.set_stock_fee_rules(0.0, 0.0, 0.0, 0.0)
    engine.set_t_plus_one(False)

    instr = akquant.Instrument(
        symbol=symbol,
        asset_type=akquant.AssetType.Stock,
        multiplier=1.0,
        margin_ratio=1.0,
        tick_size=0.01,
        option_type=None,
        strike_price=None,
        expiry_date=None,
        lot_size=1.0,
    )
    engine.add_instrument(instr)

    bars = _build_regression_bars(symbol)
    engine.add_bars(bars)

    strategy = RegressionStrategy()
    engine.run(strategy, show_progress=False)
    result = engine.get_results()

    day1 = bars[0].timestamp
    day2 = bars[1].timestamp
    day3 = bars[2].timestamp
    expected_equity = [
        (day1, 100000.0),
        (day2, 100020.0),
        (day3, 100010.0),
    ]
    assert len(result.equity_curve) == len(expected_equity)
    for (ts, val), (exp_ts, exp_val) in zip(result.equity_curve, expected_equity):
        assert ts == exp_ts
        assert val == pytest.approx(exp_val, rel=1e-9)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.symbol == symbol
    assert trade.entry_time == day1
    assert trade.exit_time == day3
    assert trade.entry_price == pytest.approx(10.0, rel=1e-9)
    assert trade.exit_price == pytest.approx(11.0, rel=1e-9)
    assert trade.quantity == pytest.approx(10.0, rel=1e-9)
    assert trade.side == "Long"
    assert trade.pnl == pytest.approx(10.0, rel=1e-9)
    assert trade.net_pnl == pytest.approx(10.0, rel=1e-9)
    assert trade.return_pct == pytest.approx(10.0, rel=1e-9)
    assert trade.commission == pytest.approx(0.0, rel=1e-9)
    assert trade.duration_bars == 2


def test_backtest_performance_baseline() -> None:
    """Verify minimum throughput for a no-op strategy."""
    data = _build_benchmark_data(n=3000, symbol="PERF")
    t0 = time.perf_counter()
    result = akquant.run_backtest(
        data=data,
        strategy=NoopStrategy,
        symbol="PERF",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
    )
    duration = time.perf_counter() - t0
    throughput = len(data) / duration if duration > 0 else 0.0
    assert throughput >= 200.0
    assert result.metrics.initial_market_value == pytest.approx(100000.0, rel=1e-9)


def test_run_backtest_on_event_emits_ordered_events() -> None:
    """Stream API should emit ordered lifecycle events."""
    data = _build_benchmark_data(n=20, symbol="STREAM")
    events: list[akquant.BacktestStreamEvent] = []

    def on_event(event: akquant.BacktestStreamEvent) -> None:
        events.append(event)

    result = akquant.run_backtest(
        data=data,
        strategy=NoopStrategy,
        symbol="STREAM",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        on_event=on_event,
        stream_progress_interval=5,
        stream_equity_interval=7,
        stream_batch_size=8,
        stream_max_buffer=64,
    )

    assert events
    assert events[0]["event_type"] == "started"
    assert events[-1]["event_type"] == "finished"
    seq_values = [event["seq"] for event in events]
    assert seq_values == sorted(seq_values)
    progress_count = sum(1 for event in events if event.get("event_type") == "progress")
    equity_count = sum(1 for event in events if event.get("event_type") == "equity")
    assert 0 < progress_count < 10
    assert 0 < equity_count < 10
    assert result.metrics.initial_market_value == pytest.approx(100000.0, rel=1e-9)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"stream_progress_interval": 0},
        {"stream_equity_interval": 0},
        {"stream_batch_size": 0},
        {"stream_max_buffer": 0},
    ],
)
def test_run_backtest_on_event_rejects_non_positive_stream_options(
    kwargs: dict[str, Any],
) -> None:
    """Stream API should reject non-positive option values."""
    data = _build_benchmark_data(n=5, symbol="STREAM_OPT")

    with pytest.raises(ValueError):
        akquant.run_backtest(
            data=data,
            strategy=NoopStrategy,
            symbol="STREAM_OPT",
            show_progress=False,
            on_event=lambda _event: None,
            **kwargs,
        )


def test_run_backtest_on_event_matches_run_backtest_result() -> None:
    """Stream run should keep the same backtest result semantics."""
    data = _build_benchmark_data(n=120, symbol="CONSIST")
    common_args: dict[str, Any] = dict(
        data=data,
        strategy=NoopStrategy,
        symbol="CONSIST",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
    )

    normal = akquant.run_backtest(**common_args)
    stream_events: list[akquant.BacktestStreamEvent] = []
    stream = akquant.run_backtest(
        **common_args,
        on_event=stream_events.append,
        stream_progress_interval=8,
        stream_equity_interval=8,
        stream_batch_size=16,
        stream_max_buffer=128,
    )

    assert len(stream.trades) == len(normal.trades)
    assert len(stream.equity_curve) == len(normal.equity_curve)
    assert stream.metrics.total_return == pytest.approx(
        normal.metrics.total_return, rel=1e-9
    )
    assert stream.metrics.max_drawdown == pytest.approx(
        normal.metrics.max_drawdown, rel=1e-9
    )
    assert stream_events[0]["event_type"] == "started"
    assert stream_events[-1]["event_type"] == "finished"


def test_run_backtest_on_event_emits_owner_strategy_id_for_trade_events() -> None:
    """Stream trade events should include owner strategy id in payload."""
    bars = _build_regression_bars("STREAM_OWNER")
    events: list[akquant.BacktestStreamEvent] = []
    result = akquant.run_backtest(
        data=bars,
        strategy=RegressionStrategy,
        symbol="STREAM_OWNER",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        on_event=events.append,
        strategy_id="stream_alpha",
    )
    trade_events = [event for event in events if event.get("event_type") == "trade"]
    assert trade_events
    owner_ids = {
        str(event.get("payload", {}).get("owner_strategy_id", ""))
        for event in trade_events
    }
    assert owner_ids == {"stream_alpha"}
    assert result.metrics.initial_market_value == pytest.approx(100000.0, rel=1e-9)


def test_run_backtest_without_on_event_keeps_legacy_semantics() -> None:
    """run_backtest without on_event should keep non-stream semantics."""
    data = _build_benchmark_data(n=80, symbol="NO_EVENT")
    result = akquant.run_backtest(
        data=data,
        strategy=NoopStrategy,
        symbol="NO_EVENT",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
    )
    assert result.metrics.initial_market_value == pytest.approx(100000.0, rel=1e-9)
    assert len(result.equity_curve) == len(data)


def test_run_backtest_strategy_id_propagates_to_orders() -> None:
    """run_backtest should tag generated orders with owner strategy id."""
    bars = _build_regression_bars("OWNER")
    result = akquant.run_backtest(
        data=bars,
        strategy=RegressionStrategy,
        symbol="OWNER",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
    )
    orders_df = result.orders_df
    assert not orders_df.empty
    assert "owner_strategy_id" in orders_df.columns
    assert set(orders_df["owner_strategy_id"].dropna().astype(str)) == {"alpha"}


def test_run_backtest_accepts_strategies_by_slot() -> None:
    """run_backtest should accept optional strategies_by_slot mapping."""
    bars = _build_regression_bars("SLOT_MAP")
    result = akquant.run_backtest(
        data=bars,
        strategy=NoopStrategy,
        symbol="SLOT_MAP",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategies_by_slot={"beta": NoopStrategy},
    )
    assert result.trade_metrics.total_closed_trades == 0


def test_run_backtest_multi_slot_owner_strategy_ids_mixed() -> None:
    """run_backtest should expose mixed owner strategy ids across slots."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_slots") or not hasattr(
        probe, "set_strategy_for_slot"
    ):
        pytest.skip("Engine binary does not expose multi-slot strategy methods")

    bars = _build_regression_bars("SLOT_OWNER_MIX")
    result = akquant.run_backtest(
        data=bars,
        strategy=RegressionStrategy,
        symbol="SLOT_OWNER_MIX",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategies_by_slot={"beta": RegressionStrategy},
    )
    orders_df = result.orders_df
    executions_df = result.executions_df
    assert not orders_df.empty
    assert not executions_df.empty
    assert "owner_strategy_id" in orders_df.columns
    assert "owner_strategy_id" in executions_df.columns
    order_owner_ids = set(orders_df["owner_strategy_id"].dropna().astype(str))
    exec_owner_ids = set(executions_df["owner_strategy_id"].dropna().astype(str))
    assert order_owner_ids == {"alpha", "beta"}
    assert exec_owner_ids == {"alpha", "beta"}


def test_run_backtest_functional_on_start_on_stop_callbacks() -> None:
    """Function-style strategy should support on_start/on_stop lifecycle callbacks."""
    events: list[str] = []

    def initialize(ctx: Any) -> None:
        _ = ctx
        events.append("initialize")

    def on_start(ctx: Any) -> None:
        _ = ctx
        events.append("on_start")

    def on_bar(ctx: Any, bar: akquant.Bar) -> None:
        _ = ctx
        _ = bar
        events.append("on_bar")

    def on_stop(ctx: Any) -> None:
        _ = ctx
        events.append("on_stop")

    _ = akquant.run_backtest(
        data=_build_regression_bars("FUNC_LIFECYCLE"),
        strategy=on_bar,
        symbol="FUNC_LIFECYCLE",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        initialize=initialize,
        on_start=on_start,
        on_stop=on_stop,
    )

    assert events[0] == "initialize"
    assert events.count("on_start") == 1
    assert events.count("on_stop") == 1
    assert events[-1] == "on_stop"
    assert events.count("on_bar") == 3


@pytest.mark.parametrize(
    ("limit_key", "limit_value", "rejection_marker", "required_method"),
    [
        (
            "strategy_max_order_value",
            {"alpha": 50.0, "beta": 200.0},
            "exceeds strategy limit",
            "set_strategy_max_order_value_limits",
        ),
        (
            "strategy_max_order_size",
            {"alpha": 5.0, "beta": 20.0},
            "order quantity",
            "set_strategy_max_order_size_limits",
        ),
    ],
)
def test_run_backtest_functional_multi_slot_risk_matrix(
    limit_key: str,
    limit_value: dict[str, float],
    rejection_marker: str,
    required_method: str,
) -> None:
    """Function-style multi-slot strategies should honor per-slot risk limits."""
    probe = akquant.Engine()
    if not hasattr(probe, required_method):
        pytest.skip("Engine binary does not expose required strategy risk methods")

    def alpha_on_bar(ctx: Any, bar: akquant.Bar) -> None:
        if getattr(ctx, "_submitted_once", False):
            return
        ctx.buy(symbol=bar.symbol, quantity=10)
        ctx._submitted_once = True

    def beta_on_bar(ctx: Any, bar: akquant.Bar) -> None:
        if getattr(ctx, "_submitted_once", False):
            return
        ctx.buy(symbol=bar.symbol, quantity=10)
        ctx._submitted_once = True

    events: list[akquant.BacktestStreamEvent] = []
    extra_limits: dict[str, Any] = {limit_key: limit_value}
    result = akquant.run_backtest(
        data=_build_regression_bars(f"FUNC_SLOT_{limit_key.upper()}"),
        strategy=alpha_on_bar,
        symbol=f"FUNC_SLOT_{limit_key.upper()}",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategies_by_slot={"beta": beta_on_bar},
        on_event=events.append,
        stream_progress_interval=1,
        stream_equity_interval=1,
        stream_batch_size=1,
        stream_max_buffer=256,
        **extra_limits,
    )

    orders_df = result.orders_df
    assert not orders_df.empty
    alpha_rows = orders_df[orders_df["owner_strategy_id"].astype(str) == "alpha"]
    beta_rows = orders_df[orders_df["owner_strategy_id"].astype(str) == "beta"]
    assert not alpha_rows.empty
    assert not beta_rows.empty
    alpha_reject_reasons = alpha_rows["reject_reason"].fillna("").astype(str).tolist()
    beta_reject_reasons = beta_rows["reject_reason"].fillna("").astype(str).tolist()
    assert any(rejection_marker in reason for reason in alpha_reject_reasons)
    assert not any(rejection_marker in reason for reason in beta_reject_reasons)

    risk_owner_ids = {
        str(event["payload"].get("owner_strategy_id"))
        for event in events
        if event.get("event_type") == "risk"
    }
    assert risk_owner_ids == {"alpha"}


def test_run_backtest_strategy_max_order_value_by_slot() -> None:
    """Per-strategy order value limit should reject only limited slot orders."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_max_order_value_limits"):
        pytest.skip("Engine binary does not expose strategy-level risk limit methods")

    bars = _build_regression_bars("SLOT_RISK_LIMIT")
    result = akquant.run_backtest(
        data=bars,
        strategy=SingleBuyStrategy,
        symbol="SLOT_RISK_LIMIT",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategies_by_slot={"beta": SingleBuyStrategy},
        strategy_max_order_value={"alpha": 50.0, "beta": 200.0},
    )
    orders_df = result.orders_df
    assert not orders_df.empty
    alpha_rows = orders_df[orders_df["owner_strategy_id"].astype(str) == "alpha"]
    beta_rows = orders_df[orders_df["owner_strategy_id"].astype(str) == "beta"]
    assert not alpha_rows.empty
    assert not beta_rows.empty
    alpha_reject_reasons = alpha_rows["reject_reason"].fillna("").astype(str).tolist()
    assert any("exceeds strategy limit" in reason for reason in alpha_reject_reasons)
    beta_reject_reasons = beta_rows["reject_reason"].fillna("").astype(str).tolist()
    assert not any("exceeds strategy limit" in reason for reason in beta_reject_reasons)


def test_run_backtest_strategy_max_order_size_by_slot() -> None:
    """Per-strategy order size limit should reject only limited slot orders."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_max_order_size_limits"):
        pytest.skip("Engine binary does not expose strategy-level risk limit methods")

    bars = _build_regression_bars("SLOT_RISK_SIZE")
    result = akquant.run_backtest(
        data=bars,
        strategy=SingleBuyStrategy,
        symbol="SLOT_RISK_SIZE",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategies_by_slot={"beta": SingleBuyStrategy},
        strategy_max_order_size={"alpha": 5.0, "beta": 20.0},
    )
    orders_df = result.orders_df
    assert not orders_df.empty
    alpha_rows = orders_df[orders_df["owner_strategy_id"].astype(str) == "alpha"]
    beta_rows = orders_df[orders_df["owner_strategy_id"].astype(str) == "beta"]
    alpha_reject_reasons = alpha_rows["reject_reason"].fillna("").astype(str).tolist()
    beta_reject_reasons = beta_rows["reject_reason"].fillna("").astype(str).tolist()
    assert any("order quantity" in reason for reason in alpha_reject_reasons)
    assert not any("order quantity" in reason for reason in beta_reject_reasons)


def test_run_backtest_strategy_slot_risk_from_config() -> None:
    """Config strategy settings should drive slot topology and risk limits."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_max_order_size_limits"):
        pytest.skip("Engine binary does not expose strategy-level risk limit methods")

    config = akquant.BacktestConfig(
        strategy_config=akquant.StrategyConfig(
            initial_cash=100000.0,
            strategy_id="alpha",
            strategies_by_slot={"beta": SingleBuyStrategy},
            strategy_max_order_size={"alpha": 5.0, "beta": 20.0},
        )
    )
    bars = _build_regression_bars("SLOT_RISK_SIZE_CFG")
    result = akquant.run_backtest(
        data=bars,
        strategy=SingleBuyStrategy,
        symbol="SLOT_RISK_SIZE_CFG",
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        config=config,
    )
    orders_df = result.orders_df
    assert not orders_df.empty
    alpha_rows = orders_df[orders_df["owner_strategy_id"].astype(str) == "alpha"]
    beta_rows = orders_df[orders_df["owner_strategy_id"].astype(str) == "beta"]
    alpha_reject_reasons = alpha_rows["reject_reason"].fillna("").astype(str).tolist()
    beta_reject_reasons = beta_rows["reject_reason"].fillna("").astype(str).tolist()
    assert any("order quantity" in reason for reason in alpha_reject_reasons)
    assert not any("order quantity" in reason for reason in beta_reject_reasons)


def test_run_backtest_explicit_strategy_slot_risk_overrides_config() -> None:
    """Explicit strategy slot risk args should override config values."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_max_order_size_limits"):
        pytest.skip("Engine binary does not expose strategy-level risk limit methods")

    config = akquant.BacktestConfig(
        strategy_config=akquant.StrategyConfig(
            initial_cash=100000.0,
            strategy_id="alpha",
            strategies_by_slot={"beta": SingleBuyStrategy},
            strategy_max_order_size={"alpha": 5.0, "beta": 20.0},
        )
    )
    bars = _build_regression_bars("SLOT_RISK_SIZE_CFG_OVERRIDE")
    result = akquant.run_backtest(
        data=bars,
        strategy=SingleBuyStrategy,
        symbol="SLOT_RISK_SIZE_CFG_OVERRIDE",
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        config=config,
        strategy_max_order_size={"alpha": 20.0, "beta": 5.0},
    )
    orders_df = result.orders_df
    assert not orders_df.empty
    alpha_rows = orders_df[orders_df["owner_strategy_id"].astype(str) == "alpha"]
    beta_rows = orders_df[orders_df["owner_strategy_id"].astype(str) == "beta"]
    alpha_reject_reasons = alpha_rows["reject_reason"].fillna("").astype(str).tolist()
    beta_reject_reasons = beta_rows["reject_reason"].fillna("").astype(str).tolist()
    assert not any("order quantity" in reason for reason in alpha_reject_reasons)
    assert any("order quantity" in reason for reason in beta_reject_reasons)


def test_backtest_result_strategy_level_views() -> None:
    """BacktestResult should provide strategy-level orders/executions views."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_slots") or not hasattr(
        probe, "set_strategy_for_slot"
    ):
        pytest.skip("Engine binary does not expose multi-slot strategy methods")

    bars = _build_regression_bars("SLOT_VIEW")
    result = akquant.run_backtest(
        data=bars,
        strategy=RegressionStrategy,
        symbol="SLOT_VIEW",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategies_by_slot={"beta": RegressionStrategy},
    )
    orders_view = result.orders_by_strategy()
    executions_view = result.executions_by_strategy()

    assert set(orders_view["owner_strategy_id"].astype(str)) == {"alpha", "beta"}
    assert set(executions_view["owner_strategy_id"].astype(str)) == {"alpha", "beta"}
    assert int(orders_view["order_count"].sum()) == len(result.orders_df)
    assert int(executions_view["execution_count"].sum()) == len(result.executions_df)


def test_backtest_result_risk_rejections_by_strategy_view() -> None:
    """BacktestResult should aggregate strategy-level risk rejections."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_reduce_only_after_risk"):
        pytest.skip("Engine binary does not expose strategy-level risk limit methods")

    bars = _build_reduce_only_bars("SLOT_RISK_VIEW")
    result = akquant.run_backtest(
        data=bars,
        strategy=BuyBuySellBuyStrategy,
        symbol="SLOT_RISK_VIEW",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategies_by_slot={"beta": BuyBuySellBuyStrategy},
        strategy_max_daily_loss={"alpha": 5.0, "beta": 50.0},
        strategy_reduce_only_after_risk={"alpha": True, "beta": False},
    )
    risk_view = result.risk_rejections_by_strategy()
    assert not risk_view.empty
    assert "owner_strategy_id" in risk_view.columns
    alpha = risk_view[risk_view["owner_strategy_id"].astype(str) == "alpha"]
    assert not alpha.empty
    alpha_row = alpha.iloc[0]
    assert int(alpha_row["risk_reject_count"]) >= 2
    assert int(alpha_row["daily_loss_reject_count"]) >= 1
    assert int(alpha_row["reduce_only_reject_count"]) >= 1
    assert "strategy_risk_budget_reject_count" in risk_view.columns
    assert "portfolio_risk_budget_reject_count" in risk_view.columns


def test_backtest_result_risk_rejections_trend_view() -> None:
    """BacktestResult should provide daily trend for risk rejections."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_reduce_only_after_risk"):
        pytest.skip("Engine binary does not expose strategy-level risk limit methods")

    bars = _build_reduce_only_bars("SLOT_RISK_TREND")
    result = akquant.run_backtest(
        data=bars,
        strategy=BuyBuySellBuyStrategy,
        symbol="SLOT_RISK_TREND",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategies_by_slot={"beta": BuyBuySellBuyStrategy},
        strategy_max_daily_loss={"alpha": 5.0, "beta": 50.0},
        strategy_reduce_only_after_risk={"alpha": True, "beta": False},
    )
    trend_view = result.risk_rejections_trend(freq="D")
    assert not trend_view.empty
    assert "date" in trend_view.columns
    assert "risk_reject_count" in trend_view.columns
    assert int(trend_view["risk_reject_count"].sum()) >= 2
    assert int(trend_view["reduce_only_reject_count"].sum()) >= 1
    assert "strategy_risk_budget_reject_count" in trend_view.columns
    assert "portfolio_risk_budget_reject_count" in trend_view.columns


def test_backtest_result_risk_rejections_trend_by_strategy_view() -> None:
    """BacktestResult should provide strategy-split risk rejection trend."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_reduce_only_after_risk"):
        pytest.skip("Engine binary does not expose strategy-level risk limit methods")

    bars = _build_reduce_only_bars("SLOT_RISK_TREND_BY_STRATEGY")
    result = akquant.run_backtest(
        data=bars,
        strategy=BuyBuySellBuyStrategy,
        symbol="SLOT_RISK_TREND_BY_STRATEGY",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategies_by_slot={"beta": BuyBuySellBuyStrategy},
        strategy_max_daily_loss={"alpha": 5.0, "beta": 50.0},
        strategy_reduce_only_after_risk={"alpha": True, "beta": False},
    )
    trend_by_strategy = result.risk_rejections_trend_by_strategy(freq="D")
    assert not trend_by_strategy.empty
    assert "date" in trend_by_strategy.columns
    assert "owner_strategy_id" in trend_by_strategy.columns
    assert "risk_reject_count" in trend_by_strategy.columns
    assert "strategy_risk_budget_reject_count" in trend_by_strategy.columns
    assert "portfolio_risk_budget_reject_count" in trend_by_strategy.columns
    alpha = trend_by_strategy[
        trend_by_strategy["owner_strategy_id"].astype(str) == "alpha"
    ]
    assert not alpha.empty
    assert int(alpha["risk_reject_count"].sum()) >= 2


def test_run_backtest_rejects_invalid_strategies_by_slot_type() -> None:
    """run_backtest should validate strategies_by_slot type."""
    bars = _build_regression_bars("SLOT_BAD")
    with pytest.raises(TypeError, match="strategies_by_slot"):
        akquant.run_backtest(
            data=bars,
            strategy=NoopStrategy,
            symbol="SLOT_BAD",
            show_progress=False,
            strategies_by_slot=cast(Any, ["bad"]),
        )


def test_run_backtest_rejects_unknown_strategy_max_order_value_key() -> None:
    """Unknown strategy id in strategy_max_order_value should fail fast."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_max_order_value_limits"):
        pytest.skip("Engine binary does not expose strategy-level risk limit methods")
    bars = _build_regression_bars("SLOT_RISK_BAD")
    with pytest.raises(ValueError, match="unknown strategy id"):
        akquant.run_backtest(
            data=bars,
            strategy=NoopStrategy,
            symbol="SLOT_RISK_BAD",
            show_progress=False,
            strategy_id="alpha",
            strategy_max_order_value={"beta": 100.0},
        )


def test_run_backtest_rejects_unknown_strategy_max_order_size_key() -> None:
    """Unknown strategy id in strategy_max_order_size should fail fast."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_max_order_size_limits"):
        pytest.skip("Engine binary does not expose strategy-level risk limit methods")
    bars = _build_regression_bars("SLOT_RISK_SIZE_BAD")
    with pytest.raises(ValueError, match="unknown strategy id"):
        akquant.run_backtest(
            data=bars,
            strategy=NoopStrategy,
            symbol="SLOT_RISK_SIZE_BAD",
            show_progress=False,
            strategy_id="alpha",
            strategy_max_order_size={"beta": 10.0},
        )


def test_run_backtest_strategy_max_position_size_by_slot() -> None:
    """Per-strategy position limit should reject only limited slot orders."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_max_position_size_limits"):
        pytest.skip("Engine binary does not expose strategy-level risk limit methods")

    bars = _build_regression_bars("SLOT_RISK_POSITION")
    result = akquant.run_backtest(
        data=bars,
        strategy=DualBuyStrategy,
        symbol="SLOT_RISK_POSITION",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategies_by_slot={"beta": DualBuyStrategy},
        strategy_max_position_size={"alpha": 15.0, "beta": 30.0},
    )
    orders_df = result.orders_df
    alpha_rows = orders_df[orders_df["owner_strategy_id"].astype(str) == "alpha"]
    beta_rows = orders_df[orders_df["owner_strategy_id"].astype(str) == "beta"]
    alpha_reject_reasons = alpha_rows["reject_reason"].fillna("").astype(str).tolist()
    beta_reject_reasons = beta_rows["reject_reason"].fillna("").astype(str).tolist()
    assert any("projected position" in reason for reason in alpha_reject_reasons)
    assert not any("projected position" in reason for reason in beta_reject_reasons)


def test_run_backtest_rejects_unknown_strategy_max_position_size_key() -> None:
    """Unknown strategy id in strategy_max_position_size should fail fast."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_max_position_size_limits"):
        pytest.skip("Engine binary does not expose strategy-level risk limit methods")
    bars = _build_regression_bars("SLOT_RISK_POSITION_BAD")
    with pytest.raises(ValueError, match="unknown strategy id"):
        akquant.run_backtest(
            data=bars,
            strategy=NoopStrategy,
            symbol="SLOT_RISK_POSITION_BAD",
            show_progress=False,
            strategy_id="alpha",
            strategy_max_position_size={"beta": 10.0},
        )


def test_run_backtest_strategy_max_daily_loss_by_slot() -> None:
    """Per-strategy daily loss limit should reject only limited slot orders."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_max_daily_loss_limits"):
        pytest.skip("Engine binary does not expose strategy-level risk limit methods")

    bars = _build_daily_loss_bars("SLOT_RISK_DAILY_LOSS")
    result = akquant.run_backtest(
        data=bars,
        strategy=DualBuyStrategy,
        symbol="SLOT_RISK_DAILY_LOSS",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategies_by_slot={"beta": DualBuyStrategy},
        strategy_max_daily_loss={"alpha": 5.0, "beta": 50.0},
    )
    orders_df = result.orders_df
    alpha_rows = orders_df[orders_df["owner_strategy_id"].astype(str) == "alpha"]
    beta_rows = orders_df[orders_df["owner_strategy_id"].astype(str) == "beta"]
    alpha_reject_reasons = alpha_rows["reject_reason"].fillna("").astype(str).tolist()
    beta_reject_reasons = beta_rows["reject_reason"].fillna("").astype(str).tolist()
    assert any("daily loss" in reason for reason in alpha_reject_reasons)
    assert not any("daily loss" in reason for reason in beta_reject_reasons)


def test_run_backtest_rejects_unknown_strategy_max_daily_loss_key() -> None:
    """Unknown strategy id in strategy_max_daily_loss should fail fast."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_max_daily_loss_limits"):
        pytest.skip("Engine binary does not expose strategy-level risk limit methods")
    bars = _build_regression_bars("SLOT_RISK_DAILY_LOSS_BAD")
    with pytest.raises(ValueError, match="unknown strategy id"):
        akquant.run_backtest(
            data=bars,
            strategy=NoopStrategy,
            symbol="SLOT_RISK_DAILY_LOSS_BAD",
            show_progress=False,
            strategy_id="alpha",
            strategy_max_daily_loss={"beta": 10.0},
        )


def test_run_backtest_strategy_max_drawdown_by_slot() -> None:
    """Per-strategy drawdown limit should reject only limited slot orders."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_max_drawdown_limits"):
        pytest.skip("Engine binary does not expose strategy-level risk limit methods")

    bars = _build_daily_loss_bars("SLOT_RISK_DRAWDOWN")
    result = akquant.run_backtest(
        data=bars,
        strategy=DualBuyStrategy,
        symbol="SLOT_RISK_DRAWDOWN",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategies_by_slot={"beta": DualBuyStrategy},
        strategy_max_drawdown={"alpha": 5.0, "beta": 50.0},
    )
    orders_df = result.orders_df
    alpha_rows = orders_df[orders_df["owner_strategy_id"].astype(str) == "alpha"]
    beta_rows = orders_df[orders_df["owner_strategy_id"].astype(str) == "beta"]
    alpha_reject_reasons = alpha_rows["reject_reason"].fillna("").astype(str).tolist()
    beta_reject_reasons = beta_rows["reject_reason"].fillna("").astype(str).tolist()
    assert any("drawdown" in reason for reason in alpha_reject_reasons)
    assert not any("drawdown" in reason for reason in beta_reject_reasons)


def test_run_backtest_rejects_unknown_strategy_max_drawdown_key() -> None:
    """Unknown strategy id in strategy_max_drawdown should fail fast."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_max_drawdown_limits"):
        pytest.skip("Engine binary does not expose strategy-level risk limit methods")
    bars = _build_regression_bars("SLOT_RISK_DRAWDOWN_BAD")
    with pytest.raises(ValueError, match="unknown strategy id"):
        akquant.run_backtest(
            data=bars,
            strategy=NoopStrategy,
            symbol="SLOT_RISK_DRAWDOWN_BAD",
            show_progress=False,
            strategy_id="alpha",
            strategy_max_drawdown={"beta": 10.0},
        )


def test_run_backtest_reduce_only_after_risk_allows_only_closing_orders() -> None:
    """Reduce-only mode after risk should reject reopen orders."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_reduce_only_after_risk"):
        pytest.skip("Engine binary does not expose strategy-level risk limit methods")

    bars = _build_reduce_only_bars("SLOT_RISK_REDUCE_ONLY")
    result = akquant.run_backtest(
        data=bars,
        strategy=BuyBuySellBuyStrategy,
        symbol="SLOT_RISK_REDUCE_ONLY",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategies_by_slot={"beta": BuyBuySellBuyStrategy},
        strategy_max_daily_loss={"alpha": 5.0, "beta": 50.0},
        strategy_reduce_only_after_risk={"alpha": True, "beta": False},
    )
    orders_df = result.orders_df
    alpha_rows = orders_df[orders_df["owner_strategy_id"].astype(str) == "alpha"]
    alpha_reject_reasons = alpha_rows["reject_reason"].fillna("").astype(str).tolist()
    assert any("daily loss" in reason for reason in alpha_reject_reasons)
    assert any("reduce_only mode" in reason for reason in alpha_reject_reasons)


def test_run_backtest_strategy_risk_cooldown_blocks_orders() -> None:
    """Risk-triggered cooldown should reject subsequent orders for configured bars."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_risk_cooldown_bars"):
        pytest.skip("Engine binary does not expose strategy cooldown methods")

    bars = _build_reduce_only_bars("SLOT_RISK_COOLDOWN")
    result = akquant.run_backtest(
        data=bars,
        strategy=ContinuousBuyStrategy,
        symbol="SLOT_RISK_COOLDOWN",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategy_max_order_size={"alpha": 5.0},
        strategy_risk_cooldown_bars={"alpha": 2},
    )
    orders_df = result.orders_df
    assert not orders_df.empty
    reject_reasons = orders_df["reject_reason"].fillna("").astype(str).tolist()
    assert any("order quantity" in reason for reason in reject_reasons)
    assert any("cooldown" in reason for reason in reject_reasons)


def test_run_backtest_rejects_unknown_strategy_reduce_only_after_risk_key() -> None:
    """Unknown strategy id in reduce-only map should fail fast."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_reduce_only_after_risk"):
        pytest.skip("Engine binary does not expose strategy-level risk limit methods")
    bars = _build_regression_bars("SLOT_RISK_REDUCE_ONLY_BAD")
    with pytest.raises(ValueError, match="unknown strategy id"):
        akquant.run_backtest(
            data=bars,
            strategy=NoopStrategy,
            symbol="SLOT_RISK_REDUCE_ONLY_BAD",
            show_progress=False,
            strategy_id="alpha",
            strategy_reduce_only_after_risk={"beta": True},
        )


def test_run_backtest_rejects_unknown_strategy_risk_cooldown_bars_key() -> None:
    """Unknown strategy id in strategy_risk_cooldown_bars should fail fast."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_risk_cooldown_bars"):
        pytest.skip("Engine binary does not expose strategy cooldown methods")
    bars = _build_regression_bars("SLOT_RISK_COOLDOWN_BAD")
    with pytest.raises(ValueError, match="unknown strategy id"):
        akquant.run_backtest(
            data=bars,
            strategy=NoopStrategy,
            symbol="SLOT_RISK_COOLDOWN_BAD",
            show_progress=False,
            strategy_id="alpha",
            strategy_risk_cooldown_bars={"beta": 2},
        )


def test_run_backtest_rejects_unknown_strategy_priority_key() -> None:
    """Unknown strategy id in strategy_priority should fail fast."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_priorities"):
        pytest.skip("Engine binary does not expose strategy priority methods")
    bars = _build_regression_bars("SLOT_PRIORITY_BAD")
    with pytest.raises(ValueError, match="unknown strategy id"):
        akquant.run_backtest(
            data=bars,
            strategy=NoopStrategy,
            symbol="SLOT_PRIORITY_BAD",
            show_progress=False,
            strategy_id="alpha",
            strategy_priority={"beta": 100},
        )


def test_run_backtest_rejects_unknown_strategy_risk_budget_key() -> None:
    """Unknown strategy id in strategy_risk_budget should fail fast."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_risk_budget_limits"):
        pytest.skip("Engine binary does not expose strategy risk budget methods")
    bars = _build_regression_bars("SLOT_RISK_BUDGET_BAD")
    with pytest.raises(ValueError, match="unknown strategy id"):
        akquant.run_backtest(
            data=bars,
            strategy=NoopStrategy,
            symbol="SLOT_RISK_BUDGET_BAD",
            show_progress=False,
            strategy_id="alpha",
            strategy_risk_budget={"beta": 100.0},
        )


def test_run_backtest_rejects_invalid_risk_budget_mode() -> None:
    """Invalid risk_budget_mode should fail fast."""
    bars = _build_regression_bars("SLOT_RISK_BUDGET_MODE_BAD")
    with pytest.raises(ValueError, match="risk_budget_mode"):
        akquant.run_backtest(
            data=bars,
            strategy=NoopStrategy,
            symbol="SLOT_RISK_BUDGET_MODE_BAD",
            show_progress=False,
            risk_budget_mode=cast(Any, "bad_mode"),
        )


def test_run_backtest_strategy_id_propagates_to_executions_df() -> None:
    """run_backtest should expose owner strategy id in executions dataframe."""
    bars = _build_regression_bars("OWNER_EXEC")
    result = akquant.run_backtest(
        data=bars,
        strategy=RegressionStrategy,
        symbol="OWNER_EXEC",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha_exec",
    )
    executions_df = result.executions_df
    assert not executions_df.empty
    assert "owner_strategy_id" in executions_df.columns
    owner_ids = set(executions_df["owner_strategy_id"].dropna().astype(str))
    assert owner_ids == {"alpha_exec"}


def test_run_backtest_with_on_event_matches_stream_entry() -> None:
    """run_backtest with on_event should match unified stream semantics."""
    data = _build_benchmark_data(n=120, symbol="EVENT_EQ")
    common_args: dict[str, Any] = dict(
        data=data,
        strategy=NoopStrategy,
        symbol="EVENT_EQ",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
    )
    direct_events: list[akquant.BacktestStreamEvent] = []
    via_run_backtest = akquant.run_backtest(
        **common_args,
        on_event=direct_events.append,
        stream_progress_interval=8,
        stream_equity_interval=8,
        stream_batch_size=16,
        stream_max_buffer=128,
    )
    stream_events: list[akquant.BacktestStreamEvent] = []
    via_stream_entry = akquant.run_backtest(
        **common_args,
        on_event=stream_events.append,
        stream_progress_interval=8,
        stream_equity_interval=8,
        stream_batch_size=16,
        stream_max_buffer=128,
    )

    assert direct_events
    assert direct_events[0]["event_type"] == "started"
    assert direct_events[-1]["event_type"] == "finished"
    direct_seq_values = [event["seq"] for event in direct_events]
    assert direct_seq_values == sorted(direct_seq_values)
    assert len(via_run_backtest.trades) == len(via_stream_entry.trades)
    assert len(via_run_backtest.equity_curve) == len(via_stream_entry.equity_curve)
    assert via_run_backtest.metrics.total_return == pytest.approx(
        via_stream_entry.metrics.total_return, rel=1e-9
    )
    assert via_run_backtest.metrics.max_drawdown == pytest.approx(
        via_stream_entry.metrics.max_drawdown, rel=1e-9
    )


def test_run_backtest_on_event_multi_slot_owner_strategy_ids_mixed() -> None:
    """run_backtest with on_event should emit mixed owner strategy ids across slots."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_slots") or not hasattr(
        probe, "set_strategy_for_slot"
    ):
        pytest.skip("Engine binary does not expose multi-slot strategy methods")

    bars = _build_regression_bars("STREAM_SLOT_OWNER")
    events: list[akquant.BacktestStreamEvent] = []
    akquant.run_backtest(
        data=bars,
        strategy=RegressionStrategy,
        symbol="STREAM_SLOT_OWNER",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategies_by_slot={"beta": RegressionStrategy},
        on_event=events.append,
        stream_progress_interval=1,
        stream_equity_interval=1,
        stream_batch_size=1,
        stream_max_buffer=256,
    )

    owner_ids = {
        str(event["payload"]["owner_strategy_id"])
        for event in events
        if event.get("event_type") in {"order", "trade", "risk"}
        and "owner_strategy_id" in event.get("payload", {})
    }
    assert owner_ids == {"alpha", "beta"}


def test_run_backtest_on_event_strategy_priority_orders_requests_by_priority() -> None:
    """run_backtest with on_event should process higher-priority orders first."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_priorities"):
        pytest.skip("Engine binary does not expose strategy priority methods")

    bars = _build_regression_bars("STREAM_SLOT_PRIORITY")
    events: list[akquant.BacktestStreamEvent] = []
    akquant.run_backtest(
        data=bars,
        strategy=SingleBuyStrategy,
        symbol="STREAM_SLOT_PRIORITY",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategies_by_slot={"beta": SingleBuyStrategy},
        strategy_priority={"alpha": 1, "beta": 10},
        on_event=events.append,
        stream_progress_interval=1,
        stream_equity_interval=1,
        stream_batch_size=1,
        stream_max_buffer=256,
    )
    submitted_owner_ids = [
        str(event["payload"].get("owner_strategy_id"))
        for event in events
        if event.get("event_type") == "order"
        and str(event.get("payload", {}).get("status")) == "New"
    ]
    assert len(submitted_owner_ids) >= 2
    assert submitted_owner_ids[0] == "beta"
    assert submitted_owner_ids[1] == "alpha"


def test_run_backtest_on_event_portfolio_risk_budget_respects_priority_order() -> None:
    """Portfolio risk budget should reject lower-priority strategy."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_portfolio_risk_budget_limit"):
        pytest.skip("Engine binary does not expose portfolio risk budget methods")

    bars = _build_regression_bars("STREAM_SLOT_PORTFOLIO_BUDGET")
    events: list[akquant.BacktestStreamEvent] = []
    akquant.run_backtest(
        data=bars,
        strategy=SingleBuyStrategy,
        symbol="STREAM_SLOT_PORTFOLIO_BUDGET",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategies_by_slot={"beta": SingleBuyStrategy},
        strategy_priority={"alpha": 1, "beta": 10},
        portfolio_risk_budget=100.0,
        on_event=events.append,
        stream_progress_interval=1,
        stream_equity_interval=1,
        stream_batch_size=1,
        stream_max_buffer=256,
    )
    accepted = [
        str(event["payload"].get("owner_strategy_id"))
        for event in events
        if event.get("event_type") == "order"
        and str(event.get("payload", {}).get("status")) == "New"
    ]
    assert accepted == ["beta"]
    rejected = [
        (
            str(event["payload"].get("owner_strategy_id")),
            str(event["payload"].get("reason", "")),
        )
        for event in events
        if event.get("event_type") == "risk"
    ]
    assert any(
        owner_id == "alpha" and "portfolio risk budget" in reason.lower()
        for owner_id, reason in rejected
    )


def test_run_backtest_trade_notional_budget_blocks_later_orders() -> None:
    """Trade-notional budget mode should block later bars after accumulated fills."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_risk_budget_mode"):
        pytest.skip("Engine binary does not expose risk budget mode methods")
    bars = _build_regression_bars("SLOT_TRADE_NOTIONAL_BUDGET")
    result = akquant.run_backtest(
        data=bars,
        strategy=ContinuousBuyStrategy,
        symbol="SLOT_TRADE_NOTIONAL_BUDGET",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategy_risk_budget={"alpha": 100.0},
        risk_budget_mode="trade_notional",
    )
    reasons = result.orders_df["reject_reason"].fillna("").astype(str).tolist()
    assert any("risk budget" in reason.lower() for reason in reasons)


def test_run_backtest_trade_notional_budget_resets_daily() -> None:
    """Daily reset should allow next-day orders under trade-notional budget mode."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_risk_budget_reset_daily"):
        pytest.skip("Engine binary does not expose risk budget reset methods")
    bars = _build_regression_bars("SLOT_TRADE_NOTIONAL_RESET")
    result = akquant.run_backtest(
        data=bars,
        strategy=ContinuousSmallBuyStrategy,
        symbol="SLOT_TRADE_NOTIONAL_RESET",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategy_risk_budget={"alpha": 100.0},
        risk_budget_mode="trade_notional",
        risk_budget_reset_daily=True,
    )
    reasons = result.orders_df["reject_reason"].fillna("").astype(str).tolist()
    assert not any("risk budget" in reason.lower() for reason in reasons)


def test_run_backtest_on_event_strategy_max_order_value_by_slot() -> None:
    """Per-strategy order value limit should reflect in stream risk events."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_max_order_value_limits"):
        pytest.skip("Engine binary does not expose strategy-level risk limit methods")

    bars = _build_regression_bars("STREAM_SLOT_RISK")
    events: list[akquant.BacktestStreamEvent] = []
    akquant.run_backtest(
        data=bars,
        strategy=SingleBuyStrategy,
        symbol="STREAM_SLOT_RISK",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategies_by_slot={"beta": SingleBuyStrategy},
        strategy_max_order_value={"alpha": 50.0, "beta": 200.0},
        on_event=events.append,
        stream_progress_interval=1,
        stream_equity_interval=1,
        stream_batch_size=1,
        stream_max_buffer=256,
    )
    risk_owner_ids = {
        str(event["payload"].get("owner_strategy_id"))
        for event in events
        if event.get("event_type") == "risk"
    }
    assert risk_owner_ids == {"alpha"}


def test_run_backtest_on_event_strategy_max_order_size_by_slot() -> None:
    """Per-strategy order size limit should reflect in stream risk events."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_max_order_size_limits"):
        pytest.skip("Engine binary does not expose strategy-level risk limit methods")

    bars = _build_regression_bars("STREAM_SLOT_SIZE")
    events: list[akquant.BacktestStreamEvent] = []
    akquant.run_backtest(
        data=bars,
        strategy=SingleBuyStrategy,
        symbol="STREAM_SLOT_SIZE",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategies_by_slot={"beta": SingleBuyStrategy},
        strategy_max_order_size={"alpha": 5.0, "beta": 20.0},
        on_event=events.append,
        stream_progress_interval=1,
        stream_equity_interval=1,
        stream_batch_size=1,
        stream_max_buffer=256,
    )
    risk_owner_ids = {
        str(event["payload"].get("owner_strategy_id"))
        for event in events
        if event.get("event_type") == "risk"
    }
    assert risk_owner_ids == {"alpha"}


def test_run_backtest_on_event_strategy_max_position_size_by_slot() -> None:
    """Per-strategy position limit should reflect in stream risk events."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_max_position_size_limits"):
        pytest.skip("Engine binary does not expose strategy-level risk limit methods")

    bars = _build_regression_bars("STREAM_SLOT_POSITION")
    events: list[akquant.BacktestStreamEvent] = []
    akquant.run_backtest(
        data=bars,
        strategy=DualBuyStrategy,
        symbol="STREAM_SLOT_POSITION",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategies_by_slot={"beta": DualBuyStrategy},
        strategy_max_position_size={"alpha": 15.0, "beta": 30.0},
        on_event=events.append,
        stream_progress_interval=1,
        stream_equity_interval=1,
        stream_batch_size=1,
        stream_max_buffer=256,
    )
    risk_owner_ids = {
        str(event["payload"].get("owner_strategy_id"))
        for event in events
        if event.get("event_type") == "risk"
    }
    assert risk_owner_ids == {"alpha"}


def test_run_backtest_on_event_strategy_max_daily_loss_by_slot() -> None:
    """Per-strategy daily loss limit should reflect in stream risk events."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_max_daily_loss_limits"):
        pytest.skip("Engine binary does not expose strategy-level risk limit methods")

    bars = _build_daily_loss_bars("STREAM_SLOT_DAILY_LOSS")
    events: list[akquant.BacktestStreamEvent] = []
    akquant.run_backtest(
        data=bars,
        strategy=DualBuyStrategy,
        symbol="STREAM_SLOT_DAILY_LOSS",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategies_by_slot={"beta": DualBuyStrategy},
        strategy_max_daily_loss={"alpha": 5.0, "beta": 50.0},
        on_event=events.append,
        stream_progress_interval=1,
        stream_equity_interval=1,
        stream_batch_size=1,
        stream_max_buffer=256,
    )
    risk_owner_ids = {
        str(event["payload"].get("owner_strategy_id"))
        for event in events
        if event.get("event_type") == "risk"
    }
    assert risk_owner_ids == {"alpha"}


def test_run_backtest_on_event_strategy_max_drawdown_by_slot() -> None:
    """Per-strategy drawdown limit should reflect in stream risk events."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_max_drawdown_limits"):
        pytest.skip("Engine binary does not expose strategy-level risk limit methods")

    bars = _build_daily_loss_bars("STREAM_SLOT_DRAWDOWN")
    events: list[akquant.BacktestStreamEvent] = []
    akquant.run_backtest(
        data=bars,
        strategy=DualBuyStrategy,
        symbol="STREAM_SLOT_DRAWDOWN",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategies_by_slot={"beta": DualBuyStrategy},
        strategy_max_drawdown={"alpha": 5.0, "beta": 50.0},
        on_event=events.append,
        stream_progress_interval=1,
        stream_equity_interval=1,
        stream_batch_size=1,
        stream_max_buffer=256,
    )
    risk_owner_ids = {
        str(event["payload"].get("owner_strategy_id"))
        for event in events
        if event.get("event_type") == "risk"
    }
    assert risk_owner_ids == {"alpha"}


def test_run_backtest_on_event_reduce_only_after_risk_by_slot() -> None:
    """Stream risk events should include reduce-only rejections."""
    probe = akquant.Engine()
    if not hasattr(probe, "set_strategy_reduce_only_after_risk"):
        pytest.skip("Engine binary does not expose strategy-level risk limit methods")

    bars = _build_reduce_only_bars("STREAM_SLOT_REDUCE_ONLY")
    events: list[akquant.BacktestStreamEvent] = []
    akquant.run_backtest(
        data=bars,
        strategy=BuyBuySellBuyStrategy,
        symbol="STREAM_SLOT_REDUCE_ONLY",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        strategy_id="alpha",
        strategies_by_slot={"beta": BuyBuySellBuyStrategy},
        strategy_max_daily_loss={"alpha": 5.0, "beta": 50.0},
        strategy_reduce_only_after_risk={"alpha": True, "beta": False},
        on_event=events.append,
        stream_progress_interval=1,
        stream_equity_interval=1,
        stream_batch_size=1,
        stream_max_buffer=256,
    )
    alpha_reduce_only_events = [
        event
        for event in events
        if event.get("event_type") == "risk"
        and str(event.get("payload", {}).get("owner_strategy_id")) == "alpha"
        and "reduce_only mode" in str(event.get("payload", {}).get("reason", ""))
    ]
    assert alpha_reduce_only_events


def test_run_backtest_rejects_removed_engine_mode_option() -> None:
    """Removed internal _engine_mode option should raise fast."""
    data = _build_benchmark_data(n=10, symbol="BAD_MODE")
    with pytest.raises(TypeError, match="_engine_mode is no longer supported"):
        akquant.run_backtest(
            data=data,
            strategy=NoopStrategy,
            symbol="BAD_MODE",
            show_progress=False,
            _engine_mode="legacy_blocking",
        )


def test_run_backtest_on_event_high_frequency_keeps_critical_events() -> None:
    """High-frequency stream should keep critical events and sampled updates."""
    data = _build_benchmark_data(n=2000, symbol="HF")
    events: list[akquant.BacktestStreamEvent] = []
    akquant.run_backtest(
        data=data,
        strategy=NoopStrategy,
        symbol="HF",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
        on_event=events.append,
        stream_progress_interval=50,
        stream_equity_interval=40,
        stream_batch_size=64,
        stream_max_buffer=256,
    )

    assert events
    assert events[0]["event_type"] == "started"
    assert events[-1]["event_type"] == "finished"
    assert sum(1 for e in events if e.get("event_type") == "started") == 1
    assert sum(1 for e in events if e.get("event_type") == "finished") == 1
    progress_count = sum(1 for e in events if e.get("event_type") == "progress")
    equity_count = sum(1 for e in events if e.get("event_type") == "equity")
    assert progress_count < 80
    assert equity_count < 100
    seq_values = [event["seq"] for event in events]
    assert seq_values == sorted(seq_values)
    finished_payload = events[-1]["payload"]
    assert "dropped_event_count" in finished_payload
    assert "dropped_event_count_by_type" in finished_payload
    assert int(str(finished_payload["dropped_event_count"])) >= 0


def test_run_backtest_on_event_callback_error_continue_mode() -> None:
    """Continue mode should survive callback exceptions."""
    data = _build_benchmark_data(n=40, symbol="CALLBACK_CONT")
    events: list[akquant.BacktestStreamEvent] = []
    counter = {"n": 0}

    def on_event(event: akquant.BacktestStreamEvent) -> None:
        counter["n"] += 1
        if counter["n"] <= 3:
            raise RuntimeError("callback boom")
        events.append(event)

    result = akquant.run_backtest(
        data=data,
        strategy=NoopStrategy,
        symbol="CALLBACK_CONT",
        show_progress=False,
        on_event=on_event,
        stream_error_mode="continue",
    )

    assert events
    assert events[-1]["event_type"] == "finished"
    assert "callback_error_count" in events[-1]["payload"]
    assert int(str(events[-1]["payload"]["callback_error_count"])) >= 3
    assert result.metrics.initial_market_value == pytest.approx(1000000.0, rel=1e-9)


def test_run_backtest_on_event_reports_dropped_events_under_backpressure() -> None:
    """Finished payload should report dropped events when buffer is constrained."""
    data = _build_benchmark_data(n=300, symbol="DROP")
    events: list[akquant.BacktestStreamEvent] = []
    akquant.run_backtest(
        data=data,
        strategy=NoopStrategy,
        symbol="DROP",
        show_progress=False,
        on_event=events.append,
        stream_progress_interval=1,
        stream_equity_interval=1,
        stream_batch_size=32,
        stream_max_buffer=2,
    )

    assert events
    assert events[-1]["event_type"] == "finished"
    payload = events[-1]["payload"]
    dropped_count = int(str(payload.get("dropped_event_count", "0")))
    dropped_by_type = str(payload.get("dropped_event_count_by_type", ""))
    assert dropped_count > 0
    assert dropped_by_type


def test_run_backtest_on_event_audit_mode_enforces_full_delivery() -> None:
    """Audit mode should disable sampling and avoid dropping non-critical events."""
    data = _build_benchmark_data(n=300, symbol="AUDIT")
    events: list[akquant.BacktestStreamEvent] = []
    akquant.run_backtest(
        data=data,
        strategy=NoopStrategy,
        symbol="AUDIT",
        show_progress=False,
        on_event=events.append,
        stream_progress_interval=50,
        stream_equity_interval=40,
        stream_batch_size=32,
        stream_max_buffer=2,
        stream_mode="audit",
    )

    assert events
    assert events[-1]["event_type"] == "finished"
    progress_count = sum(1 for e in events if e.get("event_type") == "progress")
    equity_count = sum(1 for e in events if e.get("event_type") == "equity")
    assert progress_count > 100
    assert equity_count > 100
    payload = events[-1]["payload"]
    assert str(payload.get("stream_mode")) == "audit"
    assert str(payload.get("sampling_enabled")) == "false"
    assert str(payload.get("backpressure_policy")) == "block"
    assert int(str(payload.get("dropped_event_count", "0"))) == 0
    assert str(payload.get("dropped_event_count_by_type", "")) == ""


def test_run_backtest_on_event_callback_error_fail_fast_mode() -> None:
    """Fail-fast mode should raise once callback throws."""
    data = _build_benchmark_data(n=40, symbol="CALLBACK_FAIL")

    def on_event(_event: akquant.BacktestStreamEvent) -> None:
        raise RuntimeError("callback boom")

    with pytest.raises(RuntimeError, match="stream callback failed in fail_fast mode"):
        akquant.run_backtest(
            data=data,
            strategy=NoopStrategy,
            symbol="CALLBACK_FAIL",
            show_progress=False,
            on_event=on_event,
            stream_error_mode="fail_fast",
        )


def test_run_backtest_on_event_rejects_invalid_error_mode() -> None:
    """Invalid stream error mode should be rejected."""
    data = _build_benchmark_data(n=5, symbol="CALLBACK_MODE")
    with pytest.raises(ValueError):
        akquant.run_backtest(
            data=data,
            strategy=NoopStrategy,
            symbol="CALLBACK_MODE",
            show_progress=False,
            on_event=lambda _event: None,
            stream_error_mode=cast(Any, "bad_mode"),
        )


def test_run_backtest_on_event_rejects_invalid_stream_mode() -> None:
    """Invalid stream mode should be rejected."""
    data = _build_benchmark_data(n=5, symbol="MODE_BAD")
    with pytest.raises(ValueError):
        akquant.run_backtest(
            data=data,
            strategy=NoopStrategy,
            symbol="MODE_BAD",
            show_progress=False,
            on_event=lambda _event: None,
            stream_mode=cast(Any, "bad_mode"),
        )


def test_run_backtest_on_event_audit_mode_latency_budget_benchmark() -> None:
    """Audit mode benchmark with fixed callback delays for budget baselining."""
    data = _build_benchmark_data(n=240, symbol="AUDIT_BUDGET")
    delay_ms_options = [0, 1, 5]
    durations: dict[int, float] = {}
    event_counts: dict[int, int] = {}

    for delay_ms in delay_ms_options:
        counter = {"n": 0}

        def on_event(_event: akquant.BacktestStreamEvent) -> None:
            counter["n"] += 1
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)

        start = time.perf_counter()
        akquant.run_backtest(
            data=data,
            strategy=NoopStrategy,
            symbol="AUDIT_BUDGET",
            show_progress=False,
            on_event=on_event,
            stream_progress_interval=50,
            stream_equity_interval=50,
            stream_batch_size=32,
            stream_max_buffer=64,
            stream_mode="audit",
        )
        durations[delay_ms] = time.perf_counter() - start
        event_counts[delay_ms] = counter["n"]

    assert event_counts[0] > 100
    assert event_counts[1] == event_counts[0]
    assert event_counts[5] == event_counts[0]
    assert durations[1] > durations[0]
    assert durations[5] > durations[1]


def test_run_backtest_analyzer_plugins_lifecycle_and_output() -> None:
    """Analyzer plugins should receive lifecycle events and write result output."""

    class CountingAnalyzer:
        name = "counting"

        def __init__(self) -> None:
            self.starts = 0
            self.bars = 0
            self.trades = 0

        def on_start(self, context: dict[str, Any]) -> None:
            _ = context
            self.starts += 1

        def on_bar(self, context: dict[str, Any]) -> None:
            _ = context
            self.bars += 1

        def on_trade(self, context: dict[str, Any]) -> None:
            _ = context
            self.trades += 1

        def on_finish(self, context: dict[str, Any]) -> dict[str, Any]:
            _ = context
            return {
                "starts": self.starts,
                "bars": self.bars,
                "trades": self.trades,
            }

    analyzer = CountingAnalyzer()
    result = akquant.run_backtest(
        data=_build_regression_bars("ANALYZER"),
        strategy=RegressionStrategy,
        symbol="ANALYZER",
        execution_mode="current_close",
        show_progress=False,
        analyzer_plugins=[analyzer],
    )

    assert hasattr(result, "analyzer_outputs")
    outputs = cast(dict[str, dict[str, Any]], result.analyzer_outputs)
    assert "counting" in outputs
    assert outputs["counting"]["starts"] == 1
    assert outputs["counting"]["bars"] == 3
    assert outputs["counting"]["trades"] >= 1


def test_run_backtest_analyzer_plugins_multi_slot_owner_context() -> None:
    """Analyzer contexts should include owner strategy ids across slots."""

    class OwnerAwareAnalyzer:
        name = "owner_aware"

        def __init__(self) -> None:
            self.bar_owner_ids: set[str] = set()
            self.trade_owner_ids: set[str] = set()

        def on_start(self, context: dict[str, Any]) -> None:
            _ = context

        def on_bar(self, context: dict[str, Any]) -> None:
            owner_strategy_id = str(context.get("owner_strategy_id", "")).strip()
            if owner_strategy_id:
                self.bar_owner_ids.add(owner_strategy_id)

        def on_trade(self, context: dict[str, Any]) -> None:
            owner_strategy_id = str(context.get("owner_strategy_id", "")).strip()
            if owner_strategy_id:
                self.trade_owner_ids.add(owner_strategy_id)

        def on_finish(self, context: dict[str, Any]) -> dict[str, Any]:
            _ = context
            return {
                "bar_owner_ids": sorted(self.bar_owner_ids),
                "trade_owner_ids": sorted(self.trade_owner_ids),
            }

    analyzer = OwnerAwareAnalyzer()
    result = akquant.run_backtest(
        data=_build_regression_bars("ANALYZER_SLOT"),
        strategy=RegressionStrategy,
        symbol="ANALYZER_SLOT",
        execution_mode="current_close",
        show_progress=False,
        strategy_id="alpha",
        strategies_by_slot={"beta": RegressionStrategy},
        analyzer_plugins=[analyzer],
    )

    outputs = cast(dict[str, dict[str, Any]], result.analyzer_outputs)
    assert "owner_aware" in outputs
    assert outputs["owner_aware"]["bar_owner_ids"] == ["alpha", "beta"]
    assert outputs["owner_aware"]["trade_owner_ids"] == ["alpha", "beta"]
