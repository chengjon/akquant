"""Strategy comparison plotting module."""

from typing import TYPE_CHECKING, List, Optional

import numpy as np
import pandas as pd

from .utils import check_plotly, get_color, go, make_subplots

if TYPE_CHECKING:
    from ..backtest import BacktestResult


def _normalize_equity(series: pd.Series) -> pd.Series:
    """Normalize equity curve to start at 1.0."""
    if series.empty:
        return series
    first_valid = series.iloc[0]
    if first_valid == 0:
        return series
    return series / first_valid


def _compute_drawdown(equity: pd.Series) -> pd.Series:
    """Compute drawdown from equity curve."""
    if equity.empty:
        return equity
    peak = equity.cummax()
    return (equity - peak) / peak


def _build_metrics_row(
    result: "BacktestResult",
) -> dict[str, str]:
    """Extract key metrics for comparison table."""
    metrics = result.metrics
    total_return = getattr(metrics, "total_return_pct", float("nan"))
    cagr = getattr(metrics, "annualized_return", float("nan"))
    sharpe = getattr(metrics, "sharpe_ratio", float("nan"))
    max_dd = getattr(metrics, "max_drawdown_pct", float("nan"))
    win_rate = getattr(metrics, "win_rate", float("nan"))
    volatility = getattr(metrics, "volatility", float("nan"))
    trade_count = len(result.trades_df) if hasattr(result, "trades_df") else 0

    return {
        "total_return": f"{total_return:.2%}" if not np.isnan(total_return) else "N/A",
        "cagr": f"{cagr:.2%}" if not np.isnan(cagr) else "N/A",
        "sharpe": f"{sharpe:.2f}" if not np.isnan(sharpe) else "N/A",
        "max_dd": f"{max_dd:.2%}" if not np.isnan(max_dd) else "N/A",
        "win_rate": f"{win_rate:.2%}" if not np.isnan(win_rate) else "N/A",
        "volatility": f"{volatility:.2%}" if not np.isnan(volatility) else "N/A",
        "trades": f"{trade_count}",
    }


def plot_comparison(
    results: List["BacktestResult"],
    labels: Optional[List[str]] = None,
    title: str = "策略对比 (Strategy Comparison)",
    theme: str = "light",
    show: bool = True,
    filename: Optional[str] = None,
) -> Optional["go.Figure"]:
    """Plot strategy comparison panel.

    Row 1: Normalized equity curves overlay.
    Row 2: Drawdown comparison.
    Row 3: Metrics comparison table (via annotations).

    Args:
        results: List of BacktestResult objects.
        labels: Strategy labels (defaults to Strategy 1, 2, ...).
        title: Chart title.
        theme: "light" or "dark".
        show: Whether to show the plot.
        filename: File path to save.
    """
    if not check_plotly():
        return None

    if not results:
        print("No results provided for comparison.")
        return None

    if labels is None:
        labels = [f"Strategy {i + 1}" for i in range(len(results))]

    if len(labels) != len(results):
        print("Number of labels must match number of results.")
        return None

    colors = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
        "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
    ]

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.45, 0.30, 0.25],
        subplot_titles=(
            "归一化权益 (Normalized Equity)",
            "回撤对比 (Drawdown Comparison)",
            "核心指标对比 (Key Metrics)",
        ),
        specs=[
            [{"secondary_y": False}],
            [{"secondary_y": False}],
            [{"type": "table"}],
        ],
    )

    metrics_rows: list[dict[str, str]] = []
    has_any_data = False

    for i, (result, label) in enumerate(zip(results, labels)):
        color = colors[i % len(colors)]
        equity = result.equity_curve

        if equity.empty:
            continue
        has_any_data = True

        norm_equity = _normalize_equity(equity)
        drawdown = _compute_drawdown(equity)

        TraceType = go.Scattergl if len(norm_equity) > 10000 else go.Scatter

        fig.add_trace(
            TraceType(
                x=norm_equity.index,
                y=norm_equity.fillna(1.0).tolist(),
                mode="lines",
                name=label,
                line=dict(color=color, width=2),
            ),
            row=1,
            col=1,
        )

        fig.add_trace(
            TraceType(
                x=drawdown.index,
                y=drawdown.fillna(0.0).tolist(),
                mode="lines",
                name=f"{label} DD",
                line=dict(color=color, width=1, dash="dash"),
                showlegend=False,
            ),
            row=2,
            col=1,
        )

        row_metrics = _build_metrics_row(result)
        row_metrics["strategy"] = label
        metrics_rows.append(row_metrics)

    if not has_any_data:
        print("No equity curve data available in any result.")
        return None

    # Metrics table
    if metrics_rows:
        header_vals = [
            "策略 (Strategy)",
            "累计收益 (Total)",
            "年化 (CAGR)",
            "夏普 (Sharpe)",
            "最大回撤 (Max DD)",
            "胜率 (Win Rate)",
            "波动率 (Vol)",
            "交易数 (Trades)",
        ]
        cell_vals = [
            [r["strategy"] for r in metrics_rows],
            [r["total_return"] for r in metrics_rows],
            [r["cagr"] for r in metrics_rows],
            [r["sharpe"] for r in metrics_rows],
            [r["max_dd"] for r in metrics_rows],
            [r["win_rate"] for r in metrics_rows],
            [r["volatility"] for r in metrics_rows],
            [r["trades"] for r in metrics_rows],
        ]

        fig.add_trace(
            go.Table(
                header=dict(
                    values=header_vals,
                    fill_color=get_color(theme, "bg_color"),
                    font=dict(color=get_color(theme, "text_color"), size=12),
                    align="center",
                    height=30,
                ),
                cells=dict(
                    values=cell_vals,
                    fill_color="#ffffff",
                    font=dict(color=get_color(theme, "text_color"), size=11),
                    align="center",
                    height=25,
                ),
            ),
            row=3,
            col=1,
        )

    # Layout
    bg_color = get_color(theme, "bg_color")
    text_color = get_color(theme, "text_color")
    grid_color = get_color(theme, "grid_color")

    fig.update_yaxes(tickformat=".2f", row=1, col=1)
    fig.update_yaxes(tickformat=".2%", row=2, col=1)
    fig.update_xaxes(gridcolor=grid_color)
    fig.update_yaxes(gridcolor=grid_color)

    fig.update_layout(
        title=dict(text=title),
        height=900,
        template="plotly_white" if theme == "light" else "plotly_dark",
        plot_bgcolor=bg_color,
        paper_bgcolor=bg_color,
        font=dict(color=text_color),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
        ),
        margin=dict(t=100, b=50, l=60, r=30),
    )

    if filename:
        if filename.endswith(".html"):
            fig.write_html(filename)
        else:
            fig.write_image(filename)

    if show:
        fig.show()

    return fig
