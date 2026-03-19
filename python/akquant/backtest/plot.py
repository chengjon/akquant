from typing import Any, Optional

import pandas as pd

from ..utils import format_metric_value


def plot_result(
    result: Any,
    show: bool = True,
    filename: Optional[str] = None,
    benchmark: Optional[pd.Series] = None,
    title: str = "Strategy Performance Analysis",
) -> None:
    """
    绘制回测结果 (权益曲线、回撤、日收益率).

    :param result: BacktestResult 对象
    :param show: 是否调用 plt.show()
    :param filename: 保存图片的文件名
    :param benchmark: 基准收益率序列 (可选, Series with DatetimeIndex)
    :param title: 图表标题
    """
    try:
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
        from matplotlib.gridspec import GridSpec
    except ImportError:
        print(
            "Error: matplotlib is required for plotting. "
            "Please install it via 'pip install matplotlib'."
        )
        return

    # Extract data
    equity_curve = result.equity_curve  # List[Tuple[int, float]]

    if not equity_curve:
        print("No equity curve data to plot.")
        return

    # Check if timestamp is in nanoseconds (e.g. > 1e11)
    # 1e11 seconds is roughly year 5138, so valid seconds are < 1e11
    # 1e18 nanoseconds is roughly year 2001
    first_ts = equity_curve[0][0]
    scale = 1.0
    if first_ts > 1e11:
        scale = 1e-9

    # Use UTC to avoid local timezone issues and align with benchmark data
    from datetime import datetime, timezone

    times = [
        datetime.fromtimestamp(t * scale, tz=timezone.utc).replace(tzinfo=None)
        for t, _ in equity_curve
    ]
    equity = [e for _, e in equity_curve]

    # Convert to DataFrame for easier calculation
    df = pd.DataFrame({"equity": equity}, index=times)
    df.index.name = "Date"
    df["returns"] = df["equity"].pct_change().fillna(0)

    # Calculate Drawdown
    rolling_max = df["equity"].cummax()
    drawdown = (df["equity"] - rolling_max) / rolling_max

    # Create figure with GridSpec
    fig = plt.figure(figsize=(14, 10))
    # 3 rows: Equity (3), Drawdown (1), Daily Returns (1)
    gs = GridSpec(3, 1, height_ratios=[3, 1, 1], hspace=0.05)

    # 1. Equity Curve
    ax1 = fig.add_subplot(gs[0])
    ax1.plot(df.index, df["equity"], label="Strategy", color="#1f77b4", linewidth=1.5)

    if benchmark is not None:
        # Align benchmark to strategy dates
        try:
            # Ensure benchmark has DatetimeIndex
            if not isinstance(benchmark.index, pd.DatetimeIndex):
                benchmark.index = pd.to_datetime(benchmark.index)

            # Normalize timezones: ensure benchmark is tz-naive UTC
            if benchmark.index.tz is not None:
                benchmark.index = benchmark.index.tz_convert("UTC").tz_localize(None)

            # Reindex benchmark to match strategy dates (forward fill for missing days)
            # Normalize dates to start of day for alignment if needed
            # For simplicity, we just plot what overlaps

            # Calculate cumulative return of benchmark
            bench_cum = (1 + benchmark).cumprod()

            # Rebase benchmark to match initial strategy equity
            initial_equity = df["equity"].iloc[0]
            if not bench_cum.empty:
                # Align start
                # Find the closest date in benchmark to start date
                start_date = df.index[0]
                if start_date in bench_cum.index:
                    base_val = bench_cum.loc[start_date]
                else:
                    # Fallback: use first available
                    base_val = bench_cum.iloc[0]

                bench_scaled = (bench_cum / base_val) * initial_equity

                # Filter to strategy range
                bench_plot = bench_scaled[df.index[0] : df.index[-1]]  # type: ignore
                ax1.plot(
                    bench_plot.index,
                    bench_plot,
                    label="Benchmark",
                    color="gray",
                    linestyle="--",
                    alpha=0.7,
                )
        except Exception as e:
            print(f"Warning: Failed to plot benchmark: {e}")

    ax1.set_title(title, fontsize=14, fontweight="bold")
    ax1.set_ylabel("Equity", fontsize=10)
    ax1.grid(True, linestyle="--", alpha=0.3)
    ax1.legend(loc="upper left", frameon=True, fancybox=True, framealpha=0.8)

    # Add Metrics Text Box
    metrics = result.metrics
    trade_metrics = result.trade_metrics
    total_return_display = format_metric_value(
        "total_return_pct", metrics.total_return_pct, width=8
    )
    annualized_display = format_metric_value(
        "annualized_return", metrics.annualized_return, width=8
    )
    max_drawdown_display = format_metric_value(
        "max_drawdown_pct", metrics.max_drawdown_pct, width=8
    )
    win_rate_display = format_metric_value("win_rate", metrics.win_rate, width=8)

    metrics_text = [
        f"Total Return: {total_return_display}",
        f"Annualized:   {annualized_display}",
        f"Sharpe Ratio: {metrics.sharpe_ratio:>8.2f}",
        f"Max Drawdown: {max_drawdown_display}",
        f"Win Rate:     {win_rate_display}",
    ]

    if hasattr(trade_metrics, "total_closed_trades"):
        metrics_text.append(f"Trades:       {trade_metrics.total_closed_trades:>8d}")

    text_str = "\n".join(metrics_text)

    props = dict(boxstyle="round", facecolor="white", alpha=0.8, edgecolor="lightgray")
    ax1.text(
        0.02,
        0.05,
        text_str,
        transform=ax1.transAxes,
        fontsize=9,
        verticalalignment="bottom",
        fontfamily="monospace",
        bbox=props,
    )

    # 2. Drawdown
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax2.fill_between(
        df.index, drawdown, 0, color="#d62728", alpha=0.3, label="Drawdown"
    )
    ax2.plot(df.index, drawdown, color="#d62728", linewidth=0.8, alpha=0.8)
    ax2.set_ylabel("Drawdown", fontsize=10)
    ax2.grid(True, linestyle="--", alpha=0.3)
    # ax2.legend(loc='lower right', fontsize=8)

    # 3. Daily Returns
    ax3 = fig.add_subplot(gs[2], sharex=ax1)
    ax3.bar(
        df.index,
        df["returns"],
        color="gray",
        alpha=0.5,
        label="Daily Returns",
        width=1.0 if len(df) < 100 else 0.8,
    )
    # Highlight extreme returns? No, keep simple.
    ax3.set_ylabel("Returns", fontsize=10)
    ax3.grid(True, linestyle="--", alpha=0.3)

    # Format X axis
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.setp(ax1.get_xticklabels(), visible=False)
    plt.setp(ax2.get_xticklabels(), visible=False)
    plt.xticks(rotation=0)

    # Adjust margins
    plt.subplots_adjust(top=0.95, bottom=0.05, left=0.08, right=0.95)

    if filename:
        plt.savefig(filename, dpi=100, bbox_inches="tight")
        print(f"Plot saved to {filename}")

    if show:
        plt.show()
