"""Chart HTML generation functions for report building."""

from typing import TYPE_CHECKING, Any, Optional, Union, cast

import pandas as pd

from .analysis import (
    plot_pnl_vs_duration,
    plot_returns_distribution,
    plot_rolling_metrics,
    plot_trades_distribution,
    plot_yearly_returns,
)
from .dashboard import plot_dashboard
from .strategy import plot_strategy

if TYPE_CHECKING:
    pass


def _select_plot_symbol(
    result: Any,
    market_data: Optional[Union[pd.DataFrame, dict[str, pd.DataFrame]]],
    plot_symbol: Optional[str],
) -> Optional[str]:
    if plot_symbol:
        return str(plot_symbol)
    trades_df = getattr(result, "trades_df", pd.DataFrame())
    if (
        isinstance(trades_df, pd.DataFrame)
        and not trades_df.empty
        and "symbol" in trades_df.columns
    ):
        counts = trades_df["symbol"].dropna().astype(str).value_counts()
        if not counts.empty:
            return str(counts.index[0])
    if isinstance(market_data, dict):
        keys = [str(k) for k in market_data.keys()]
        if keys:
            return keys[0]
    if isinstance(market_data, pd.DataFrame) and "symbol" in market_data.columns:
        symbols = market_data["symbol"].dropna().astype(str)
        if not symbols.empty:
            return str(symbols.iloc[0])
    return None


def _extract_symbol_market_data(
    market_data: Optional[Union[pd.DataFrame, dict[str, pd.DataFrame]]], symbol: str
) -> pd.DataFrame:
    if market_data is None:
        return pd.DataFrame()
    if isinstance(market_data, dict):
        data = market_data.get(symbol, pd.DataFrame()).copy()
    elif isinstance(market_data, pd.DataFrame):
        data = market_data.copy()
        if "symbol" in data.columns:
            data = data[data["symbol"].astype(str) == symbol].copy()
    else:
        return pd.DataFrame()
    if data.empty:
        return cast(pd.DataFrame, data)
    if not isinstance(data.index, pd.DatetimeIndex):
        for col in ["date", "timestamp", "datetime", "Date", "Timestamp"]:
            if col in data.columns:
                data = data.set_index(col)
                break
        data.index = pd.to_datetime(data.index, errors="coerce")
    valid_index_mask = ~data.index.to_series().isna()
    data = data.loc[valid_index_mask].copy()
    required_cols = {"open", "high", "low", "close"}
    if not required_cols.issubset(set(data.columns)):
        return pd.DataFrame()
    data = data.sort_index()
    return cast(pd.DataFrame, data)


