"""Consolidated report generation module."""

import base64
import datetime
from typing import TYPE_CHECKING, Any, cast

import pandas as pd

from .analysis import (
    plot_pnl_vs_duration,
    plot_returns_distribution,
    plot_rolling_metrics,
    plot_trades_distribution,
    plot_yearly_returns,
)
from .dashboard import plot_dashboard
from .utils import check_plotly

if TYPE_CHECKING:
    from ..backtest import BacktestResult

# Embedded SVG Icon
AKQUANT_ICON_SVG = """<svg width="100" height="100" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <g transform="translate(17, 25)">
    <rect x="0" y="40" width="15" height="30" rx="4" fill="#CE412B" />
    <rect x="25" y="20" width="15" height="50" rx="4" fill="#BE5C60" />
    <rect x="50" y="0" width="15" height="70" rx="4" fill="#3776AB" />
    <circle cx="7" cy="30" r="2" fill="#CE412B" />
    <circle cx="32" cy="10" r="2" fill="#BE5C60" />
    <circle cx="57" cy="-10" r="2" fill="#3776AB" />
  </g>
</svg>"""

# Embedded SVG Logo
AKQUANT_LOGO_SVG = """<svg width="400" height="120" viewBox="0 0 400 120" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="textGradient" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#CE412B;stop-opacity:1" />
      <!-- Rust Orange -->
      <stop offset="100%" style="stop-color:#3776AB;stop-opacity:1" />
      <!-- Python Blue -->
    </linearGradient>
  </defs>

  <!-- Graphic: Quant Signal Bars (Ascending Data Spectrum) -->
  <g transform="translate(30, 25)">
    <!-- Bar 1: Low (Foundation/Data - Rust Color) -->
    <rect x="0" y="40" width="15" height="30" rx="4" fill="#CE412B" />

    <!-- Bar 2: Mid (Processing/Strategy - Blend) -->
    <rect x="25" y="20" width="15" height="50" rx="4" fill="#BE5C60" />

    <!-- Bar 3: High (Alpha/Profit - Python Color) -->
    <rect x="50" y="0" width="15" height="70" rx="4" fill="#3776AB" />

    <!-- Abstract Data Dots -->
    <circle cx="7" cy="30" r="2" fill="#CE412B" />
    <circle cx="32" cy="10" r="2" fill="#BE5C60" />
    <circle cx="57" cy="-10" r="2" fill="#3776AB" />
  </g>

  <!-- Text -->
  <text x="110" y="75"
        font-family="'Segoe UI', Helvetica, Arial, sans-serif"
        font-size="60"
        font-weight="bold"
        fill="url(#textGradient)">AKQuant</text>

  <!-- Subtitle -->
  <text x="115" y="100"
        font-family="'Segoe UI', Helvetica, Arial, sans-serif"
        font-size="14"
        fill="#666">High-Performance Quant Framework</text>
</svg>"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <link rel="icon" href="{favicon_uri}">
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <style>
        :root {{
            --primary-color: #2c3e50;
            --accent-color: #3498db;
            --bg-color: #f5f7fa;
            --card-bg: #ffffff;
            --text-color: #333333;
            --text-secondary: #7f8c8d;
            --border-color: #e1e4e8;
            --success-color: #27ae60;
            --danger-color: #c0392b;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                "Helvetica Neue", Arial, "PingFang SC", "Hiragino Sans GB",
                "Microsoft YaHei", sans-serif;
            margin: 0;
            padding: 20px;
            background-color: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: var(--card-bg);
            padding: 40px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            border-radius: 12px;
        }}

        header {{
            text-align: center;
            margin-bottom: 40px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 20px;
        }}

        .header-logo {{
            margin-bottom: 10px;
        }}

        .header-logo svg {{
            height: 80px;
            width: auto;
        }}

        header h1 {{
            margin: 0;
            color: var(--primary-color);
            font-size: 28px;
            font-weight: 700;
        }}

        header p {{
            color: var(--text-secondary);
            margin: 10px 0 0;
            font-size: 14px;
        }}

        .section-title {{
            font-size: 20px;
            font-weight: 600;
            color: var(--primary-color);
            margin: 40px 0 20px;
            padding-left: 12px;
            border-left: 4px solid var(--accent-color);
            display: flex;
            align-items: center;
        }}

        /* Summary Box */
        .summary-box {{
            display: flex;
            justify-content: space-between;
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
            border: 1px solid var(--border-color);
            flex-wrap: wrap;
            gap: 20px;
        }}

        .summary-item {{
            flex: 1;
            min-width: 200px;
        }}

        .summary-label {{
            font-size: 13px;
            color: var(--text-secondary);
            margin-bottom: 4px;
        }}

        .summary-value {{
            font-size: 18px;
            font-weight: 600;
            color: var(--primary-color);
        }}

        /* Metrics Grid */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .metric-card {{
            background: #ffffff;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid var(--border-color);
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .metric-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }}

        .metric-value {{
            font-size: 28px;
            font-weight: 700;
            color: var(--primary-color);
            margin-bottom: 5px;
        }}

        .metric-value.positive {{
            color: var(--success-color);
        }}

        .metric-value.negative {{
            color: var(--danger-color);
        }}

        .metric-label {{
            font-size: 14px;
            color: var(--text-secondary);
        }}

        /* Charts Grid Layout */
        .row {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 20px;
        }}

        .col {{
            background: white;
            border-radius: 8px;
            min-width: 0; /* Prevent grid blowout */
        }}

        /* Ensure chart containers fill the column and handle overflow */
        .chart-container {{
            width: 100%;
            height: 100%;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 5px; /* Reduced padding to give more space to chart */
            box-sizing: border-box;
            background: white;
            overflow: hidden; /* Critical for Plotly resizing */
        }}

        footer {{
            text-align: center;
            margin-top: 60px;
            padding-top: 20px;
            border-top: 1px solid var(--border-color);
            color: var(--text-secondary);
            font-size: 12px;
        }}

        @media (max-width: 768px) {{
            .container {{ padding: 20px; }}
            .row {{ grid-template-columns: 1fr; }} /* Stack on mobile */
            .summary-box {{ flex-direction: column; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-logo">{icon_svg}</div>
            <h1>{title}</h1>
            <p>生成时间: {date}</p>
        </header>

        <!-- Summary Section -->
        <div class="summary-box">
            <div class="summary-item">
                <div class="summary-label">回测区间</div>
                <div class="summary-value">{start_date} ~ {end_date}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">回测时长</div>
                <div class="summary-value">{duration_str}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">初始资金</div>
                <div class="summary-value">{initial_cash}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">最终权益</div>
                <div class="summary-value">{final_equity}</div>
            </div>
        </div>

        <div class="section-title">核心指标 (Key Metrics)</div>
        <div class="metrics-grid">
            {metrics_html}
        </div>

        <div class="section-title">权益与回撤 (Equity & Drawdown)</div>
        <div class="chart-container">
            {dashboard_html}
        </div>

        <div class="section-title">收益分析 (Return Analysis)</div>
        <div class="row">
            <div class="col">
                <div class="chart-container">
                    {yearly_returns_html}
                </div>
            </div>
            <div class="col">
                <div class="chart-container">
                    {returns_dist_html}
                </div>
            </div>
        </div>
        <div class="chart-container" style="margin-top: 20px;">
            {rolling_metrics_html}
        </div>

        <div class="section-title">交易分析 (Trade Analysis)</div>
        <div class="row">
            <div class="col">
                <div class="chart-container">
                    {trades_dist_html}
                </div>
            </div>
            <div class="col">
                <div class="chart-container">
                    {pnl_duration_html}
                </div>
            </div>
        </div>

        <div class="section-title">组合归因与容量分析 (Attribution & Capacity)</div>
        <div class="row">
            <div class="col">
                <div class="chart-container">
                    {exposure_summary_html}
                </div>
            </div>
            <div class="col">
                <div class="chart-container">
                    {capacity_summary_html}
                </div>
            </div>
        </div>
        <div class="chart-container" style="margin-top: 20px;">
            {attribution_summary_html}
        </div>
        <div class="chart-container" style="margin-top: 20px;">
            <div class="section-title">
                策略归属聚合 (Strategy Ownership Aggregation)
            </div>
        </div>
        <div class="row">
            <div class="col">
                <div class="chart-container">
                    {orders_by_strategy_html}
                </div>
            </div>
            <div class="col">
                <div class="chart-container">
                    {executions_by_strategy_html}
                </div>
            </div>
        </div>
        <div class="chart-container" style="margin-top: 20px;">
            {risk_by_strategy_html}
        </div>
        <div class="chart-container" style="margin-top: 20px;">
            {risk_reject_ratio_html}
        </div>
        <div class="chart-container" style="margin-top: 20px;">
            {risk_reason_ratio_html}
        </div>
        <div class="chart-container" style="margin-top: 20px;">
            {risk_reject_trend_html}
        </div>
        <div class="chart-container" style="margin-top: 20px;">
            {risk_reject_trend_by_strategy_html}
        </div>
        <div class="chart-container" style="margin-top: 20px;">
            {risk_reason_trend_html}
        </div>

        <footer>
            AKQuant Report | Powered by Plotly & AKQuant
        </footer>
    </div>
    <script>
        // Force Plotly resize on page load to ensure correct dimensions
        // in Grid/Flex layout
        window.addEventListener('load', function() {{
            setTimeout(function() {{
                var plots = document.getElementsByClassName('js-plotly-plot');
                for (var i = 0; i < plots.length; i++) {{
                    Plotly.Plots.resize(plots[i]);
                }}
            }}, 100); // Small delay to allow CSS layout to stabilize
        }});

        // Also trigger on resize to be safe
        // (though responsive: true handles most cases)
        window.addEventListener('resize', function() {{
            var plots = document.getElementsByClassName('js-plotly-plot');
            for (var i = 0; i < plots.length; i++) {{
                Plotly.Plots.resize(plots[i]);
            }}
        }});
    </script>
</body>
</html>
"""


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
                table[col] = table[col].map(_format_currency)
            else:
                table[col] = table[col].map(lambda x: f"{x:,.6f}")
    return str(table.to_html(index=False, border=0, classes="table"))


