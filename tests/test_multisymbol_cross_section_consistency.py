from collections import defaultdict
from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest
from akquant import Bar, Strategy, run_backtest


def _build_symbol_df(
    symbol: str, timestamps: list[pd.Timestamp], closes: list[float]
) -> pd.DataFrame:
    rows = []
    for ts, close in zip(timestamps, closes):
        rows.append(
            {
                "date": ts,
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": 10000.0,
                "symbol": symbol,
            }
        )
    return pd.DataFrame(rows)


class BucketCrossSectionStrategy(Strategy):
    """Cross-section strategy that rebalances after timestamp completion."""

    def __init__(self, symbols: list[str], lookback: int = 2) -> None:
        """Initialize strategy state."""
        super().__init__()
        self.symbols = symbols
        self.lookback = lookback
        self.warmup_period = 0
        self.seen_by_ts: dict[int, set[str]] = defaultdict(set)
        self.complete_timestamps: list[int] = []
        self.selected_symbols: list[str] = []

    def on_bar(self, bar: Bar) -> None:
        """Collect symbols by timestamp and run cross-section logic once."""
        bucket = self.seen_by_ts[bar.timestamp]
        bucket.add(bar.symbol)
        if len(bucket) < len(self.symbols):
            return

        self.complete_timestamps.append(bar.timestamp)

        scores: dict[str, float] = {}
        for symbol in self.symbols:
            closes = self.get_history(count=self.lookback, symbol=symbol, field="close")
            if len(closes) < self.lookback:
                return
            scores[symbol] = float(closes[-1] / closes[0] - 1.0)

        best_symbol = max(scores, key=lambda symbol: scores[symbol])
        self.selected_symbols.append(best_symbol)

        for symbol in self.symbols:
            if symbol != best_symbol and self.get_position(symbol) > 0:
                self.close_position(symbol)
        self.order_target_percent(target_percent=0.8, symbol=best_symbol)


def _run_multisymbol_bucket(
    data_map: dict[str, pd.DataFrame], symbols: list[str]
) -> Any:
    return run_backtest(
        data=data_map,
        strategy=BucketCrossSectionStrategy,
        symbols=symbols,
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        lot_size=1,
        execution_mode="current_close",
        history_depth=2,
        show_progress=False,
    )


def test_multisymbol_bucket_rebalances_once_per_complete_timestamp() -> None:
    """Rebalance exactly once for each complete timestamp slice."""
    timestamps = [
        pd.Timestamp("2023-01-02 10:00:00", tz="Asia/Shanghai"),
        pd.Timestamp("2023-01-03 10:00:00", tz="Asia/Shanghai"),
        pd.Timestamp("2023-01-04 10:00:00", tz="Asia/Shanghai"),
        pd.Timestamp("2023-01-05 10:00:00", tz="Asia/Shanghai"),
    ]

    data_map = {
        "AAA": _build_symbol_df("AAA", timestamps, [10.0, 10.0, 10.0, 10.0]),
        "BBB": _build_symbol_df("BBB", timestamps, [10.0, 11.0, 12.0, 13.0]),
        "CCC": _build_symbol_df("CCC", timestamps, [10.0, 9.0, 8.0, 7.0]),
    }
    symbols = ["AAA", "BBB", "CCC"]

    result = _run_multisymbol_bucket(data_map, symbols)
    strategy = result.strategy

    assert len(strategy.complete_timestamps) == len(timestamps)
    assert all(len(v) == len(symbols) for v in strategy.seen_by_ts.values())
    assert strategy.selected_symbols == ["AAA", "BBB", "BBB", "BBB"]


def test_multisymbol_bucket_is_invariant_to_data_dict_order() -> None:
    """Keep cross-section outputs stable across dict insertion orders."""
    timestamps = [
        pd.Timestamp("2023-01-02 10:00:00", tz="Asia/Shanghai"),
        pd.Timestamp("2023-01-03 10:00:00", tz="Asia/Shanghai"),
        pd.Timestamp("2023-01-04 10:00:00", tz="Asia/Shanghai"),
        pd.Timestamp("2023-01-05 10:00:00", tz="Asia/Shanghai"),
    ]

    map_a = {
        "AAA": _build_symbol_df("AAA", timestamps, [10.0, 10.0, 10.0, 10.0]),
        "BBB": _build_symbol_df("BBB", timestamps, [10.0, 11.0, 12.0, 13.0]),
        "CCC": _build_symbol_df("CCC", timestamps, [10.0, 9.0, 8.0, 7.0]),
    }
    map_b = {
        "CCC": _build_symbol_df("CCC", timestamps, [10.0, 9.0, 8.0, 7.0]),
        "AAA": _build_symbol_df("AAA", timestamps, [10.0, 10.0, 10.0, 10.0]),
        "BBB": _build_symbol_df("BBB", timestamps, [10.0, 11.0, 12.0, 13.0]),
    }
    symbols = ["AAA", "BBB", "CCC"]

    result_a = _run_multisymbol_bucket(map_a, symbols)
    result_b = _run_multisymbol_bucket(map_b, symbols)

    strategy_a = result_a.strategy
    strategy_b = result_b.strategy

    assert strategy_a.complete_timestamps == strategy_b.complete_timestamps
    assert strategy_a.selected_symbols == strategy_b.selected_symbols


