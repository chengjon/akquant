"""Consolidated report generation module."""

import base64
import datetime
from typing import TYPE_CHECKING, Any, Optional, Union, cast

import pandas as pd

from ._chart_builder import _build_chart_html_sections  # noqa: F401
from ._svg_assets import AKQUANT_ICON_SVG, AKQUANT_LOGO_SVG, HTML_TEMPLATE  # noqa: F401
from ._table_builder import (  # noqa: F401
    _build_analysis_table_sections,
    _build_benchmark_sections,
    _build_metrics_html,
    _get_metric_value,
)
from .comparison import plot_comparison
from .utils import check_plotly

if TYPE_CHECKING:
    from ..backtest import BacktestResult


def _format_currency(value: float) -> str:
    """Format large numbers nicely."""
    sign = "-" if value < 0 else ""
    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        return f"{sign}{abs_value / 1_000_000_000:.2f}B"
    elif abs_value >= 1_000_000:
        return f"{sign}{abs_value / 1_000_000:.2f}M"
    elif abs_value >= 1_000:
        return f"{sign}{abs_value / 1_000:.2f}K"
    else:
        return f"{value:.2f}"


def _format_table(
    df: pd.DataFrame,
    max_rows: int = 10,
    percentage_columns: set[str] | None = None,
    compact_currency_columns: set[str] | None = None,
    compact_currency: bool = True,
) -> str:
    """Render a compact HTML table from a dataframe."""
    if df.empty:
        return "<div>暂无数据</div>"
    table = df.head(max_rows).copy()
    pct_cols = percentage_columns or set()
    money_cols = compact_currency_columns or set()
    for col in table.columns:
        if pd.api.types.is_float_dtype(table[col]):
            if col in pct_cols:
                table[col] = table[col].map(lambda x: f"{x * 100:,.6f}%")
            elif compact_currency and col in money_cols:
                table[col] = table[col].map(lambda x: f"{_format_currency(x)}")
            else:
                table[col] = table[col].map(lambda x: f"{x:,.6f}")
    table_html = table.to_html(index=False, border=0, classes="table")
    return f'<div class="table-scroll">{table_html}</div>'


def _rename_table_columns(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """Rename technical columns to user-friendly labels."""
    renamed = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})
    return cast(pd.DataFrame, renamed)


def _normalize_curve_freq(curve_freq: str) -> str:
    """Normalize curve frequency option."""
    value = str(curve_freq).strip()
    if value.lower() == "raw":
        return "raw"
    if value.upper() == "D":
        return "D"
    raise ValueError("curve_freq must be 'raw' or 'D'")


def _resolve_equity_curve(result: Any, curve_freq: str) -> pd.Series:
    """Resolve equity curve for report rendering."""
    if curve_freq == "D" and hasattr(result, "equity_curve_daily"):
        series = cast(pd.Series, result.equity_curve_daily)
        if not series.empty:
            return series
    return cast(pd.Series, result.equity_curve)


def _build_daily_returns_from_equity(equity_curve: pd.Series) -> pd.Series:
    """Build daily returns from equity curve."""
    if equity_curve.empty:
        return pd.Series(dtype=float)
    daily_equity = equity_curve.resample("D").last().ffill()
    returns = daily_equity.pct_change().fillna(0.0)
    return cast(pd.Series, returns)


def _normalize_returns_series(series: pd.Series) -> pd.Series:
    """Normalize return series index to timezone-naive daily datetime index."""
    cleaned = series.copy()
    cleaned = pd.to_numeric(cleaned, errors="coerce")
    cleaned = cast(pd.Series, cleaned.dropna())
    if cleaned.empty:
        return cast(pd.Series, cleaned)
    index = pd.to_datetime(cleaned.index, errors="coerce")
    valid_mask = pd.Series(index).notna().to_numpy()
    cleaned = cleaned.loc[valid_mask].copy()
    index = index[valid_mask]
    dt_index = cast(pd.DatetimeIndex, index)
    if dt_index.tz is not None:
        dt_index = dt_index.tz_convert("UTC").tz_localize(None)
    cleaned.index = dt_index.normalize()
    cleaned = cast(pd.Series, cleaned.groupby(cleaned.index).last())
    cleaned = cast(pd.Series, cleaned.sort_index())
    return cleaned


