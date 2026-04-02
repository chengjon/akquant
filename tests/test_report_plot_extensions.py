import importlib.util
from pathlib import Path
from typing import cast

import pandas as pd
import pytest
from akquant import Bar, Strategy, run_backtest
from akquant.config import RiskConfig
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


class MarginLiquidationStrategy(Strategy):
    """Open a leveraged long to trigger forced liquidation on drawdown."""

    def __init__(self) -> None:
        """Initialize one-shot order flag."""
        super().__init__()
        self.ordered = False

    def on_bar(self, bar: Bar) -> None:
        """Buy once with leverage-like sizing."""
        if not self.ordered:
            self.buy(symbol=bar.symbol, quantity=150)
            self.ordered = True


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


def _build_intraday_data(symbol: str = "TEST") -> list[Bar]:
    data: list[Bar] = []
    timestamps = [
        pd.Timestamp("2023-01-01 10:00:00"),
        pd.Timestamp("2023-01-01 14:00:00"),
        pd.Timestamp("2023-01-02 10:00:00"),
    ]
    closes = [10.0, 10.5, 11.0]
    for ts, close in zip(timestamps, closes):
        data.append(
            Bar(
                timestamp=ts.value,
                open=close,
                high=close + 0.2,
                low=close - 0.2,
                close=close,
                volume=10000.0,
                symbol=symbol,
            )
        )
    return data


def _build_market_df(symbol: str = "TEST", n: int = 5) -> pd.DataFrame:
    rows = []
    for bar in _build_data(symbol=symbol, n=n):
        rows.append(
            {
                "timestamp": pd.Timestamp(bar.timestamp),
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "symbol": bar.symbol,
            }
        )
    df = pd.DataFrame(rows)
    df = df.set_index("timestamp")
    return cast(pd.DataFrame, df)


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
        symbols="TEST",
        initial_cash=200000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        fill_policy={"price_basis": "close", "temporal": "same_cycle"},
        lot_size=1,
        show_progress=False,
    )

    report_path = tmp_path / "report_with_analysis.html"
    result.report(filename=str(report_path), show=False)
    html = report_path.read_text(encoding="utf-8")
    assert "组合归因与容量分析 (Attribution & Capacity)" in html
    assert "最新净暴露比 (Latest Net Exposure %)" in html
    assert "平均换手率 (Avg Turnover)" in html
    assert "策略风控拒单明细 (Risk Rejections by Strategy)" in html
    assert "暂无策略归属风控拒单聚合数据" in html
    assert "未提供行情数据，已跳过 K 线复盘图" in html


def test_report_includes_trade_kline_with_market_data(tmp_path: Path) -> None:
    """Report HTML should embed K-line trade replay when market data is passed."""
    _skip_if_no_plotly()
    result = run_backtest(
        data=_build_data(),
        strategy=RoundTripStrategy,
        symbols="TEST",
        initial_cash=200000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        fill_policy={"price_basis": "close", "temporal": "same_cycle"},
        lot_size=1,
        show_progress=False,
    )

    report_path = tmp_path / "report_with_trade_kline.html"
    result.report(
        filename=str(report_path),
        show=False,
        market_data=_build_market_df(symbol="TEST"),
        plot_symbol="TEST",
    )
    html = report_path.read_text(encoding="utf-8")
    assert "交易复盘 (K线买卖点)" in html
    assert "Strategy Analysis: TEST" in html
    assert "entry" in html
    assert "exit" in html


def test_report_includes_benchmark_comparison_sections(tmp_path: Path) -> None:
    """Report HTML should include benchmark metrics and cumulative comparison chart."""
    _skip_if_no_plotly()
    result = run_backtest(
        data=_build_data(),
        strategy=RoundTripStrategy,
        symbols="TEST",
        initial_cash=200000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        fill_policy={"price_basis": "close", "temporal": "same_cycle"},
        lot_size=1,
        show_progress=False,
    )
    benchmark_idx = pd.date_range("2023-01-01", periods=5, freq="D", tz="Asia/Shanghai")
    benchmark_returns = pd.Series(
        [0.0, 0.001, -0.0005, 0.0008, 0.0],
        index=benchmark_idx,
        name="CSI300",
    )
    report_path = tmp_path / "report_with_benchmark.html"
    result.report(
        filename=str(report_path),
        show=False,
        benchmark=benchmark_returns,
    )
    html = report_path.read_text(encoding="utf-8")
    assert "基准对比 (Benchmark Comparison)" in html
    assert "累计超额收益 (Total Excess)" in html
    assert "信息比率 (Information Ratio)" in html
    assert "Cumulative Return Comparison" in html
    assert "CSI300" in html