def _build_chart_html_sections(
    result: Any,
    market_data: Optional[Union[pd.DataFrame, dict[str, pd.DataFrame]]] = None,
    plot_symbol: Optional[str] = None,
    include_trade_kline: bool = True,
    benchmark: Optional[Union[str, pd.Series]] = None,
    curve_freq: str = "raw",
) -> dict[str, str]:
    """Build chart HTML sections from plot figures."""
    # Import here to avoid circular imports at module level
    from ._table_builder import _build_benchmark_sections
    from .report import _build_daily_returns_from_equity, _resolve_equity_curve

    config = {"responsive": True}
    strategy_config = {
        "responsive": True,
        "scrollZoom": True,
        "displayModeBar": True,
        "doubleClick": "reset",
    }

    equity_curve = _resolve_equity_curve(result, curve_freq)
    fig_dashboard = plot_dashboard(
        result, show=False, theme="light", equity_series=equity_curve
    )
    dashboard_html = (
        fig_dashboard.to_html(full_html=False, include_plotlyjs=False, config=config)
        if fig_dashboard
        else "<div>暂无数据</div>"
    )

    returns_series = _build_daily_returns_from_equity(equity_curve)
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
    benchmark_sections = _build_benchmark_sections(
        strategy_returns=returns_series,
        benchmark=benchmark,
        config=config,
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
    strategy_kline_html = "<div>未提供行情数据，已跳过 K 线复盘图</div>"
    if not include_trade_kline:
        strategy_kline_html = "<div>已关闭 K 线复盘图</div>"
    elif market_data is not None:
        symbol = _select_plot_symbol(result, market_data, plot_symbol)
        if symbol:
            symbol_data = _extract_symbol_market_data(market_data, symbol)
            if not symbol_data.empty:
                fig_strategy = plot_strategy(
                    result=result,
                    symbol=symbol,
                    data=symbol_data,
                    theme="light",
                    show=False,
                )
                if fig_strategy:
                    strategy_kline_html = fig_strategy.to_html(
                        full_html=False,
                        include_plotlyjs=False,
                        config=strategy_config,
                    )
                else:
                    strategy_kline_html = "<div>未能生成 K 线复盘图</div>"
            else:
                strategy_kline_html = "<div>行情数据不完整，无法绘制 K 线复盘图</div>"
    risk_reject_ratio_html = "<div>暂无策略级风控拒单占比图</div>"
    risk_reason_ratio_html = "<div>暂无策略级拒单原因占比图</div>"
    risk_reject_trend_html = "<div>暂无按日风控拒单趋势图</div>"
    risk_reject_trend_by_strategy_html = "<div>暂无按策略风控拒单趋势图</div>"
    risk_reason_trend_html = "<div>暂无按日拒单原因趋势图</div>"
    risk_other_reason_table_html = ""
    has_risk_ratio_chart = False
    has_risk_reason_ratio_chart = False
    has_risk_trend_chart = False
    has_risk_strategy_trend_chart = False
    has_risk_reason_trend_chart = False
    has_liquidation_count_chart = False
    has_liquidation_interest_chart = False
    total_reject_count = 0.0
    risk_df = (
        result.risk_rejections_by_strategy()
        if hasattr(result, "risk_rejections_by_strategy")
        else pd.DataFrame()
    )
    top_reasons_df = (
        result.top_reject_reasons(top_n=8)
        if hasattr(result, "top_reject_reasons")
        else pd.DataFrame()
    )

    # Import helpers from report module
    from .report import _format_table, _rename_table_columns

    if not top_reasons_df.empty:
        top_reasons_view = _rename_table_columns(
            top_reasons_df,
            {
                "reject_reason": "拒单原因 (Reject Reason)",
                "count": "拒单数 (Count)",
                "ratio": "占比 (Ratio)",
            },
        )
        top_reasons_table_html = _format_table(
            top_reasons_view,
            max_rows=8,
            percentage_columns={"占比 (Ratio)"},
            compact_currency=False,
        )
        risk_other_reason_table_html = (
            '<div class="chart-container" style="margin-top: 20px;">'
            "<h3 style='margin: 0 0 10px 0;'>"
            "拒单原因 Top 8 明细 (Top Reject Reasons)"
            "</h3>"
            f"{top_reasons_table_html}"
            "</div>"
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
            has_risk_ratio_chart = True
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
                has_risk_reason_ratio_chart = True
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
            has_risk_trend_chart = True
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
                has_risk_reason_trend_chart = True
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
            has_risk_strategy_trend_chart = True

    liquidation_audit_df = (
        result.liquidation_audit_df
        if hasattr(result, "liquidation_audit_df")
        else pd.DataFrame()
    )
    liquidation_count_chart_html = ""
    liquidation_interest_chart_html = ""
    if not liquidation_audit_df.empty:
        liq_df = liquidation_audit_df.copy()
        if "timestamp" in liq_df.columns:
            liq_df["timestamp"] = pd.to_datetime(liq_df["timestamp"], errors="coerce")
        elif "date" in liq_df.columns:
            liq_df["timestamp"] = pd.to_datetime(liq_df["date"], errors="coerce")
        else:
            liq_df["timestamp"] = pd.NaT
        liq_df = liq_df.dropna(subset=["timestamp"]).sort_values("timestamp")

        if not liq_df.empty and "liquidated_count" in liq_df.columns:
            liq_df["liquidated_count"] = pd.to_numeric(
                liq_df["liquidated_count"], errors="coerce"
            ).fillna(0.0)
            daily_liq = (
                liq_df.set_index("timestamp")["liquidated_count"].resample("D").sum()
            ).reset_index()
            if not daily_liq.empty and float(daily_liq["liquidated_count"].sum()) > 0.0:
                px = __import__("plotly.express", fromlist=["line"])
                fig_liq_count = px.line(
                    daily_liq,
                    x="timestamp",
                    y="liquidated_count",
                    markers=True,
                    title="按日强平标的数趋势 (Daily Liquidated Symbols Trend)",
                    labels={
                        "timestamp": "日期 (Date)",
                        "liquidated_count": "强平标的数 (Liquidated Symbols)",
                    },
                )
                fig_liq_count.update_layout(
                    height=320, margin=dict(l=20, r=20, t=60, b=20)
                )
                fig_liq_count.update_traces(
                    hovertemplate="日期=%{x}<br>强平标的数=%{y:.0f}<extra></extra>"
                )
                liquidation_count_chart_html = fig_liq_count.to_html(
                    full_html=False, include_plotlyjs=False, config=config
                )
                has_liquidation_count_chart = True

        if not liq_df.empty and "daily_interest" in liq_df.columns:
            liq_df["daily_interest"] = pd.to_numeric(
                liq_df["daily_interest"], errors="coerce"
            ).fillna(0.0)
            daily_interest = (
                liq_df.set_index("timestamp")["daily_interest"].resample("D").sum()
            ).reset_index()
            has_positive_interest = bool((daily_interest["daily_interest"] > 0.0).any())
            if not daily_interest.empty and has_positive_interest:
                px = __import__("plotly.express", fromlist=["bar"])
                fig_liq_interest = px.bar(
                    daily_interest,
                    x="timestamp",
                    y="daily_interest",
                    title="按日强平计息 (Daily Liquidation Interest)",
                    labels={
                        "timestamp": "日期 (Date)",
                        "daily_interest": "当日利息 (Daily Interest)",
                    },
                )
                fig_liq_interest.update_layout(
                    height=320, margin=dict(l=20, r=20, t=60, b=20)
                )
                fig_liq_interest.update_traces(
                    hovertemplate="日期=%{x}<br>当日利息=%{y:.4f}<extra></extra>"
                )
                liquidation_interest_chart_html = fig_liq_interest.to_html(
                    full_html=False, include_plotlyjs=False, config=config
                )
                has_liquidation_interest_chart = True

    risk_chart_blocks: list[str] = []

    def append_risk_chart_block(chart_html: str) -> None:
        risk_chart_blocks.append(
            (
                '<div class="chart-container" style="margin-top: 20px;">'
                f"{chart_html}"
                "</div>"
            )
        )

    if has_risk_ratio_chart:
        append_risk_chart_block(risk_reject_ratio_html)
    if has_risk_reason_ratio_chart:
        append_risk_chart_block(risk_reason_ratio_html)
    if has_risk_trend_chart:
        append_risk_chart_block(risk_reject_trend_html)
    if has_risk_strategy_trend_chart:
        append_risk_chart_block(risk_reject_trend_by_strategy_html)
    if has_risk_reason_trend_chart:
        append_risk_chart_block(risk_reason_trend_html)
    if has_liquidation_count_chart:
        append_risk_chart_block(liquidation_count_chart_html)
    if has_liquidation_interest_chart:
        append_risk_chart_block(liquidation_interest_chart_html)
    if risk_other_reason_table_html:
        risk_chart_blocks.append(risk_other_reason_table_html)

    if risk_chart_blocks:
        risk_charts_html = "".join(risk_chart_blocks)
    else:
        if risk_df.empty:
            reason_text = "本次回测未产生策略级风控拒单统计数据。"
        elif total_reject_count <= 0.0:
            reason_text = "本次回测风控拒单总数为 0，未触发拒单。"
        else:
            reason_text = "本次回测未形成可绘制的风控拒单图表。"
        risk_charts_html = (
            '<div class="chart-container" style="margin-top: 20px;">'
            '<div class="empty-panel">'
            f"{reason_text}<br>"
            "建议：可降低风险阈值或增加高波动样本，观察风控拒单分布与趋势。"
            "</div></div>"
        )

    return {
        "dashboard_html": dashboard_html,
        "yearly_returns_html": yearly_returns_html,
        "returns_dist_html": returns_dist_html,
        "rolling_metrics_html": rolling_metrics_html,
        "benchmark_metrics_html": benchmark_sections["benchmark_metrics_html"],
        "benchmark_chart_html": benchmark_sections["benchmark_chart_html"],
        "trades_dist_html": trades_dist_html,
        "pnl_duration_html": pnl_duration_html,
        "strategy_kline_html": strategy_kline_html,
        "risk_reject_ratio_html": risk_reject_ratio_html,
        "risk_reason_ratio_html": risk_reason_ratio_html,
        "risk_reject_trend_html": risk_reject_trend_html,
        "risk_reject_trend_by_strategy_html": risk_reject_trend_by_strategy_html,
        "risk_reason_trend_html": risk_reason_trend_html,
        "risk_charts_html": risk_charts_html,
    }