def _resolve_benchmark_returns(
    benchmark: Optional[Union[str, pd.Series]], strategy_returns: pd.Series
) -> tuple[Optional[pd.Series], str]:
    """Resolve benchmark input into aligned return series and display label."""
    if benchmark is None:
        return None, "未提供基准"
    if isinstance(benchmark, str):
        return None, f"暂不支持自动拉取基准: {benchmark}"
    if not isinstance(benchmark, pd.Series):
        return None, "基准类型错误，需为 pd.Series 或 str"
    benchmark_label = (
        str(benchmark.name)
        if benchmark.name is not None and str(benchmark.name).strip()
        else "Benchmark"
    )
    benchmark_series = _normalize_returns_series(benchmark)
    if benchmark_series.empty:
        return None, f"基准序列为空: {benchmark_label}"
    quantile_95 = float(benchmark_series.abs().quantile(0.95))
    if quantile_95 > 2.0:
        benchmark_series = cast(pd.Series, benchmark_series.pct_change().fillna(0.0))
    strategy_series = _normalize_returns_series(strategy_returns)
    if strategy_series.empty:
        return None, f"策略收益为空，无法对齐基准: {benchmark_label}"
    aligned = cast(
        pd.Series,
        benchmark_series.reindex(strategy_series.index).fillna(0.0).astype(float),
    )
    if aligned.empty:
        return None, f"策略与基准无重叠区间: {benchmark_label}"
    return aligned, benchmark_label


def _build_summary_context(result: Any, curve_freq: str = "raw") -> dict[str, str]:
    """Build summary text values for report header."""
    equity_curve = _resolve_equity_curve(result, curve_freq)
    start_date = "N/A"
    end_date = "N/A"
    duration_str = "N/A"
    final_equity_str = "N/A"
    initial_cash_str = (
        f"{result.initial_cash:,.2f}" if hasattr(result, "initial_cash") else "N/A"
    )

    if not equity_curve.empty:
        start_ts = equity_curve.index[0]
        end_ts = equity_curve.index[-1]
        start_date = start_ts.strftime("%Y-%m-%d")
        end_date = end_ts.strftime("%Y-%m-%d")
        duration_str = f"{(end_ts - start_ts).days} 天"
        final_equity_str = f"{equity_curve.iloc[-1]:,.2f}"

    return {
        "start_date": start_date,
        "end_date": end_date,
        "duration_str": duration_str,
        "initial_cash": initial_cash_str,
        "final_equity": final_equity_str,
    }