def test_report_handles_string_benchmark_with_notice(tmp_path: Path) -> None:
    """Report should render benchmark section notice when benchmark is ticker string."""
    _skip_if_no_plotly()
    result = run_backtest(
        data=_build_data(),
        strategy=NoTradeStrategy,
        symbols="TEST",
        initial_cash=200000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        fill_policy={"price_basis": "close", "temporal": "same_cycle"},
        lot_size=1,
        show_progress=False,
    )
    report_path = tmp_path / "report_with_benchmark_string.html"
    result.report(
        filename=str(report_path),
        show=False,
        benchmark="000300.SH",
    )
    html = report_path.read_text(encoding="utf-8")
    assert "基准对比 (Benchmark Comparison)" in html
    assert "未生成基准对比: 暂不支持自动拉取基准: 000300.SH" in html


def test_report_handles_empty_trade_analysis_blocks(tmp_path: Path) -> None:
    """Report should still render when there are no trades."""
    _skip_if_no_plotly()
    result = run_backtest(
        data=_build_data(),
        strategy=NoTradeStrategy,
        symbols="TEST",
        initial_cash=200000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        fill_policy={"price_basis": "close", "temporal": "same_cycle"},
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
        symbols="TEST",
        initial_cash=200000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        fill_policy={"price_basis": "close", "temporal": "same_cycle"},
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


def test_daily_curve_properties_reduce_intraday_points() -> None:
    """Daily curve properties should downsample intraday points to day-end."""
    result = run_backtest(
        data=_build_intraday_data(),
        strategy=NoTradeStrategy,
        symbols="TEST",
        initial_cash=200000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        fill_policy={"price_basis": "close", "temporal": "same_cycle"},
        lot_size=1,
        show_progress=False,
    )

    assert len(result.equity_curve) == 3
    assert len(result.cash_curve) == 3
    assert len(result.margin_curve) == 3
    assert len(result.equity_curve_daily) == 2
    assert len(result.cash_curve_daily) == 2
    assert len(result.margin_curve_daily) == 2


def test_report_accepts_curve_freq_daily(tmp_path: Path) -> None:
    """Report generation should support daily curve frequency mode."""
    _skip_if_no_plotly()
    result = run_backtest(
        data=_build_intraday_data(),
        strategy=NoTradeStrategy,
        symbols="TEST",
        initial_cash=200000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        fill_policy={"price_basis": "close", "temporal": "same_cycle"},
        lot_size=1,
        show_progress=False,
    )
    report_path = tmp_path / "report_curve_freq_daily.html"
    result.report(filename=str(report_path), show=False, curve_freq="D")
    assert report_path.exists()


def test_report_rejects_invalid_curve_freq(tmp_path: Path) -> None:
    """Report generation should reject unsupported curve frequency values."""
    _skip_if_no_plotly()
    result = run_backtest(
        data=_build_intraday_data(),
        strategy=NoTradeStrategy,
        symbols="TEST",
        initial_cash=200000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        fill_policy={"price_basis": "close", "temporal": "same_cycle"},
        lot_size=1,
        show_progress=False,
    )
    report_path = tmp_path / "report_curve_freq_invalid.html"
    with pytest.raises(ValueError):
        result.report(filename=str(report_path), show=False, curve_freq="W")


def test_report_contains_forced_liquidation_audit_section(tmp_path: Path) -> None:
    """Report HTML should include forced liquidation audit section and entries."""
    _skip_if_no_plotly()
    bars = [
        Bar(
            timestamp=pd.Timestamp("2023-01-01 10:00:00").value,
            open=100.0,
            high=100.2,
            low=99.8,
            close=100.0,
            volume=10000.0,
            symbol="LIQ",
        ),
        Bar(
            timestamp=pd.Timestamp("2023-01-01 14:00:00").value,
            open=20.0,
            high=20.2,
            low=19.8,
            close=20.0,
            volume=10000.0,
            symbol="LIQ",
        ),
        Bar(
            timestamp=pd.Timestamp("2023-01-02 10:00:00").value,
            open=20.0,
            high=20.2,
            low=19.8,
            close=20.0,
            volume=10000.0,
            symbol="LIQ",
        ),
    ]
    result = run_backtest(
        data=bars,
        strategy=MarginLiquidationStrategy,
        symbols="LIQ",
        initial_cash=10000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        fill_policy={"price_basis": "close", "temporal": "same_cycle"},
        lot_size=1,
        show_progress=False,
        risk_config=RiskConfig(
            account_mode="margin",
            initial_margin_ratio=0.5,
            maintenance_margin_ratio=0.5,
            financing_rate_annual=0.0,
            borrow_rate_annual=0.0,
            allow_force_liquidation=True,
            liquidation_priority="short_first",
        ),
    )
    report_path = tmp_path / "report_with_liquidation_audit.html"
    result.report(filename=str(report_path), show=False)
    html = report_path.read_text(encoding="utf-8")
    assert "强平审计明细 (Forced Liquidation Audit)" in html
    assert "强平标的 (Liquidated Symbols)" in html
    assert "LIQ" in html