def _rename_table_columns(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """Rename technical columns to user-friendly labels."""
    renamed = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})
    return cast(pd.DataFrame, renamed)


def _build_summary_context(result: Any) -> dict[str, str]:
    """Build summary text values for report header."""
    equity_curve = result.equity_curve
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


def _get_metric_value(
    result: Any, metrics: Any, name: str, default: float = 0.0
) -> float:
    """Read metric value from object or metrics_df."""
    if hasattr(metrics, name):
        val = getattr(metrics, name)
        try:
            return float(val)
        except (ValueError, TypeError):
            return default
    try:
        return float(cast(Any, result.metrics_df.loc[name, "value"]))
    except Exception:
        return default


def _build_metrics_html(result: Any) -> str:
    """Build key-metrics HTML cards."""
    metrics = result.metrics

    def get_color_class(val: float) -> str:
        if val > 0:
            return "positive"
        if val < 0:
            return "negative"
        return ""

    metric_data = [
        (
            "累计收益率 (Total Return)",
            metrics.total_return_pct,
            f"{metrics.total_return_pct:.2f}%",
            get_color_class(metrics.total_return_pct),
        ),
        (
            "年化收益率 (CAGR)",
            metrics.annualized_return,
            f"{metrics.annualized_return:.2f}%",
            get_color_class(metrics.annualized_return),
        ),
        (
            "平均盈亏 (Avg PnL)",
            _get_metric_value(result, metrics, "avg_pnl"),
            f"{_get_metric_value(result, metrics, 'avg_pnl'):.2f}",
            get_color_class(_get_metric_value(result, metrics, "avg_pnl")),
        ),
        (
            "夏普比率 (Sharpe)",
            metrics.sharpe_ratio,
            f"{metrics.sharpe_ratio:.2f}",
            get_color_class(metrics.sharpe_ratio),
        ),
        (
            "索提诺比率 (Sortino)",
            _get_metric_value(result, metrics, "sortino_ratio"),
            f"{_get_metric_value(result, metrics, 'sortino_ratio'):.2f}",
            get_color_class(_get_metric_value(result, metrics, "sortino_ratio")),
        ),
        (
            "卡玛比率 (Calmar)",
            _get_metric_value(result, metrics, "calmar_ratio"),
            f"{_get_metric_value(result, metrics, 'calmar_ratio'):.2f}",
            get_color_class(_get_metric_value(result, metrics, "calmar_ratio")),
        ),
        (
            "最大回撤 (Max DD)",
            metrics.max_drawdown_pct,
            f"{metrics.max_drawdown_pct:.2f}%",
            "negative",
        ),
        (
            "波动率 (Volatility)",
            metrics.volatility,
            f"{metrics.volatility:.2%}",
            "",
        ),
        (
            "胜率 (Win Rate)",
            metrics.win_rate,
            f"{metrics.win_rate:.2f}%",
            "",
        ),
        (
            "盈亏比 (Profit Factor)",
            _get_metric_value(result, metrics, "profit_factor"),
            f"{_get_metric_value(result, metrics, 'profit_factor'):.2f}",
            "",
        ),
        (
            "凯利公式 (Kelly)",
            _get_metric_value(result, metrics, "kelly_criterion"),
            f"{_get_metric_value(result, metrics, 'kelly_criterion'):.2%}",
            "",
        ),
        ("交易次数 (Trades)", len(result.trades_df), f"{len(result.trades_df)}", ""),
    ]

    metrics_html = ""
    for label, _raw_val, fmt_val, color_cls in metric_data:
        metrics_html += f"""
        <div class="metric-card">
            <div class="metric-value {color_cls}">{fmt_val}</div>
            <div class="metric-label">{label}</div>
        </div>
        """
    return metrics_html


