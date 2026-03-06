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


def test_run_backtest_stream_emits_ordered_events() -> None:
    """Stream API should emit ordered lifecycle events."""
    data = _build_benchmark_data(n=20, symbol="STREAM")
    events: list[akquant.BacktestStreamEvent] = []

    def on_event(event: akquant.BacktestStreamEvent) -> None:
        events.append(event)

    result = akquant.run_backtest_stream(
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
def test_run_backtest_stream_rejects_non_positive_stream_options(
    kwargs: dict[str, Any],
) -> None:
    """Stream API should reject non-positive option values."""
    data = _build_benchmark_data(n=5, symbol="STREAM_OPT")

    with pytest.raises(ValueError):
        akquant.run_backtest_stream(
            data=data,
            strategy=NoopStrategy,
            symbol="STREAM_OPT",
            show_progress=False,
            on_event=lambda _event: None,
            **kwargs,
        )


def test_run_backtest_stream_matches_run_backtest_result() -> None:
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
    stream = akquant.run_backtest_stream(
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


def test_run_backtest_with_on_event_matches_stream_entry() -> None:
    """run_backtest with on_event should match run_backtest_stream semantics."""
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
    via_stream_entry = akquant.run_backtest_stream(
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


def test_run_backtest_stream_high_frequency_keeps_critical_events() -> None:
    """High-frequency stream should keep critical events and sampled updates."""
    data = _build_benchmark_data(n=2000, symbol="HF")
    events: list[akquant.BacktestStreamEvent] = []
    akquant.run_backtest_stream(
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


def test_run_backtest_stream_callback_error_continue_mode() -> None:
    """Continue mode should survive callback exceptions."""
    data = _build_benchmark_data(n=40, symbol="CALLBACK_CONT")
    events: list[akquant.BacktestStreamEvent] = []
    counter = {"n": 0}

    def on_event(event: akquant.BacktestStreamEvent) -> None:
        counter["n"] += 1
        if counter["n"] <= 3:
            raise RuntimeError("callback boom")
        events.append(event)

    result = akquant.run_backtest_stream(
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


def test_run_backtest_stream_callback_error_fail_fast_mode() -> None:
    """Fail-fast mode should raise once callback throws."""
    data = _build_benchmark_data(n=40, symbol="CALLBACK_FAIL")

    def on_event(_event: akquant.BacktestStreamEvent) -> None:
        raise RuntimeError("callback boom")

    with pytest.raises(RuntimeError, match="stream callback failed in fail_fast mode"):
        akquant.run_backtest_stream(
            data=data,
            strategy=NoopStrategy,
            symbol="CALLBACK_FAIL",
            show_progress=False,
            on_event=on_event,
            stream_error_mode="fail_fast",
        )


def test_run_backtest_stream_rejects_invalid_error_mode() -> None:
    """Invalid stream error mode should be rejected."""
    data = _build_benchmark_data(n=5, symbol="CALLBACK_MODE")
    with pytest.raises(ValueError):
        akquant.run_backtest_stream(
            data=data,
            strategy=NoopStrategy,
            symbol="CALLBACK_MODE",
            show_progress=False,
            on_event=lambda _event: None,
            stream_error_mode=cast(Any, "bad_mode"),
        )