def test_multisymbol_bucket_skips_incomplete_timestamp() -> None:
    """Skip timestamps that are missing at least one symbol."""
    timestamps = [
        pd.Timestamp("2023-01-02 10:00:00", tz="Asia/Shanghai"),
        pd.Timestamp("2023-01-03 10:00:00", tz="Asia/Shanghai"),
        pd.Timestamp("2023-01-04 10:00:00", tz="Asia/Shanghai"),
        pd.Timestamp("2023-01-05 10:00:00", tz="Asia/Shanghai"),
    ]

    ccc_df = _build_symbol_df("CCC", timestamps, [10.0, 9.0, 8.0, 7.0]).drop(index=[1])

    data_map = {
        "AAA": _build_symbol_df("AAA", timestamps, [10.0, 10.0, 10.0, 10.0]),
        "BBB": _build_symbol_df("BBB", timestamps, [10.0, 11.0, 12.0, 13.0]),
        "CCC": ccc_df,
    }
    symbols = ["AAA", "BBB", "CCC"]

    result = _run_multisymbol_bucket(data_map, symbols)
    strategy = result.strategy

    assert len(strategy.complete_timestamps) == 3
    assert strategy.selected_symbols == ["AAA", "BBB", "BBB"]


def test_multisymbol_bucket_keeps_single_winner_position() -> None:
    """Keep at most one long position after each timestamp rebalance."""
    timestamps = [
        pd.Timestamp("2023-01-02 10:00:00", tz="Asia/Shanghai"),
        pd.Timestamp("2023-01-03 10:00:00", tz="Asia/Shanghai"),
        pd.Timestamp("2023-01-04 10:00:00", tz="Asia/Shanghai"),
        pd.Timestamp("2023-01-05 10:00:00", tz="Asia/Shanghai"),
    ]

    data_map = {
        "AAA": _build_symbol_df("AAA", timestamps, [10.0, 10.0, 10.0, 10.0]),
        "BBB": _build_symbol_df("BBB", timestamps, [10.0, 11.0, 12.0, 13.0]),
        "CCC": _build_symbol_df("CCC", timestamps, [10.0, 9.0, 8.0, 7.0]),
    }
    symbols = ["AAA", "BBB", "CCC"]

    result = _run_multisymbol_bucket(data_map, symbols)
    positions = result.positions
    positive_counts = (positions > 0).sum(axis=1)

    assert (positive_counts <= 1).all()


class TargetWeightsStrategy(Strategy):
    """Strategy for validating multi-symbol target weight rebalancing."""

    def __init__(self, symbols: list[str]) -> None:
        """Initialize state for staged rotation rebalancing."""
        super().__init__()
        self.symbols = symbols
        self.pending: dict[int, set[str]] = defaultdict(set)
        self.rebalance_count = 0

    def on_bar(self, bar: Bar) -> None:
        """Rebalance once all symbols of current timestamp are collected."""
        bucket = self.pending[bar.timestamp]
        bucket.add(bar.symbol)
        if len(bucket) < len(self.symbols):
            return
        self.pending.pop(bar.timestamp, None)

        if self.rebalance_count == 0:
            self.order_target_weights(
                {"AAA": 1.0},
                liquidate_unmentioned=True,
                rebalance_tolerance=0.0,
            )
        elif self.rebalance_count in (1, 2):
            self.order_target_weights(
                {"BBB": 1.0},
                liquidate_unmentioned=True,
                rebalance_tolerance=0.0,
            )
        self.rebalance_count += 1


