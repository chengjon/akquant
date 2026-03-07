import importlib.util
from pathlib import Path

import pandas as pd
import pytest
from akquant import Bar, Strategy, run_backtest
from akquant.plot import (
    plot_dashboard,
    plot_pnl_vs_duration,
    plot_trades_distribution,
)
from akquant.plot.analysis import plot_returns_distribution, plot_rolling_metrics


class RoundTripStrategy(Strategy):
    """Generate one round-trip trade for report and plot checks."""

    def __init__(self) -> None:
        """Initialize internal step counter."""
        super().__init__()
        self.step = 0

    def on_bar(self, bar: Bar) -> None:
        """Buy once and sell once."""
        self.step += 1
        if self.step == 1:
            self.buy(symbol=bar.symbol, quantity=100, tag="entry")
        elif self.step == 3:
            self.sell(symbol=bar.symbol, quantity=100, tag="exit")


class NoTradeStrategy(Strategy):
    """Produce no trades for empty-trade report branch."""

    def on_bar(self, bar: Bar) -> None:
        """Do nothing on each bar."""
        _ = bar


def _build_data(symbol: str = "TEST", n: int = 5) -> list[Bar]:
    """Build deterministic daily bars."""
    data: list[Bar] = []
    for i in range(n):
        close = 10.0 + i
        data.append(
            Bar(
                timestamp=pd.Timestamp(f"2023-01-{i + 1:02d} 10:00:00").value,
                open=close,
                high=close + 0.2,
                low=close - 0.2,
                close=close,
                volume=10000.0,
                symbol=symbol,
            )
        )
    return data


def _skip_if_no_plotly() -> None:
    """Skip tests if plotly is unavailable."""
    if importlib.util.find_spec("plotly") is None:
        pytest.skip("plotly is required for report/plot tests")


def test_report_contains_new_analysis_sections(tmp_path: Path) -> None:
    """Report HTML should include attribution and capacity sections."""
    _skip_if_no_plotly()
    result = run_backtest(
        data=_build_data(),
        strategy=RoundTripStrategy,
        symbol="TEST",
        initial_cash=200000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
    )

    report_path = tmp_path / "report_with_analysis.html"
    result.report(filename=str(report_path), show=False)
    html = report_path.read_text(encoding="utf-8")
    assert "组合归因与容量分析 (Attribution & Capacity)" in html
    assert "最新净暴露比 (Latest Net Exposure %)" in html
    assert "平均换手率 (Avg Turnover)" in html
    assert "暂无策略级风控拒单占比图" in html
    assert "暂无策略级拒单原因占比图" in html
    assert "暂无按日风控拒单趋势图" in html
    assert "暂无按策略风控拒单趋势图" in html
    assert "暂无按日拒单原因趋势图" in html


def test_report_handles_empty_trade_analysis_blocks(tmp_path: Path) -> None:
    """Report should still render when there are no trades."""
    _skip_if_no_plotly()
    result = run_backtest(
        data=_build_data(),
        strategy=NoTradeStrategy,
        symbol="TEST",
        initial_cash=200000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
    )

    report_path = tmp_path / "report_empty_trades.html"
    result.report(filename=str(report_path), show=False)
    html = report_path.read_text(encoding="utf-8")
    assert "暂无归因数据" in html


def test_plot_functions_return_figures_for_non_empty_result() -> None:
    """Core plot functions should return figures for non-empty inputs."""
    _skip_if_no_plotly()
    result = run_backtest(
        data=_build_data(),
        strategy=RoundTripStrategy,
        symbol="TEST",
        initial_cash=200000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        execution_mode="current_close",
        lot_size=1,
        show_progress=False,
    )

    fig_dashboard = plot_dashboard(result, show=False)
    assert fig_dashboard is not None
    fig_trades = plot_trades_distribution(result.trades_df)
    assert fig_trades is not None
    fig_duration = plot_pnl_vs_duration(result.trades_df)
    assert fig_duration is not None
    fig_rolling = plot_rolling_metrics(result.daily_returns)
    assert fig_rolling is not None
    fig_returns = plot_returns_distribution(result.daily_returns)
    assert fig_returns is not None