def plot_report(
    result: "BacktestResult",
    title: str = "AKQuant 策略回测报告",
    filename: str = "akquant_report.html",
    show: bool = False,
    compact_currency: bool = True,
    market_data: Optional[Union[pd.DataFrame, dict[str, pd.DataFrame]]] = None,
    plot_symbol: Optional[str] = None,
    include_trade_kline: bool = True,
    benchmark: Optional[Union[str, pd.Series]] = None,
    curve_freq: str = "raw",
    comparison_results: Optional[list[Any]] = None,
    comparison_labels: Optional[list[str]] = None,
) -> None:
    """
    生成类似 QuantStats 的整合版 HTML 报告 (中文优化版).

    内容包括:
    1. 核心指标概览 (Key Metrics)
    2. 权益曲线、回撤、月度热力图 (Dashboard)
    3. 交易分布与持仓时间分析 (Trade Analysis)

    :param compact_currency: 是否将金额列按 K/M/B 紧凑显示
    :param benchmark: 基准收益序列 (pd.Series) 或基准标识字符串
    :param curve_freq: 曲线频率，"raw" 为原始频率，"D" 为日频末值
    """
    if not check_plotly():
        return
    normalized_curve_freq = _normalize_curve_freq(curve_freq)

    # Prepare Icon
    icon_b64 = base64.b64encode(AKQUANT_ICON_SVG.encode("utf-8")).decode("utf-8")
    favicon_uri = f"data:image/svg+xml;base64,{icon_b64}"

    summary_context = _build_summary_context(result, curve_freq=normalized_curve_freq)
    metrics_html = _build_metrics_html(result)
    chart_sections = _build_chart_html_sections(
        result=result,
        market_data=market_data,
        plot_symbol=plot_symbol,
        include_trade_kline=include_trade_kline,
        benchmark=benchmark,
        curve_freq=normalized_curve_freq,
    )
    analysis_sections = _build_analysis_table_sections(
        result, compact_currency=compact_currency
    )

    comparison_section_html = ""
    if comparison_results:
        all_results = [result] + list(comparison_results)
        default_labels = [f"Strategy {i + 1}" for i in range(len(all_results))]
        all_labels = comparison_labels or default_labels
        if len(all_labels) != len(all_results):
            all_labels = default_labels
        fig_comparison = plot_comparison(
            all_results, labels=all_labels, theme="light", show=False,
        )
        if fig_comparison:
            cmp_config = {"responsive": True}
            cmp_html = fig_comparison.to_html(
                full_html=False, include_plotlyjs=False, config=cmp_config,
            )
            comparison_section_html = (
                '<div class="section-title">'
                '策略对比 (Strategy Comparison)</div>'
                f'<div class="chart-container">{cmp_html}</div>'
            )

    # 4. Assemble HTML
    html_content = HTML_TEMPLATE.format(
        title=title,
        favicon_uri=favicon_uri,
        icon_svg=AKQUANT_LOGO_SVG,
        date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        start_date=summary_context["start_date"],
        end_date=summary_context["end_date"],
        duration_str=summary_context["duration_str"],
        initial_cash=summary_context["initial_cash"],
        final_equity=summary_context["final_equity"],
        metrics_html=metrics_html,
        comparison_section_html=comparison_section_html,
        dashboard_html=chart_sections["dashboard_html"],
        yearly_returns_html=chart_sections["yearly_returns_html"],
        returns_dist_html=chart_sections["returns_dist_html"],
        rolling_metrics_html=chart_sections["rolling_metrics_html"],
        benchmark_metrics_html=chart_sections["benchmark_metrics_html"],
        benchmark_chart_html=chart_sections["benchmark_chart_html"],
        trades_dist_html=chart_sections["trades_dist_html"],
        pnl_duration_html=chart_sections["pnl_duration_html"],
        strategy_kline_html=chart_sections["strategy_kline_html"],
        risk_reject_ratio_html=chart_sections["risk_reject_ratio_html"],
        risk_reason_ratio_html=chart_sections["risk_reason_ratio_html"],
        risk_reject_trend_html=chart_sections["risk_reject_trend_html"],
        risk_reject_trend_by_strategy_html=chart_sections[
            "risk_reject_trend_by_strategy_html"
        ],
        risk_reason_trend_html=chart_sections["risk_reason_trend_html"],
        analysis_overview_html=analysis_sections["analysis_overview_html"],
        exposure_summary_html=analysis_sections["exposure_summary_html"],
        capacity_summary_html=analysis_sections["capacity_summary_html"],
        attribution_summary_html=analysis_sections["attribution_summary_html"],
        orders_by_strategy_html=analysis_sections["orders_by_strategy_html"],
        executions_by_strategy_html=analysis_sections["executions_by_strategy_html"],
        risk_by_strategy_html=analysis_sections["risk_by_strategy_html"],
        liquidation_audit_html=analysis_sections["liquidation_audit_html"],
        risk_charts_html=chart_sections["risk_charts_html"],
    )

    # 5. Save File
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Report saved to: {filename}")

        if show:
            import os
            import webbrowser

            webbrowser.open(f"file://{os.path.abspath(filename)}")

    except Exception as e:
        print(f"Error saving report: {e}")