class TargetWeightsSplitStrategy(Strategy):
    """Strategy for validating split target weights."""

    def __init__(self, symbols: list[str]) -> None:
        """Initialize state for one-shot split allocation."""
        super().__init__()
        self.symbols = symbols
        self.pending: dict[int, set[str]] = defaultdict(set)
        self.rebalanced = False

    def on_bar(self, bar: Bar) -> None:
        """Apply target split after timestamp bucket is complete."""
        bucket = self.pending[bar.timestamp]
        bucket.add(bar.symbol)
        if len(bucket) < len(self.symbols):
            return
        self.pending.pop(bar.timestamp, None)

        if not self.rebalanced:
            self.order_target_weights(
                {"AAA": 0.6, "BBB": 0.3},
                liquidate_unmentioned=True,
                rebalance_tolerance=0.0,
            )
            self.rebalanced = True


def test_order_target_weights_rotation_liquidates_unmentioned_symbols() -> None:
    """Target weights should support one-call rotation and clear old holdings."""
    timestamps = [
        pd.Timestamp("2023-01-02 10:00:00", tz="Asia/Shanghai"),
        pd.Timestamp("2023-01-03 10:00:00", tz="Asia/Shanghai"),
        pd.Timestamp("2023-01-04 10:00:00", tz="Asia/Shanghai"),
        pd.Timestamp("2023-01-05 10:00:00", tz="Asia/Shanghai"),
    ]
    data_map = {
        "AAA": _build_symbol_df("AAA", timestamps, [10.0, 10.0, 10.0, 10.0]),
        "BBB": _build_symbol_df("BBB", timestamps, [10.0, 10.0, 10.0, 10.0]),
    }

    result = run_backtest(
        data=data_map,
        strategy=TargetWeightsStrategy,
        symbols=["AAA", "BBB"],
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        lot_size=1,
        execution_mode="current_close",
        show_progress=False,
    )

    final_positions = result.positions.iloc[-1]
    assert float(final_positions.get("AAA", 0.0)) == 0.0
    assert float(final_positions.get("BBB", 0.0)) > 0.0


def test_order_target_weights_split_allocation_is_close_to_target() -> None:
    """Target weights should allocate multi-symbol positions by portfolio ratio."""
    timestamps = [
        pd.Timestamp("2023-01-02 10:00:00", tz="Asia/Shanghai"),
        pd.Timestamp("2023-01-03 10:00:00", tz="Asia/Shanghai"),
    ]
    data_map = {
        "AAA": _build_symbol_df("AAA", timestamps, [10.0, 10.0]),
        "BBB": _build_symbol_df("BBB", timestamps, [10.0, 10.0]),
    }

    result = run_backtest(
        data=data_map,
        strategy=TargetWeightsSplitStrategy,
        symbols=["AAA", "BBB"],
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        lot_size=1,
        execution_mode="current_close",
        show_progress=False,
    )

    final_positions = result.positions.iloc[-1]
    aaa_value = float(final_positions.get("AAA", 0.0)) * 10.0
    bbb_value = float(final_positions.get("BBB", 0.0)) * 10.0
    total_value = float(result.equity_curve.iloc[-1])

    assert abs(aaa_value / total_value - 0.6) < 0.02
    assert abs(bbb_value / total_value - 0.3) < 0.02


def _build_validation_strategy() -> Strategy:
    """Build strategy with minimal mock context for validation tests."""
    strategy = TargetWeightsSplitStrategy(symbols=["AAA", "BBB"])
    strategy.ctx = MagicMock()
    strategy.ctx.positions = {}
    strategy.ctx.cash = 100000.0
    strategy.ctx.get_position.return_value = 0.0
    return strategy


def test_order_target_weights_rejects_negative_tolerance() -> None:
    """Reject negative rebalance tolerance values."""
    strategy = _build_validation_strategy()
    with pytest.raises(ValueError, match="rebalance_tolerance must be >= 0"):
        strategy.order_target_weights({"AAA": 0.5}, rebalance_tolerance=-0.01)


def test_order_target_weights_rejects_weight_sum_over_one_without_leverage() -> None:
    """Reject total weights above one when leverage is disabled."""
    strategy = _build_validation_strategy()
    with pytest.raises(ValueError, match="exceeds 1.0"):
        strategy.order_target_weights({"AAA": 0.7, "BBB": 0.4})


def test_order_target_weights_rejects_negative_weight() -> None:
    """Reject negative target weight input."""
    strategy = _build_validation_strategy()
    with pytest.raises(ValueError, match="must be >= 0"):
        strategy.order_target_weights({"AAA": -0.1})


def test_order_target_weights_rejects_empty_symbol() -> None:
    """Reject empty symbol key in target weights."""
    strategy = _build_validation_strategy()
    with pytest.raises(ValueError, match="must be non-empty"):
        strategy.order_target_weights({"": 0.2})