def _build_chart_html_sections(result: Any) -> dict[str, str]:
    """Build chart HTML sections from plot figures."""
    config = {"responsive": True}

    fig_dashboard = plot_dashboard(result, show=False, theme="light")
    dashboard_html = (
        fig_dashboard.to_html(full_html=False, include_plotlyjs=False, config=config)
        if fig_dashboard
        else "<div>暂无数据</div>"
    )

    returns_series = result.daily_returns
    fig_rolling = plot_rolling_metrics(returns_series, theme="light")
    rolling_metrics_html = (
        fig_rolling.to_html(full_html=False, include_plotlyjs=False, config=config)
        if fig_rolling
        else "<div>暂无数据</div>"
    )
    fig_dist_ret = plot_returns_distribution(returns_series, theme="light")
    returns_dist_html = (
        fig_dist_ret.to_html(full_html=False, include_plotlyjs=False, config=config)
        if fig_dist_ret
        else "<div>暂无数据</div>"
    )
    fig_yearly = plot_yearly_returns(returns_series, theme="light")
    yearly_returns_html = (
        fig_yearly.to_html(full_html=False, include_plotlyjs=False, config=config)
        if fig_yearly
        else "<div>暂无数据</div>"
    )

    fig_dist = plot_trades_distribution(result.trades_df)
    trades_dist_html = (
        fig_dist.to_html(full_html=False, include_plotlyjs=False, config=config)
        if fig_dist
        else "<div>无交易数据</div>"
    )
    fig_duration = plot_pnl_vs_duration(result.trades_df)
    pnl_duration_html = (
        fig_duration.to_html(full_html=False, include_plotlyjs=False, config=config)
        if fig_duration
        else "<div>无交易数据</div>"
    )
    risk_reject_ratio_html = "<div>暂无策略级风控拒单占比图</div>"
    risk_reason_ratio_html = "<div>暂无策略级拒单原因占比图</div>"
    risk_reject_trend_html = "<div>暂无按日风控拒单趋势图</div>"
    risk_reject_trend_by_strategy_html = "<div>暂无按策略风控拒单趋势图</div>"
    risk_reason_trend_html = "<div>暂无按日拒单原因趋势图</div>"
    risk_df = (
        result.risk_rejections_by_strategy()
        if hasattr(result, "risk_rejections_by_strategy")
        else pd.DataFrame()
    )
    if not risk_df.empty and "risk_reject_count" in risk_df.columns:
        risk_base_df = risk_df.copy()
        if "owner_strategy_id" not in risk_base_df.columns:
            risk_base_df["owner_strategy_id"] = "_default"
        risk_base_df["owner_strategy_id"] = (
            risk_base_df["owner_strategy_id"].fillna("_default").astype(str)
        )
        reject_count = pd.to_numeric(
            risk_base_df["risk_reject_count"], errors="coerce"
        ).fillna(0.0)
        total_reject_count = float(reject_count.sum())
        if total_reject_count > 0.0:
            px = __import__("plotly.express", fromlist=["bar"])

            ratio_df = pd.DataFrame(
                {
                    "owner_strategy_id": risk_base_df["owner_strategy_id"],
                    "reject_ratio": reject_count / total_reject_count,
                    "risk_reject_count": reject_count,
                }
            ).sort_values("reject_ratio", ascending=False)
            fig_risk_ratio = px.bar(
                ratio_df,
                x="owner_strategy_id",
                y="reject_ratio",
                title="策略级风控拒单占比 (Risk Reject Ratio by Strategy)",
                text=ratio_df["reject_ratio"].map(lambda v: f"{v:.1%}"),
                labels={
                    "owner_strategy_id": "策略ID (Strategy ID)",
                    "reject_ratio": "拒单占比 (Reject Ratio)",
                },
            )
            fig_risk_ratio.update_traces(
                hovertemplate=(
                    "策略ID=%{x}<br>拒单占比=%{y:.1%}<br>"
                    "拒单数=%{customdata[0]:.0f}<extra></extra>"
                ),
                customdata=ratio_df[["risk_reject_count"]].to_numpy(),
            )
            fig_risk_ratio.update_yaxes(tickformat=".0%")
            fig_risk_ratio.update_layout(
                height=320, margin=dict(l=20, r=20, t=60, b=20)
            )
            risk_reject_ratio_html = fig_risk_ratio.to_html(
                full_html=False, include_plotlyjs=False, config=config
            )
        reason_columns = [
            ("daily_loss_reject_count", "Daily Loss"),
            ("drawdown_reject_count", "Drawdown"),
            ("reduce_only_reject_count", "Reduce-Only"),
            ("position_limit_reject_count", "Position Limit"),
            ("order_size_limit_reject_count", "Order Size Limit"),
            ("order_value_limit_reject_count", "Order Value Limit"),
            ("strategy_risk_budget_reject_count", "Strategy Risk Budget"),
            ("portfolio_risk_budget_reject_count", "Portfolio Risk Budget"),
            ("other_risk_reject_count", "Other"),
        ]
        available_reason_columns = [
            (column_name, label)
            for column_name, label in reason_columns
            if column_name in risk_base_df.columns
        ]
        if available_reason_columns:
            stacked_df = pd.DataFrame(
                {"owner_strategy_id": risk_base_df["owner_strategy_id"]}
            )
            for column_name, label in available_reason_columns:
                values = pd.to_numeric(
                    risk_base_df[column_name], errors="coerce"
                ).fillna(0.0)
                stacked_df[label] = values
            totals = stacked_df.drop(columns=["owner_strategy_id"]).sum(axis=1)
            non_zero_totals = totals > 0
            if bool(non_zero_totals.any()):
                stacked_df = stacked_df.loc[non_zero_totals].reset_index(drop=True)
                totals = totals.loc[non_zero_totals].reset_index(drop=True)
                value_columns = [
                    col for col in stacked_df.columns if col != "owner_strategy_id"
                ]
                ratio_stacked = stacked_df.copy()
                ratio_stacked[value_columns] = ratio_stacked[value_columns].div(
                    totals, axis=0
                )
                px = __import__("plotly.express", fromlist=["bar"])
                long_df = ratio_stacked.melt(
                    id_vars=["owner_strategy_id"],
                    value_vars=value_columns,
                    var_name="risk_reason",
                    value_name="reject_ratio",
                )
                fig_reason_ratio = px.bar(
                    long_df,
                    x="owner_strategy_id",
                    y="reject_ratio",
                    color="risk_reason",
                    title="策略级拒单原因占比 (Risk Reason Ratio by Strategy)",
                    labels={
                        "owner_strategy_id": "策略ID (Strategy ID)",
                        "reject_ratio": "拒单原因占比 (Reason Ratio)",
                        "risk_reason": "拒单原因 (Reason)",
                    },
                )
                fig_reason_ratio.update_layout(
                    barmode="stack",
                    height=360,
                    margin=dict(l=20, r=20, t=60, b=20),
                )
                fig_reason_ratio.update_yaxes(tickformat=".0%")
                fig_reason_ratio.update_traces(
                    hovertemplate=(
                        "策略ID=%{x}<br>原因=%{fullData.name}<br>"
                        "占比=%{y:.1%}<extra></extra>"
                    )
                )
                risk_reason_ratio_html = fig_reason_ratio.to_html(
                    full_html=False, include_plotlyjs=False, config=config
                )
    risk_trend_df = (
        result.risk_rejections_trend(freq="D")
        if hasattr(result, "risk_rejections_trend")
        else pd.DataFrame()
    )
    if not risk_trend_df.empty:
        trend_df = risk_trend_df.copy()
        trend_df["date"] = pd.to_datetime(trend_df["date"], errors="coerce")
        trend_df = trend_df.dropna(subset=["date"]).sort_values("date")
        if not trend_df.empty and "risk_reject_count" in trend_df.columns:
            px = __import__("plotly.express", fromlist=["line"])
            trend_df["risk_reject_count"] = pd.to_numeric(
                trend_df["risk_reject_count"], errors="coerce"
            ).fillna(0.0)
            fig_risk_trend = px.line(
                trend_df,
                x="date",
                y="risk_reject_count",
                markers=True,
                title="按日风控拒单趋势 (Daily Risk Reject Trend)",
                labels={
                    "date": "日期 (Date)",
                    "risk_reject_count": "风控拒单数 (Risk Reject Count)",
                },
            )
            fig_risk_trend.update_layout(
                height=320, margin=dict(l=20, r=20, t=60, b=20)
            )
            fig_risk_trend.update_traces(
                hovertemplate="日期=%{x}<br>拒单数=%{y:.0f}<extra></extra>"
            )
            risk_reject_trend_html = fig_risk_trend.to_html(
                full_html=False, include_plotlyjs=False, config=config
            )
            reason_columns = [
                ("daily_loss_reject_count", "Daily Loss"),
                ("drawdown_reject_count", "Drawdown"),
                ("reduce_only_reject_count", "Reduce-Only"),
                ("position_limit_reject_count", "Position Limit"),
                ("order_size_limit_reject_count", "Order Size Limit"),
                ("order_value_limit_reject_count", "Order Value Limit"),
                ("strategy_risk_budget_reject_count", "Strategy Risk Budget"),
                ("portfolio_risk_budget_reject_count", "Portfolio Risk Budget"),
                ("other_risk_reject_count", "Other"),
            ]
            available_reason_columns = [
                (column_name, label)
                for column_name, label in reason_columns
                if column_name in trend_df.columns
            ]
            if available_reason_columns:
                reason_trend_df = pd.DataFrame({"date": trend_df["date"]})
                for column_name, label in available_reason_columns:
                    values = pd.to_numeric(
                        trend_df[column_name], errors="coerce"
                    ).fillna(0.0)
                    reason_trend_df[label] = values
                long_reason_df = reason_trend_df.melt(
                    id_vars=["date"],
                    value_vars=[
                        col for col in reason_trend_df.columns if col != "date"
                    ],
                    var_name="risk_reason",
                    value_name="reject_count",
                )
                fig_reason_trend = px.area(
                    long_reason_df,
                    x="date",
                    y="reject_count",
                    color="risk_reason",
                    title="按日拒单原因趋势 (Daily Risk Reason Trend)",
                    labels={
                        "date": "日期 (Date)",
                        "reject_count": "拒单数 (Reject Count)",
                        "risk_reason": "拒单原因 (Reason)",
                    },
                )
                fig_reason_trend.update_layout(
                    height=340, margin=dict(l=20, r=20, t=60, b=20)
                )
                fig_reason_trend.update_traces(
                    hovertemplate=(
                        "日期=%{x}<br>原因=%{fullData.name}<br>"
                        "拒单数=%{y:.0f}<extra></extra>"
                    )
                )
                risk_reason_trend_html = fig_reason_trend.to_html(
                    full_html=False, include_plotlyjs=False, config=config
                )
    trend_by_strategy_df = (
        result.risk_rejections_trend_by_strategy(freq="D")
        if hasattr(result, "risk_rejections_trend_by_strategy")
        else pd.DataFrame()
    )
    if not trend_by_strategy_df.empty:
        strategy_trend_df = trend_by_strategy_df.copy()
        strategy_trend_df["date"] = pd.to_datetime(
            strategy_trend_df["date"], errors="coerce"
        )
        strategy_trend_df = strategy_trend_df.dropna(subset=["date"]).sort_values(
            ["date", "owner_strategy_id"]
        )
        if (
            not strategy_trend_df.empty
            and "risk_reject_count" in strategy_trend_df.columns
        ):
            px = __import__("plotly.express", fromlist=["line"])
            strategy_trend_df["owner_strategy_id"] = (
                strategy_trend_df["owner_strategy_id"].fillna("_default").astype(str)
            )
            strategy_trend_df["risk_reject_count"] = pd.to_numeric(
                strategy_trend_df["risk_reject_count"], errors="coerce"
            ).fillna(0.0)
            fig_risk_strategy_trend = px.line(
                strategy_trend_df,
                x="date",
                y="risk_reject_count",
                color="owner_strategy_id",
                markers=True,
                title="按策略风控拒单趋势 (Risk Reject Trend by Strategy)",
                labels={
                    "date": "日期 (Date)",
                    "risk_reject_count": "风控拒单数 (Risk Reject Count)",
                    "owner_strategy_id": "策略ID (Strategy ID)",
                },
            )
            fig_risk_strategy_trend.update_layout(
                height=340, margin=dict(l=20, r=20, t=60, b=20)
            )
            fig_risk_strategy_trend.update_traces(
                hovertemplate=(
                    "日期=%{x}<br>策略ID=%{fullData.name}<br>"
                    "拒单数=%{y:.0f}<extra></extra>"
                )
            )
            risk_reject_trend_by_strategy_html = fig_risk_strategy_trend.to_html(
                full_html=False, include_plotlyjs=False, config=config
            )

    return {
        "dashboard_html": dashboard_html,
        "yearly_returns_html": yearly_returns_html,
        "returns_dist_html": returns_dist_html,
        "rolling_metrics_html": rolling_metrics_html,
        "trades_dist_html": trades_dist_html,
        "pnl_duration_html": pnl_duration_html,
        "risk_reject_ratio_html": risk_reject_ratio_html,
        "risk_reason_ratio_html": risk_reason_ratio_html,
        "risk_reject_trend_html": risk_reject_trend_html,
        "risk_reject_trend_by_strategy_html": risk_reject_trend_by_strategy_html,
        "risk_reason_trend_html": risk_reason_trend_html,
    }


