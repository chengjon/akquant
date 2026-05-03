"""Table and metrics HTML generation functions for report building."""

from typing import TYPE_CHECKING, Any, Optional, Union, cast

import pandas as pd

from ..utils import format_metric_value

if TYPE_CHECKING:
    pass


def _build_benchmark_sections(
    strategy_returns: pd.Series,
    benchmark: Optional[Union[str, pd.Series]],
    config: dict[str, Any],
) -> dict[str, str]:
    """Build benchmark comparison metrics and chart sections."""
    # Import here to avoid circular imports
    from .report import _normalize_returns_series, _resolve_benchmark_returns

    benchmark_returns, benchmark_label = _resolve_benchmark_returns(
        benchmark, strategy_returns
    )
    if benchmark_returns is None:
        reason = (
            "未提供可用基准数据，已跳过相对收益分析。"
            if benchmark is None
            else f"未生成基准对比: {benchmark_label}"
        )
        empty_html = f'<div class="empty-panel">{reason}</div>'
        return {
            "benchmark_metrics_html": empty_html,
            "benchmark_chart_html": empty_html,
        }
    strategy_series = _normalize_returns_series(strategy_returns)
    aligned = pd.concat(
        [strategy_series.rename("strategy"), benchmark_returns.rename("benchmark")],
        axis=1,
        join="inner",
    ).dropna()
    if aligned.empty:
        empty_html = (
            '<div class="empty-panel">'
            "策略与基准收益率无可用重叠样本，已跳过对比。"
            "</div>"
        )
        return {
            "benchmark_metrics_html": empty_html,
            "benchmark_chart_html": empty_html,
        }
    strategy_aligned = cast(pd.Series, aligned["strategy"].astype(float))
    benchmark_aligned = cast(pd.Series, aligned["benchmark"].astype(float))
    excess = cast(pd.Series, strategy_aligned - benchmark_aligned)
    annual_factor = 252.0
    annual_excess = float(excess.mean() * annual_factor)
    tracking_error = float(excess.std(ddof=0) * (annual_factor**0.5))
    info_ratio = annual_excess / tracking_error if tracking_error > 0 else float("nan")
    strategy_total = float((1.0 + strategy_aligned).to_numpy(dtype=float).prod())
    benchmark_total = float((1.0 + benchmark_aligned).to_numpy(dtype=float).prod())
    total_excess = (
        strategy_total / benchmark_total - 1.0 if benchmark_total > 0 else float("nan")
    )
    mean_strategy = float(strategy_aligned.mean())
    mean_benchmark = float(benchmark_aligned.mean())
    variance_benchmark = float(benchmark_aligned.var(ddof=0))
    beta = float("nan")
    alpha = float("nan")
    if variance_benchmark > 0:
        covariance = float(
            (
                (strategy_aligned - mean_strategy)
                * (benchmark_aligned - mean_benchmark)
            ).mean()
        )
        beta = covariance / variance_benchmark
        alpha = (mean_strategy - beta * mean_benchmark) * annual_factor

    def metric_color(value: float) -> str:
        if pd.isna(value):
            return ""
        if value > 0:
            return "positive"
        if value < 0:
            return "negative"
        return ""

    def metric_fmt(value: float, kind: str) -> str:
        if pd.isna(value):
            return "N/A"
        if kind == "pct":
            return f"{value * 100:.2f}%"
        return f"{value:.4f}"

    benchmark_metrics = [
        ("基准名称 (Benchmark)", benchmark_label, ""),
        (
            "累计超额收益 (Total Excess)",
            metric_fmt(total_excess, "pct"),
            metric_color(total_excess),
        ),
        (
            "年化超额收益 (Annual Excess)",
            metric_fmt(annual_excess, "pct"),
            metric_color(annual_excess),
        ),
        (
            "跟踪误差 (Tracking Error)",
            metric_fmt(tracking_error, "pct"),
            "",
        ),
        (
            "信息比率 (Information Ratio)",
            metric_fmt(info_ratio, "ratio"),
            metric_color(info_ratio),
        ),
        (
            "Beta",
            metric_fmt(beta, "ratio"),
            metric_color(beta - 1.0 if not pd.isna(beta) else beta),
        ),
        (
            "Alpha (Annual)",
            metric_fmt(alpha, "pct"),
            metric_color(alpha),
        ),
    ]
    metrics_html = ""
    for label, value, color_cls in benchmark_metrics:
        metrics_html += (
            f'<div class="metric-card"><div class="metric-value {color_cls}">{value}'
            f'</div><div class="metric-label">{label}</div></div>'
        )
    cumulative_strategy = cast(pd.Series, (1.0 + strategy_aligned).cumprod() - 1.0)
    cumulative_benchmark = cast(pd.Series, (1.0 + benchmark_aligned).cumprod() - 1.0)
    cumulative_excess = cast(pd.Series, cumulative_strategy - cumulative_benchmark)
    go = __import__("plotly.graph_objects", fromlist=["Figure"])
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=cumulative_strategy.index,
            y=cumulative_strategy,
            mode="lines",
            name="策略累计收益",
            line=dict(color="#1f77b4", width=2),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=cumulative_benchmark.index,
            y=cumulative_benchmark,
            mode="lines",
            name=f"基准累计收益 ({benchmark_label})",
            line=dict(color="#7f8c8d", width=2, dash="dash"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=cumulative_excess.index,
            y=cumulative_excess,
            mode="lines",
            name="累计超额收益",
            line=dict(color="#c0392b", width=2),
        )
    )
    fig.update_layout(
        title="策略与基准累计收益对比 (Cumulative Return Comparison)",
        template="plotly_white",
        yaxis=dict(tickformat=".2%"),
        height=420,
        margin=dict(l=20, r=20, t=60, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="x unified",
    )
    chart_html = fig.to_html(full_html=False, include_plotlyjs=False, config=config)
    return {
        "benchmark_metrics_html": metrics_html,
        "benchmark_chart_html": chart_html,
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
            format_metric_value("total_return_pct", metrics.total_return_pct),
            get_color_class(metrics.total_return_pct),
        ),
        (
            "年化收益率 (CAGR)",
            metrics.annualized_return,
            format_metric_value("annualized_return", metrics.annualized_return),
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
            format_metric_value("max_drawdown_pct", metrics.max_drawdown_pct),
            "negative",
        ),
        (
            "波动率 (Volatility)",
            metrics.volatility,
            format_metric_value("volatility", metrics.volatility),
            "",
        ),
        (
            "胜率 (Win Rate)",
            metrics.win_rate,
            format_metric_value("win_rate", metrics.win_rate),
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
            format_metric_value(
                "kelly_criterion",
                _get_metric_value(result, metrics, "kelly_criterion"),
            ),
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


def _build_analysis_table_sections(
    result: Any, compact_currency: bool = True
) -> dict[str, str]:
    """Build attribution/exposure/capacity HTML tables."""
    # Import helpers from report module
    from .report import _format_currency, _format_table, _rename_table_columns

    overview_cards: list[tuple[str, str]] = []

    def add_overview_card(label: str, value: str) -> None:
        overview_cards.append((label, value))

    exposure_df = (
        result.exposure_df() if hasattr(result, "exposure_df") else pd.DataFrame()
    )
    if not exposure_df.empty:
        latest_net_exposure_pct = float(exposure_df["net_exposure_pct"].iloc[-1])
        latest_gross_exposure_pct = float(exposure_df["gross_exposure_pct"].iloc[-1])
        max_leverage = float(exposure_df["leverage"].max())
        add_overview_card("最新净暴露比", f"{latest_net_exposure_pct * 100:.2f}%")
        add_overview_card("最新总暴露比", f"{latest_gross_exposure_pct * 100:.2f}%")
        add_overview_card("最大杠杆", f"{max_leverage:.4f}")
        exposure_view = pd.DataFrame(
            [
                {
                    "latest_net_exposure_pct": latest_net_exposure_pct,
                    "latest_gross_exposure_pct": latest_gross_exposure_pct,
                    "max_leverage": max_leverage,
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
        total_order_count = float(capacity_df["order_count"].sum())
        total_filled_value = float(capacity_df["filled_value"].sum())
        avg_fill_rate_qty = float(capacity_df["fill_rate_qty"].mean())
        avg_turnover = float(capacity_df["turnover"].mean())
        add_overview_card("总订单数", f"{total_order_count:,.0f}")
        add_overview_card("总成交额", _format_currency(total_filled_value))
        add_overview_card("平均成交率", f"{avg_fill_rate_qty * 100:.2f}%")
        add_overview_card("平均换手率", f"{avg_turnover * 100:.2f}%")
        capacity_view = pd.DataFrame(
            [
                {
                    "total_order_count": total_order_count,
                    "total_filled_value": total_filled_value,
                    "avg_fill_rate_qty": avg_fill_rate_qty,
                    "avg_turnover": avg_turnover,
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
        total_pnl = float(attribution_df["total_pnl"].sum())
        total_commission = float(attribution_df["total_commission"].sum())
        total_trade_count = float(attribution_df["trade_count"].sum())
        add_overview_card("归因总盈亏", _format_currency(total_pnl))
        add_overview_card("归因总手续费", _format_currency(total_commission))
        add_overview_card("归因交易次数", f"{total_trade_count:,.0f}")
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

    liquidation_audit_df = (
        result.liquidation_audit_df
        if hasattr(result, "liquidation_audit_df")
        else pd.DataFrame()
    )
    if not liquidation_audit_df.empty:
        liq_df = liquidation_audit_df.copy()
        cols = [
            "timestamp",
            "date",
            "daily_interest",
            "liquidated_count",
            "liquidated_symbols",
            "priority",
        ]
        cols = [c for c in cols if c in liq_df.columns]
        if "priority" in liq_df.columns:
            liq_df["priority"] = (
                liq_df["priority"]
                .astype(str)
                .replace({"short_first": "先平空头", "long_first": "先平多头"})
            )
        if "liquidated_symbols" in liq_df.columns:
            liq_df["liquidated_symbols"] = (
                liq_df["liquidated_symbols"].astype(str).str.replace(",", ", ")
            )
        liquidation_view = _rename_table_columns(
            liq_df[cols],
            {
                "timestamp": "时间戳 (Timestamp)",
                "date": "日期 (Date)",
                "daily_interest": "当日利息 (Daily Interest)",
                "liquidated_count": "强平标的数 (Liquidated Count)",
                "liquidated_symbols": "强平标的 (Liquidated Symbols)",
                "priority": "强平顺序 (Priority)",
            },
        )
        liquidation_audit_html = _format_table(
            liquidation_view,
            max_rows=20,
            compact_currency_columns={"当日利息 (Daily Interest)"},
            compact_currency=compact_currency,
        )
    else:
        liquidation_audit_html = "<div>暂无强平审计数据</div>"

    if overview_cards:
        analysis_overview_html = "".join(
            [
                (
                    '<div class="analysis-card">'
                    f'<div class="analysis-card-label">{label}</div>'
                    f'<div class="analysis-card-value">{value}</div>'
                    "</div>"
                )
                for label, value in overview_cards
            ]
        )
    else:
        analysis_overview_html = "<div>暂无归因与容量摘要数据</div>"

    return {
        "analysis_overview_html": analysis_overview_html,
        "exposure_summary_html": exposure_summary_html,
        "capacity_summary_html": capacity_summary_html,
        "attribution_summary_html": attribution_summary_html,
        "orders_by_strategy_html": orders_by_strategy_html,
        "executions_by_strategy_html": executions_by_strategy_html,
        "risk_by_strategy_html": risk_by_strategy_html,
        "liquidation_audit_html": liquidation_audit_html,
    }
