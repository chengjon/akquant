from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from akquant.plot.comparison import plot_comparison


def _make_result(equity_values: list[float]) -> MagicMock:
    """Create a mock BacktestResult with equity curve and metrics."""
    result = MagicMock()
    idx = pd.date_range("2024-01-01", periods=len(equity_values), freq="D")
    result.equity_curve = pd.Series(equity_values, index=idx)
    metrics = MagicMock()
    metrics.total_return_pct = (equity_values[-1] / equity_values[0] - 1) if equity_values[0] != 0 else 0
    metrics.annualized_return = metrics.total_return_pct
    metrics.sharpe_ratio = 1.5
    metrics.max_drawdown_pct = -0.1
    metrics.win_rate = 0.6
    metrics.volatility = 0.15
    result.metrics = metrics
    result.trades_df = pd.DataFrame({"pnl": [1.0, -0.5]})
    return result


class TestPlotComparison:
    """Strategy comparison panel tests."""

    def test_basic_two_strategies(self) -> None:
        """Two strategies produce figure with overlay."""
        r1 = _make_result([100, 110, 120, 130])
        r2 = _make_result([100, 95, 105, 115])
        fig = plot_comparison([r1, r2], labels=["A", "B"], show=False)
        assert fig is not None

    def test_empty_results_list(self) -> None:
        """Empty results list returns None."""
        assert plot_comparison([], show=False) is None

    def test_label_count_mismatch(self) -> None:
        """Mismatched label count returns None."""
        r1 = _make_result([100, 110])
        assert plot_comparison([r1], labels=["A", "B"], show=False) is None

    def test_empty_equity_curve(self) -> None:
        """Result with empty equity curve returns None."""
        r = _make_result([100])
        r.equity_curve = pd.Series(dtype=float)
        assert plot_comparison([r], show=False) is None

    def test_single_strategy(self) -> None:
        """Single strategy comparison works."""
        r = _make_result([100, 105, 110])
        fig = plot_comparison([r], show=False)
        assert fig is not None

    def test_default_labels(self) -> None:
        """Default labels are generated when none provided."""
        r1 = _make_result([100, 110])
        r2 = _make_result([100, 90])
        fig = plot_comparison([r1, r2], show=False)
        assert fig is not None