def _build_analysis_table_sections(
    result: Any, compact_currency: bool = True
) -> dict[str, str]:
    """Build attribution/exposure/capacity HTML tables."""
    exposure_df = (
        result.exposure_df() if hasattr(result, "exposure_df") else pd.DataFrame()
    )
    if not exposure_df.empty:
        exposure_view = pd.DataFrame(
            [
                {
                    "latest_net_exposure_pct": float(
                        exposure_df["net_exposure_pct"].iloc[-1]
                    ),
                    "latest_gross_exposure_pct": float(
                        exposure_df["gross_exposure_pct"].iloc[-1]
                    ),
                    "max_leverage": float(exposure_df["leverage"].max()),
                }
            ]
        )
        exposure_view = _rename_table_columns(
            exposure_view,
            {
                "latest_net_exposure_pct": "最新净暴露比 (Latest Net Exposure %)",
                "latest_gross_exposure_pct": "最新总暴露比 (Latest Gross Exposure %)",
                "max_leverage": "最大杠杆 (Max Leverage)",
            },
        )
        exposure_summary_html = _format_table(
            exposure_view,
            max_rows=1,
            percentage_columns={
                "最新净暴露比 (Latest Net Exposure %)",
                "最新总暴露比 (Latest Gross Exposure %)",
            },
            compact_currency=compact_currency,
        )
    else:
        exposure_summary_html = "<div>暂无暴露数据</div>"

    capacity_df = (
        result.capacity_df() if hasattr(result, "capacity_df") else pd.DataFrame()
    )
    if not capacity_df.empty:
        capacity_view = pd.DataFrame(
            [
                {
                    "total_order_count": float(capacity_df["order_count"].sum()),
                    "total_filled_value": float(capacity_df["filled_value"].sum()),
                    "avg_fill_rate_qty": float(capacity_df["fill_rate_qty"].mean()),
                    "avg_turnover": float(capacity_df["turnover"].mean()),
                }
            ]
        )
        capacity_view = _rename_table_columns(
            capacity_view,
            {
                "total_order_count": "总订单数 (Total Orders)",
                "total_filled_value": "总成交额 (Total Filled Value)",
                "avg_fill_rate_qty": "平均成交率 (Avg Fill Rate Qty)",
                "avg_turnover": "平均换手率 (Avg Turnover)",
            },
        )
        capacity_summary_html = _format_table(
            capacity_view,
            max_rows=1,
            percentage_columns={
                "平均成交率 (Avg Fill Rate Qty)",
                "平均换手率 (Avg Turnover)",
            },
            compact_currency_columns={"总成交额 (Total Filled Value)"},
            compact_currency=compact_currency,
        )
    else:
        capacity_summary_html = "<div>暂无容量数据</div>"

    attribution_df = (
        result.attribution_df(by="symbol")
        if hasattr(result, "attribution_df")
        else pd.DataFrame()
    )
    if not attribution_df.empty:
        cols = [
            "group",
            "trade_count",
            "total_pnl",
            "contribution_pct",
            "total_commission",
        ]
        cols = [c for c in cols if c in attribution_df.columns]
        attribution_view = _rename_table_columns(
            attribution_df[cols],
            {
                "group": "分组 (Group)",
                "trade_count": "交易次数 (Trade Count)",
                "total_pnl": "总盈亏 (Total PnL)",
                "contribution_pct": "贡献占比 (Contribution %)",
                "total_commission": "总手续费 (Total Commission)",
            },
        )
        attribution_summary_html = _format_table(
            attribution_view,
            max_rows=10,
            percentage_columns={"贡献占比 (Contribution %)"},
            compact_currency_columns={
                "总盈亏 (Total PnL)",
                "总手续费 (Total Commission)",
            },
            compact_currency=compact_currency,
        )
    else:
        attribution_summary_html = "<div>暂无归因数据</div>"

    orders_by_strategy_df = (
        result.orders_by_strategy()
        if hasattr(result, "orders_by_strategy")
        else pd.DataFrame()
    )
    if not orders_by_strategy_df.empty:
        cols = [
            "owner_strategy_id",
            "order_count",
            "filled_order_count",
            "filled_quantity",
            "filled_value",
            "fill_rate_qty",
        ]
        cols = [c for c in cols if c in orders_by_strategy_df.columns]
        orders_by_strategy_view = _rename_table_columns(
            orders_by_strategy_df[cols],
            {
                "owner_strategy_id": "策略ID (Strategy ID)",
                "order_count": "订单数 (Orders)",
                "filled_order_count": "已成交订单数 (Filled Orders)",
                "filled_quantity": "成交数量 (Filled Qty)",
                "filled_value": "成交额 (Filled Value)",
                "fill_rate_qty": "数量成交率 (Fill Rate Qty)",
            },
        )
        orders_by_strategy_html = _format_table(
            orders_by_strategy_view,
            max_rows=20,
            percentage_columns={"数量成交率 (Fill Rate Qty)"},
            compact_currency_columns={"成交额 (Filled Value)"},
            compact_currency=compact_currency,
        )
    else:
        orders_by_strategy_html = "<div>暂无策略归属订单聚合数据</div>"

    executions_by_strategy_df = (
        result.executions_by_strategy()
        if hasattr(result, "executions_by_strategy")
        else pd.DataFrame()
    )
    if not executions_by_strategy_df.empty:
        cols = [
            "owner_strategy_id",
            "execution_count",
            "total_quantity",
            "total_notional",
            "total_commission",
            "avg_fill_price",
        ]
        cols = [c for c in cols if c in executions_by_strategy_df.columns]
        executions_by_strategy_view = _rename_table_columns(
            executions_by_strategy_df[cols],
            {
                "owner_strategy_id": "策略ID (Strategy ID)",
                "execution_count": "成交笔数 (Executions)",
                "total_quantity": "总成交数量 (Total Qty)",
                "total_notional": "总成交额 (Total Notional)",
                "total_commission": "总手续费 (Total Commission)",
                "avg_fill_price": "平均成交价 (Avg Fill Price)",
            },
        )
        executions_by_strategy_html = _format_table(
            executions_by_strategy_view,
            max_rows=20,
            compact_currency_columns={
                "总成交额 (Total Notional)",
                "总手续费 (Total Commission)",
            },
            compact_currency=compact_currency,
        )
    else:
        executions_by_strategy_html = "<div>暂无策略归属成交聚合数据</div>"

    risk_by_strategy_df = (
        result.risk_rejections_by_strategy()
        if hasattr(result, "risk_rejections_by_strategy")
        else pd.DataFrame()
    )
    if not risk_by_strategy_df.empty:
        cols = [
            "owner_strategy_id",
            "risk_reject_count",
            "daily_loss_reject_count",
            "drawdown_reject_count",
            "reduce_only_reject_count",
            "strategy_risk_budget_reject_count",
            "portfolio_risk_budget_reject_count",
            "other_risk_reject_count",
        ]
        cols = [c for c in cols if c in risk_by_strategy_df.columns]
        risk_by_strategy_view = _rename_table_columns(
            risk_by_strategy_df[cols],
            {
                "owner_strategy_id": "策略ID (Strategy ID)",
                "risk_reject_count": "风险拒单总数 (Risk Rejects)",
                "daily_loss_reject_count": "日损拒单数 (Daily Loss Rejects)",
                "drawdown_reject_count": "回撤拒单数 (Drawdown Rejects)",
                "reduce_only_reject_count": "仅平仓拒单数 (Reduce-Only Rejects)",
                "strategy_risk_budget_reject_count": (
                    "策略预算拒单数 (Strategy Budget Rejects)"
                ),
                "portfolio_risk_budget_reject_count": (
                    "组合预算拒单数 (Portfolio Budget Rejects)"
                ),
                "other_risk_reject_count": "其他拒单数 (Other Rejects)",
            },
        )
        risk_by_strategy_html = _format_table(
            risk_by_strategy_view,
            max_rows=20,
        )
    else:
        risk_by_strategy_html = "<div>暂无策略归属风控拒单聚合数据</div>"

    return {
        "exposure_summary_html": exposure_summary_html,
        "capacity_summary_html": capacity_summary_html,
        "attribution_summary_html": attribution_summary_html,
        "orders_by_strategy_html": orders_by_strategy_html,
        "executions_by_strategy_html": executions_by_strategy_html,
        "risk_by_strategy_html": risk_by_strategy_html,
    }


