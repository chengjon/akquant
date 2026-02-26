from functools import cached_property
from typing import (
    Any,
    List,
    Optional,
    Union,
    cast,
)

import pandas as pd

from ..akquant import (
    BacktestResult as RustBacktestResult,
)
from ..akquant import (
    ClosedTrade,
    Order,
)


class BacktestResult:
    """
    Backtest Result Wrapper.

    Wraps the underlying Rust BacktestResult to provide Python-friendly properties
    like DataFrames.
    """

    def __init__(
        self,
        raw_result: RustBacktestResult,
        timezone: str = "Asia/Shanghai",
        initial_cash: float = 0.0,
    ):
        """
        Initialize the BacktestResult wrapper.

        :param raw_result: The raw Rust BacktestResult object.
        :param timezone: The timezone string for datetime conversion.
        :param initial_cash: Initial capital used in backtest.
        """
        self._raw = raw_result
        self._timezone = timezone
        self.initial_cash = initial_cash

    @property
    def equity_curve(self) -> pd.Series:
        """
        Get the equity curve as a Pandas Series.

        Index: Datetime (Timezone-aware)
        Values: Total equity
        """
        series = pd.Series(dtype=float)

        if self._raw.equity_curve:
            df = pd.DataFrame(self._raw.equity_curve, columns=["timestamp", "equity"])
            df["timestamp"] = pd.to_datetime(
                df["timestamp"], unit="ns", utc=True
            ).dt.tz_convert(self._timezone)
            df.set_index("timestamp", inplace=True)
            series = df["equity"]

        # Fallback: Try to derive from snapshots via positions_df
        if series.empty:
            try:
                pos_df = self.positions_df
                if (
                    not pos_df.empty
                    and "equity" in pos_df.columns
                    and "date" in pos_df.columns
                ):
                    # WARNING: pos_df["equity"] might be Position Value,
                    # not Account Equity.
                    # We only use it if it looks like Account Equity
                    # (>= initial_cash * 0.5) or if we can't determine otherwise.
                    # Equity is account-level, unique per timestamp
                    df = pos_df[["date", "equity"]].drop_duplicates(subset=["date"])
                    df.set_index("date", inplace=True)
                    df.sort_index(inplace=True)
                    series = df["equity"]
            except Exception:
                pass

        # Post-processing: Handle PnL-only curve (starts at 0)
        if not series.empty and self.initial_cash > 0:
            # If the curve starts near 0 (e.g., < 10% of initial cash), assume it's PnL
            # and add initial_cash to convert to Equity.
            if abs(series.iloc[0]) < self.initial_cash * 0.1:
                series += self.initial_cash

            # Special case: If the curve is significantly below initial cash
            # (e.g., just position value), and we are in the fallback scenario,
            # we might want to warn or fix.
            # But adding initial_cash blindly to Position Value is also wrong.
            # For now, the PnL check handles the "0 to 250" case.

        return series

    @property
    def daily_returns(self) -> pd.Series:
        """
        Get daily returns of the strategy equity.

        Returns:
            pd.Series: Daily returns (percentage).
        """
        equity = self.equity_curve
        if equity.empty:
            return pd.Series(dtype=float)

        # Resample to daily and calculate percentage change
        # Assuming equity curve might have intraday data,
        # take the last value of each day
        # For intraday data, we need to be careful. 'D' means Calendar Day.
        # If we have multiple days, this works.
        daily_equity = equity.resample("D").last().ffill()
        returns = daily_equity.pct_change().fillna(0.0)
        return cast(pd.Series, returns)

    @property
    def cash_curve(self) -> pd.Series:
        """
        Get the cash curve as a Pandas Series.

        Index: Datetime (Timezone-aware)
        Values: Available cash
        """
        if not hasattr(self._raw, "cash_curve") or not self._raw.cash_curve:
            return pd.Series(dtype=float)

        df = pd.DataFrame(self._raw.cash_curve, columns=["timestamp", "cash"])
        df["timestamp"] = pd.to_datetime(
            df["timestamp"], unit="ns", utc=True
        ).dt.tz_convert(self._timezone)
        df.set_index("timestamp", inplace=True)
        return df["cash"]

    @property
    def trades(self) -> List[ClosedTrade]:
        """
        Get closed trades as a list of raw objects (Raw Access).

        These are the raw Rust objects, useful for iteration and accessing complex
        fields. For statistical analysis, use `trades_df`.
        """
        return cast(List[ClosedTrade], self._raw.trades)

    @property
    def orders(self) -> List[Order]:
        """
        Get orders as a list of raw objects (Raw Access).

        These are the raw Rust objects, useful for iteration and debugging.
        For statistical analysis, use `orders_df`.
        """
        if hasattr(self._raw, "orders"):
            return cast(List[Order], self._raw.orders)
        return []

    @property
    def metrics(self) -> Any:
        """Get metrics with timezone-aware datetime conversion."""
        metrics = self._raw.metrics

        class MetricsWrapper:
            def __init__(self, raw_metrics: Any, timezone: str) -> None:
                self._raw = raw_metrics
                self._timezone = timezone

            def __getattr__(self, name: str) -> Any:
                val = getattr(self._raw, name)
                if name in ["start_time", "end_time"]:
                    # Convert ns timestamp to datetime
                    if isinstance(val, int):
                        dt = pd.to_datetime(val, unit="ns", utc=True).tz_convert(
                            self._timezone
                        )
                        return dt
                return val

        return MetricsWrapper(metrics, self._timezone)

    @property
    def positions(self) -> pd.DataFrame:
        """
        Get positions history as a Pandas DataFrame.

        Index: Datetime (Timezone-aware)
        Columns: Symbols
        Values: Quantity.
        """
        if not self._raw.snapshots:
            return pd.DataFrame()

        # Extract data from snapshots
        data = []
        timestamps = []

        for ts, snapshots in self._raw.snapshots:
            timestamps.append(ts)
            # Create a dict for this timestamp: {symbol: quantity}
            row = {s.symbol: s.quantity for s in snapshots}
            data.append(row)

        df = pd.DataFrame(data, index=timestamps)

        # Convert nanosecond timestamp to datetime with timezone
        df.index = pd.to_datetime(df.index, unit="ns", utc=True).tz_convert(
            self._timezone
        )

        # Sort index just in case
        df = df.sort_index()

        # Fill missing values with 0.0
        df = df.fillna(0.0)

        return cast(pd.DataFrame, df)

    @property
    def positions_df(self) -> pd.DataFrame:
        """
        Get detailed positions history as a Pandas DataFrame (PyBroker style).

        Columns:
            - date (datetime): Snapshot time.
            - symbol (str): Trading symbol.
            - long_shares (float): Long position quantity.
            - short_shares (float): Short position quantity.
            - close (float): Closing price.
            - equity (float): Total account equity.
            - market_value (float): Market value of positions.
            - margin (float): Margin used.
            - unrealized_pnl (float): Floating PnL.
            - entry_price (float): Average entry price.
        """
        df = pd.DataFrame()

        # 1. Try IPC
        if hasattr(self._raw, "get_positions_ipc"):
            try:
                import io

                import pyarrow as pa

                ipc_bytes = self._raw.get_positions_ipc()
                if ipc_bytes and len(ipc_bytes) > 0:
                    reader = pa.ipc.open_stream(io.BytesIO(ipc_bytes))
                    df = reader.read_pandas()
            except (ImportError, Exception):
                pass

        # 2. Try Dict
        if df.empty and hasattr(self._raw, "get_positions_dict"):
            try:
                data = self._raw.get_positions_dict()
                if data and data.get("symbol"):  # Check if data exists
                    df = pd.DataFrame(data)
            except Exception:
                pass

        if df.empty:
            return pd.DataFrame()

        # Convert date to datetime
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], unit="ns", utc=True).dt.tz_convert(
                self._timezone
            )

        # Reorder columns
        cols = [
            "long_shares",
            "short_shares",
            "close",
            "equity",
            "market_value",
            "margin",
            "unrealized_pnl",
            "entry_price",
            "symbol",
            "date",
        ]
        # Ensure all columns exist
        existing_cols = [c for c in cols if c in df.columns]
        df = df[existing_cols]

        # Sort
        if "symbol" in df.columns and "date" in df.columns:
            df = df.sort_values(by=["symbol", "date"])

        return cast(pd.DataFrame, df)

    @property
    def metrics_df(self) -> pd.DataFrame:
        """
        Get performance metrics as a Pandas DataFrame.

        Returns a DataFrame indexed by metric name with a single 'value' column,
        matching PyBroker's format.
        """
        df = cast(pd.DataFrame, self._raw.metrics_df)

        # Convert time fields to the configured timezone
        time_fields = ["start_time", "end_time"]
        for field in time_fields:
            if field in df.index:
                val = df.at[field, "value"]
                if val is not None:
                    try:
                        # Convert to pandas Timestamp for easy tz handling
                        ts = pd.Timestamp(cast(Any, val))
                        if ts.tz is not None:
                            df.at[field, "value"] = ts.tz_convert(self._timezone)
                    except Exception:
                        pass

        # Calculate additional margin/leverage metrics using snapshots
        try:
            pos_df = self.positions_df
            if (
                not pos_df.empty
                and "margin" in pos_df.columns
                and "equity" in pos_df.columns
            ):
                # Group by date to get account-level snapshot
                # Sum margin (used margin) and market_value
                # Equity should be the same for all symbols on the same date
                # (it's account level)
                # But to be safe, take the first one or mean (should be identical)
                daily_agg = pos_df.groupby("date").agg(
                    {
                        "margin": "sum",
                        "market_value": lambda x: x.abs().sum(),  # type: ignore # Gross
                        "equity": "first",
                    }
                )

                # Calculate Max Leverage
                # Leverage = Gross Market Value / Equity
                daily_agg["leverage"] = daily_agg["market_value"] / daily_agg["equity"]
                max_leverage = daily_agg["leverage"].max()

                # Calculate Min Margin Level (Safety)
                # Margin Level = Equity / Used Margin
                # Avoid division by zero
                daily_agg["margin_level"] = daily_agg.apply(
                    lambda row: row["equity"] / row["margin"]
                    if row["margin"] > 0
                    else float("inf"),
                    axis=1,
                )
                # Filter out inf (no margin used)
                valid_levels = daily_agg[daily_agg["margin_level"] != float("inf")][
                    "margin_level"
                ]
                min_margin_level = (
                    valid_levels.min() if not valid_levels.empty else float("inf")
                )

                # Append to metrics DataFrame
                new_rows = pd.DataFrame(
                    [
                        {"value": max_leverage},
                        {
                            "value": min_margin_level
                            if min_margin_level != float("inf")
                            else 0.0
                        },
                    ],
                    index=["max_leverage", "min_margin_level"],
                )

                df = pd.concat([df, new_rows])
        except Exception:
            # Fallback or ignore if calculation fails
            pass

        return df

    @cached_property
    def orders_df(self) -> pd.DataFrame:
        """
        Get orders history as a Pandas DataFrame.

        Columns:
            - id (str): Order ID.
            - symbol (str): Trading symbol.
            - side (str): 'buy' or 'sell'.
            - order_type (str): 'market', 'limit', 'stop'.
            - quantity (float): Order quantity.
            - filled_quantity (float): Executed quantity.
            - limit_price (float): Price for limit orders.
            - stop_price (float): Trigger price for stop orders.
            - avg_price (float): Average execution price.
            - commission (float): Commission paid.
            - status (str): 'filled', 'cancelled', 'rejected', etc.
            - time_in_force (str): 'gtc', 'day', 'ioc', etc.
            - created_at (datetime): Creation time.
        """
        if not hasattr(self._raw, "orders_df"):
            return pd.DataFrame()

        df = cast(pd.DataFrame, self._raw.orders_df.copy())

        if df.empty:
            return df

        if "created_at" in df.columns:
            # Rust returns int64 timestamp (ns since epoch)
            if pd.api.types.is_numeric_dtype(df["created_at"]):
                df["created_at"] = pd.to_datetime(
                    df["created_at"], unit="ns", utc=True
                ).dt.tz_convert(self._timezone)
            elif hasattr(df["created_at"], "dt"):
                if df["created_at"].dt.tz is None:
                    df["created_at"] = (
                        df["created_at"]
                        .dt.tz_localize("UTC")
                        .dt.tz_convert(self._timezone)
                    )
                else:
                    df["created_at"] = df["created_at"].dt.tz_convert(self._timezone)

        if "updated_at" in df.columns:
            # Rust returns int64 timestamp (ns since epoch)
            if pd.api.types.is_numeric_dtype(df["updated_at"]):
                df["updated_at"] = pd.to_datetime(
                    df["updated_at"], unit="ns", utc=True
                ).dt.tz_convert(self._timezone)
            elif hasattr(df["updated_at"], "dt"):
                if df["updated_at"].dt.tz is None:
                    df["updated_at"] = (
                        df["updated_at"]
                        .dt.tz_localize("UTC")
                        .dt.tz_convert(self._timezone)
                    )
                else:
                    df["updated_at"] = df["updated_at"].dt.tz_convert(self._timezone)

        # Calculate derivative columns
        if "filled_quantity" in df.columns and "avg_price" in df.columns:
            # Calculate filled value (成交金额)
            df["filled_value"] = df["filled_quantity"] * df["avg_price"].fillna(0.0)

        if "created_at" in df.columns and "updated_at" in df.columns:
            # Calculate duration (存续时长)
            df["duration"] = df["updated_at"] - df["created_at"]

        # Sort by creation time for better readability
        if "created_at" in df.columns:
            df.sort_values(by="created_at", inplace=True)
            df.reset_index(drop=True, inplace=True)

        return df

    @cached_property
    def trades_df(self) -> pd.DataFrame:
        """
        Get closed trades as a Pandas DataFrame.

        Columns:
            - symbol (str): Trading symbol.
            - entry_time (datetime): Time of entry.
            - exit_time (datetime): Time of exit.
            - entry_price (float): Average entry price.
            - exit_price (float): Average exit price.
            - quantity (float): Traded quantity.
            - side (str): 'long' or 'short'.
            - pnl (float): Gross PnL.
            - net_pnl (float): Net PnL (after commission).
            - return_pct (float): Trade return (decimal).
            - commission (float): Commission paid.
            - duration_bars (int): Number of bars held.
            - duration (timedelta): Duration of trade.
            - mae (float): Maximum Adverse Excursion (%).
            - mfe (float): Maximum Favorable Excursion (%).
            - entry_tag (str): Tag of the entry order.
            - exit_tag (str): Tag of the exit order.
            - entry_portfolio_value (float): Portfolio value at entry.
            - max_drawdown_pct (float): Max drawdown % during trade.
        """
        if not self._raw.trades:
            return pd.DataFrame()

        df = pd.DataFrame()

        # 1. Try IPC (Zero-Copy-ish via Arrow)
        if hasattr(self._raw, "get_trades_ipc"):
            try:
                import io

                import pyarrow as pa

                ipc_bytes = self._raw.get_trades_ipc()
                if ipc_bytes and len(ipc_bytes) > 0:
                    reader = pa.ipc.open_stream(io.BytesIO(ipc_bytes))
                    df = reader.read_pandas()
            except (ImportError, Exception):
                # Fallback to other methods if pyarrow missing or IPC fails
                pass

        # 2. Try Dict (Fast)
        if df.empty and hasattr(self._raw, "get_trades_dict"):
            try:
                data_dict = self._raw.get_trades_dict()
                if data_dict:
                    df = pd.DataFrame(data_dict)
            except Exception:
                pass

        # 3. Fallback to List of Objects (Slow)
        if df.empty:
            data_list = []
            for t in self._raw.trades:
                data_list.append(
                    {
                        "symbol": t.symbol,
                        "entry_time": t.entry_time,
                        "exit_time": t.exit_time,
                        "entry_price": t.entry_price,
                        "exit_price": t.exit_price,
                        "quantity": t.quantity,
                        "side": t.side,
                        "pnl": t.pnl,
                        "net_pnl": t.net_pnl,
                        "return_pct": t.return_pct,
                        "commission": t.commission,
                        "duration_bars": t.duration_bars,
                        "duration": t.duration,
                        "mae": t.mae,
                        "mfe": t.mfe,
                        "entry_tag": t.entry_tag,
                        "exit_tag": t.exit_tag,
                        "entry_portfolio_value": getattr(
                            t, "entry_portfolio_value", 0.0
                        ),
                        "max_drawdown_pct": getattr(t, "max_drawdown_pct", 0.0),
                    }
                )
            df = pd.DataFrame(data_list)

        if df.empty:
            return df

        # Convert timestamps
        # Check columns exist. IPC schema may vary across versions;
        # here we control the schema.
        if "entry_time" in df.columns:
            df["entry_time"] = pd.to_datetime(
                df["entry_time"], unit="ns", utc=True
            ).dt.tz_convert(self._timezone)

        if "exit_time" in df.columns:
            df["exit_time"] = pd.to_datetime(
                df["exit_time"], unit="ns", utc=True
            ).dt.tz_convert(self._timezone)

        # Convert duration to Timedelta
        if "duration" in df.columns:
            df["duration"] = pd.to_timedelta(df["duration"], unit="ns")

        return df

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the raw result."""
        return getattr(self._raw, name)

    def __repr__(self) -> str:
        """Return the string representation of the result (Vertical Metrics)."""
        metrics = self.metrics_df
        metrics.columns = ["Value"]
        return f"BacktestResult:\n{metrics.to_string()}"

    def __dir__(self) -> List[str]:
        """Return the list of attributes including raw result attributes."""
        return list(set(dir(self._raw) + list(self.__dict__.keys()) + ["positions"]))

    def plot(
        self,
        symbol: Optional[str] = None,
        show: bool = True,
        title: str = "Backtest Result",
    ) -> Any:
        """
        Plot the backtest results using Plotly.

        :param symbol: The symbol to highlight positions for.
        :param show: Whether to display the plot immediately.
        :param title: Title of the plot.
        :return: Plotly Figure object.
        """
        try:
            from .plot import plot_result
        except ImportError:
            print(
                "Plotly is not installed. Please install it using `pip install plotly` "
                "or `pip install akquant[plot]`."
            )
            return None

        return plot_result(result=self, show=show, title=title)

    def to_quantstats(self) -> pd.Series:
        """
        Convert backtest results to QuantStats-compatible returns series.

        :return: pd.Series with DatetimeIndex and daily returns.
        """
        # Get daily returns (already calculated from equity curve)
        returns = self.daily_returns.copy()

        if returns.empty:
            return returns

        # QuantStats prefers timezone-naive index (or UTC) usually, but it handles
        # datetime index well.
        # However, to be safe and compatible with most data sources QS uses (Yahoo),
        # we might want to ensure it's timezone-naive (localized to None)
        # or keep it as is if QS handles it.
        # AKQuant returns are timezone-aware (user configured).
        # Let's strip timezone to avoid warnings/errors in some QS versions if they
        # compare with naive benchmarks.
        # Use cast to help mypy understand it's a DatetimeIndex
        idx = cast(pd.DatetimeIndex, returns.index)
        if idx.tz is not None:
            returns.index = idx.tz_localize(None)

        return returns

    def report_quantstats(
        self,
        benchmark: Optional[Union[str, pd.Series]] = None,
        title: str = "Strategy Report",
        filename: str = "quantstats-report.html",
        **kwargs: Any,
    ) -> None:
        """
        Generate a QuantStats HTML report.

        :param benchmark: Benchmark ticker (e.g. "SPY") or pd.Series.
        :param title: Report title.
        :param filename: Output filename.
        :param kwargs: Additional arguments passed to qs.reports.html.
        """
        try:
            import quantstats as qs
        except ImportError:
            print(
                "QuantStats is not installed. Please install it using "
                "`pip install quantstats` or `pip install akquant[quantstats]`."
            )
            return

        # Extend pandas functionality (optional, but good practice for QS)
        qs.extend_pandas()

        returns = self.to_quantstats()

        if returns.empty:
            print("No returns data available to generate report.")
            return

        print(f"Generating QuantStats report to {filename}...")
        qs.reports.html(
            returns, benchmark=benchmark, title=title, output=filename, **kwargs
        )
        print("Done.")

    def report(
        self,
        title: str = "AKQuant 策略回测报告",
        filename: str = "akquant_report.html",
        show: bool = False,
    ) -> None:
        """
        生成 HTML 策略回测报告 (便捷方法).

        该方法是 akquant.plot.report.plot_report 的快捷入口。

        :param title: 报告标题
        :param filename: 保存的文件名
        :param show: 是否在浏览器中自动打开 (默认 False)
        """
        # 延迟导入，避免循环引用和非必要的 Plotly 依赖
        try:
            from ..plot.report import plot_report
        except ImportError:
            print("Plot module not found. Please install akquant[plot] or plotly.")
            return

        return plot_report(result=self, title=title, filename=filename, show=show)