def plot_report(
    result: "BacktestResult",
    title: str = "AKQuant 策略回测报告",
    filename: str = "akquant_report.html",
    show: bool = False,
    compact_currency: bool = True,
) -> None:
    """
    生成类似 QuantStats 的整合版 HTML 报告 (中文优化版).

    内容包括:
    1. 核心指标概览 (Key Metrics)
    2. 权益曲线、回撤、月度热力图 (Dashboard)
    3. 交易分布与持仓时间分析 (Trade Analysis)

    :param compact_currency: 是否将金额列按 K/M/B 紧凑显示
    """
    if not check_plotly():
        return

    # Prepare Icon
    icon_b64 = base64.b64encode(AKQUANT_ICON_SVG.encode("utf-8")).decode("utf-8")
    favicon_uri = f"data:image/svg+xml;base64,{icon_b64}"

    summary_context = _build_summary_context(result)
    metrics_html = _build_metrics_html(result)
    chart_sections = _build_chart_html_sections(result)
    analysis_sections = _build_analysis_table_sections(
        result, compact_currency=compact_currency
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
        dashboard_html=chart_sections["dashboard_html"],
        yearly_returns_html=chart_sections["yearly_returns_html"],
        returns_dist_html=chart_sections["returns_dist_html"],
        rolling_metrics_html=chart_sections["rolling_metrics_html"],
        trades_dist_html=chart_sections["trades_dist_html"],
        pnl_duration_html=chart_sections["pnl_duration_html"],
        risk_reject_ratio_html=chart_sections["risk_reject_ratio_html"],
        risk_reason_ratio_html=chart_sections["risk_reason_ratio_html"],
        risk_reject_trend_html=chart_sections["risk_reject_trend_html"],
        risk_reject_trend_by_strategy_html=chart_sections[
            "risk_reject_trend_by_strategy_html"
        ],
        risk_reason_trend_html=chart_sections["risk_reason_trend_html"],
        exposure_summary_html=analysis_sections["exposure_summary_html"],
        capacity_summary_html=analysis_sections["capacity_summary_html"],
        attribution_summary_html=analysis_sections["attribution_summary_html"],
        orders_by_strategy_html=analysis_sections["orders_by_strategy_html"],
        executions_by_strategy_html=analysis_sections["executions_by_strategy_html"],
        risk_by_strategy_html=analysis_sections["risk_by_strategy_html"],
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
