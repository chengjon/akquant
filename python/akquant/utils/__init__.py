from typing import Dict, List, Literal, Optional, Tuple, Union, cast

import numpy as np
import pandas as pd

from ..akquant import Bar, from_arrays


def load_bar_from_df(
    df: pd.DataFrame,
    symbol: Optional[str] = None,
    column_map: Optional[Dict[str, str]] = None,
) -> List[Bar]:
    r"""
    Convert DataFrame to list of akquant.Bar.

    :param df: Historical market data
    :type df: pandas.DataFrame
    :param symbol: Symbol code; if not provided, try to use "symbol" column
    :type symbol: str, optional
    :param column_map: Mapping from DataFrame columns to standard fields.
                       Defaults: date->timestamp, open->open, etc.
    :type column_map: Dict[str, str], optional
    :return: List of Bar objects
    :rtype: List[Bar]
    """
    if df.empty:
        return []

    # Default mapping
    required_map = {
        "date": "timestamp",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
    }

    if column_map:
        required_map.update(column_map)

    # Reverse map to find dataframe columns
    # We need to find which df column corresponds to 'timestamp', 'open', etc.
    # required_map is DF_COL -> STANDARD_FIELD
    # So we want to check if keys of required_map exist in df.columns

    # Actually, let's flip logic slightly to be more robust.
    # Users pass { "my_date": "date", "my_open": "open" } ?
    # Or { "date": "my_date", "open": "my_open" } ?
    # The previous implementation had: required_map = {"日期": "timestamp", ...}
    # implying Key is DF Column, Value is Internal Field.

    # Let's keep that convention.

    # Check for required internal fields
    internal_fields = ["timestamp", "open", "high", "low", "close", "volume"]

    # Find which DF column maps to which internal field
    field_to_col = {}
    for col, field in required_map.items():
        if field in internal_fields:
            field_to_col[field] = col

    # Check if all internal fields have a corresponding column in DF
    missing_fields = []
    for field in internal_fields:
        if field not in field_to_col:
            # try finding exact match in df
            if field in df.columns:
                field_to_col[field] = field
            else:
                missing_fields.append(field)
        else:
            if field_to_col[field] not in df.columns:
                missing_fields.append(f"{field} (mapped to {field_to_col[field]})")

    if missing_fields:
        raise ValueError(f"DataFrame missing columns for fields: {missing_fields}")

    # Vectorized Preprocessing

    # 1. Handle Timestamp
    col_date = field_to_col["timestamp"]
    # Convert to datetime with error coercion (invalid dates becomes NaT)
    dt_series = pd.to_datetime(df[col_date], errors="coerce")
    # Fill NaT with 0 (Epoch 0) or handle appropriately
    dt_series = dt_series.fillna(pd.Timestamp(0))
    # type: ignore
    if dt_series.dt.tz is None:
        dt_series = dt_series.dt.tz_localize("Asia/Shanghai")
    dt_series = dt_series.dt.tz_convert("UTC")
    timestamps = dt_series.astype("int64").values

    # 2. Extract numeric columns
    # Use astype(float) to ensure correct type, fillna(0.0) for safety
    opens = df[field_to_col["open"]].fillna(0.0).astype(float).values
    highs = df[field_to_col["high"]].fillna(0.0).astype(float).values
    lows = df[field_to_col["low"]].fillna(0.0).astype(float).values
    closes = df[field_to_col["close"]].fillna(0.0).astype(float).values
    volumes = df[field_to_col["volume"]].fillna(0.0).astype(float).values

    # 3. Handle Symbol
    symbols_list: Optional[List[str]] = None
    symbol_val = None

    if symbol:
        symbol_val = symbol
    elif "股票代码" in df.columns:
        # Convert to string
        symbols_list = cast(List[str], df["股票代码"].astype(str).tolist())
    else:
        symbol_val = "UNKNOWN"

    # Call Rust extension
    bars = from_arrays(
        timestamps, opens, highs, lows, closes, volumes, symbol_val, symbols_list, None
    )

    # Auto-fix timestamps if they appear to be in seconds (small magnitude)
    # 10_000_000_000 seconds is year 2286.
    # Valid nanosecond timestamps for 2023 are around 1.6e18.
    if bars and bars[0].timestamp < 10_000_000_000:
        for bar in bars:
            bar.timestamp = bar.timestamp * 1_000_000_000

    return bars


def fetch_akshare_symbol(
    symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
) -> pd.DataFrame:
    """
    Fetch daily data from AKShare for a given symbol.

    Automatically handles market prefixes.

    :param symbol: Stock symbol (e.g., "600519", "000858")
    :param start_date: Start date string (e.g., "20231001")
    :param end_date: End date string (e.g., "20231101")
    :param adjust: Adjustment type ("qfq", "hfq", ""). Default "qfq".
    :return: DataFrame with standardized columns compatible with AKQuant.
    """
    try:
        import akshare as ak
    except ImportError:
        raise ImportError(
            "AKShare is not installed. Please install it via 'pip install akshare'."
        )

    # Determine market prefix
    ak_symbol = symbol
    if symbol.isdigit():
        if symbol.startswith("6"):
            ak_symbol = f"sh{symbol}"
        elif symbol.startswith("0") or symbol.startswith("3"):
            ak_symbol = f"sz{symbol}"
        elif symbol.startswith("4") or symbol.startswith("8"):
            ak_symbol = f"bj{symbol}"

    # print(f"Fetching {ak_symbol} from AKShare...")
    try:
        df = ak.stock_zh_a_daily(
            symbol=ak_symbol, start_date=start_date, end_date=end_date, adjust=adjust
        )
    except Exception:
        # Fallback or retry
        df = pd.DataFrame()

    if df.empty:
        # Try without prefix if failed (just in case akshare changes behavior)
        try:
            df = ak.stock_zh_a_daily(
                symbol=symbol, start_date=start_date, end_date=end_date, adjust=adjust
            )
        except Exception:
            pass

    if df.empty:
        raise ValueError(
            f"No data found for {symbol} ({ak_symbol}) between {start_date} and "
            f"{end_date}"
        )

    # Standardize columns
    rename_map = {
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
    }
    df = df.rename(columns=rename_map)

    # Ensure date is datetime
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])

    return cast(pd.DataFrame, df)


def parse_duration_to_bars(duration: Union[str, int], frequency: str = "1d") -> int:
    """
    Parse duration string to number of bars.

    Assumes A-share trading hours for intraday frequencies.

    :param duration: Duration string (e.g. "1y", "3m", "20d") or integer bars.
    :param frequency: Data frequency ("1d", "1h", "1m"). Default "1d".
    :return: Estimated number of bars.
    """
    if isinstance(duration, int):
        return duration

    import re

    match = re.match(r"(\d+)([ymwd])", duration.lower())
    if not match:
        # Try to parse as int string
        try:
            return int(duration)
        except ValueError:
            raise ValueError(f"Invalid duration format: {duration}")

    value = int(match.group(1))
    unit = match.group(2)

    # Estimated bars per day (A-share)
    if frequency == "1d":
        bars_per_day = 1
    elif frequency == "1h":
        bars_per_day = 4
    elif frequency == "30m":
        bars_per_day = 8
    elif frequency == "15m":
        bars_per_day = 16
    elif frequency == "5m":
        bars_per_day = 48
    elif frequency == "1m":
        bars_per_day = 240
    else:
        bars_per_day = 1

    if unit == "y":
        return int(value * 252 * bars_per_day)
    elif unit == "m":
        return int(value * 21 * bars_per_day)
    elif unit == "w":
        return int(value * 5 * bars_per_day)
    elif unit == "d":
        return int(value * bars_per_day)

    return value


def df_to_arrays(
    df: pd.DataFrame, symbol: Optional[str] = None
) -> Tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    Optional[str],
    Optional[List[str]],
    Optional[Dict[str, np.ndarray]],
]:
    r"""
    将 DataFrame 转换为用于 DataFeed.add_arrays 的数组元组.

    :param df: 输入的 DataFrame
    :param symbol: 标的代码 (可选)
    :return: (timestamps, opens, highs, lows, closes, volumes, symbol, symbols, extra)
    """
    if df.empty:
        return (
            np.array([], dtype=np.int64),
            np.array([], dtype=np.float64),
            np.array([], dtype=np.float64),
            np.array([], dtype=np.float64),
            np.array([], dtype=np.float64),
            np.array([], dtype=np.float64),
            symbol,
            None,
            None,
        )

    # Column Mapping Strategy
    # Priority:
    # 1. AKShare Chinese columns: "日期", "开盘", ...
    # 2. Standard English columns: "date", "open", ...
    # 3. Lowercase normalized check

    # Define targets
    targets = {
        "timestamp": ["日期", "date", "datetime", "time", "timestamp"],
        "open": ["开盘", "open"],
        "high": ["最高", "high"],
        "low": ["最低", "low"],
        "close": ["收盘", "close"],
        "volume": ["成交量", "volume", "vol"],
        "symbol": ["股票代码", "symbol", "code", "ticker"],
    }

    # Resolve columns
    df_cols = df.columns
    df_cols_lower = [str(c).lower() for c in df_cols]

    resolved = {}

    for key, candidates in targets.items():
        found = None
        for cand in candidates:
            if cand in df_cols:
                found = cand
                break

        # If not found, try case-insensitive
        if not found:
            for cand in candidates:
                if cand.lower() in df_cols_lower:
                    idx = df_cols_lower.index(cand.lower())
                    found = str(df_cols[idx])
                    break

        if found:
            resolved[key] = found

    # Check essential columns
    missing = []
    for essential in ["timestamp", "open", "high", "low", "close", "volume"]:
        if essential not in resolved:
            missing.append(essential)

    if missing:
        # If timestamp is index, handle it
        if isinstance(df.index, pd.DatetimeIndex):
            resolved["timestamp"] = "__index__"
            missing = [m for m in missing if m != "timestamp"]

        if missing:
            msg = f"Missing columns: {missing}. Available: {df.columns.tolist()}"
            raise ValueError(msg)

    # 1. Handle Timestamp
    dt_series: Union[pd.Series, pd.Index]
    if resolved.get("timestamp") == "__index__":
        dt_series = df.index
    else:
        dt_series = pd.to_datetime(df[resolved["timestamp"]], errors="coerce")

    if not isinstance(dt_series, pd.DatetimeIndex):
        dt_series = pd.to_datetime(dt_series)

    # Ensure nanosecond resolution
    if hasattr(dt_series, "astype"):
        # Check if tz-aware to avoid TypeError
        is_aware = False
        if isinstance(dt_series, pd.DatetimeIndex):
            is_aware = dt_series.tz is not None
        elif hasattr(dt_series, "dt"):
            is_aware = dt_series.dt.tz is not None

        if not is_aware:
            dt_series = dt_series.astype("datetime64[ns]")

    dt_series = dt_series.fillna(pd.Timestamp(0))

    # Handle timezone (support both Series and DatetimeIndex)
    # Convert to Series for consistent handling
    dt_series_s: pd.Series
    if isinstance(dt_series, pd.Index):
        dt_series_s = dt_series.to_series(index=dt_series)
    else:
        dt_series_s = cast(pd.Series, dt_series)

    # Help mypy know it's a Series
    if dt_series_s.dt.tz is None:
        dt_series_s = dt_series_s.dt.tz_localize("Asia/Shanghai")
    dt_series_s = dt_series_s.dt.tz_convert("UTC")

    # Force nanosecond resolution before converting to int64
    if not str(dt_series_s.dtype).startswith("datetime64[ns"):
        try:
            dt_series_s = dt_series_s.astype("datetime64[ns, UTC]")
        except Exception:
            # Fallback for older pandas or incompatible types
            pass

    timestamps = cast(np.ndarray, dt_series_s.astype("int64").values)

    # 2. Extract numeric columns
    def get_col(name: str) -> np.ndarray:
        return cast(np.ndarray, df[resolved[name]].fillna(0.0).astype(float).values)

    opens = get_col("open")
    highs = get_col("high")
    lows = get_col("low")
    closes = get_col("close")
    volumes = get_col("volume")

    # 3. Handle Symbol
    symbols_list: Optional[List[str]] = None
    symbol_val = None

    if symbol:
        symbol_val = symbol
    elif "symbol" in resolved:
        symbols_list = cast(List[str], df[resolved["symbol"]].astype(str).tolist())
    else:
        symbol_val = "UNKNOWN"

    # 4. Handle Extra Columns
    extra = {}
    used_columns = set(resolved.values())

    # Iterate over all columns to find numeric ones not in resolved
    for col in df.columns:
        if col in used_columns:
            continue

        # Try to convert to float
        try:
            # We use fillna(0.0) for safety, similar to other fields
            # Check if column is numeric
            if pd.api.types.is_numeric_dtype(df[col]):
                extra[str(col)] = cast(
                    np.ndarray, df[col].fillna(0.0).astype(float).values
                )
        except Exception:
            # Skip non-numeric extra columns
            pass

    # print(f"DEBUG: df_to_arrays extra keys: {list(extra.keys())}")
    return (
        timestamps,
        opens,
        highs,
        lows,
        closes,
        volumes,
        symbol_val,
        symbols_list,
        extra if extra else None,
    )


def prepare_dataframe(
    df: pd.DataFrame, date_col: Optional[str] = None, tz: str = "Asia/Shanghai"
) -> pd.DataFrame:
    r"""
    自动预处理 DataFrame，处理时区并生成标准时间戳列.

    :param df: 输入 DataFrame
    :param date_col: 日期列名 (若为 None 则自动探测)
    :param tz: 默认时区 (若数据为 Naive 时间，则假定为此时区)
    :return: 处理后的 DataFrame (包含 'timestamp' 列)
    """
    df = df.copy()

    # 1. Auto-detect date column
    if date_col is None:
        candidates = ["date", "datetime", "time", "timestamp", "日期", "时间"]
        for c in candidates:
            if c in df.columns:
                date_col = c
                break

    if date_col and date_col in df.columns:
        # 2. Convert to datetime
        dt = pd.to_datetime(df[date_col], errors="coerce")

        # 3. Handle Timezone
        if dt.dt.tz is None:
            # Ensure ns for naive before localizing
            dt = dt.astype("datetime64[ns]")
            dt = dt.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")

        # 4. Convert to UTC
        dt = dt.dt.tz_convert("UTC")

        # 5. Assign back
        df[date_col] = dt
        df["timestamp"] = dt
    elif isinstance(df.index, pd.DatetimeIndex):
        # Handle DatetimeIndex
        dt_idx = df.index

        if dt_idx.tz is None:
            dt_idx = cast(pd.DatetimeIndex, dt_idx.astype("datetime64[ns]"))
            dt_idx = dt_idx.tz_localize(
                tz, ambiguous="NaT", nonexistent="shift_forward"
            )

        dt_idx = dt_idx.tz_convert("UTC")
        df.index = dt_idx
        df["timestamp"] = dt_idx
    else:
        # Warn or ignore? For now silent, user might be processing non-time data?
        pass

    return df


_RATIO_PERCENT_METRICS = frozenset(
    {
        "annualized_return",
        "volatility",
        "kelly_criterion",
    }
)

_PERCENT_VALUE_METRICS = frozenset(
    {
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "loss_rate",
        "exposure_time_pct",
    }
)


def format_percentage(
    value: float,
    source: Literal["ratio", "pct_value"] = "ratio",
    precision: int = 2,
    width: Optional[int] = None,
) -> str:
    r"""
    Format a value as percentage with explicit source unit.

    :param value: Numeric value to format.
    :param source: "ratio" 表示 0.1 -> 10%，"pct_value" 表示 10 -> 10%。
    :param precision: Decimal places.
    :param width: Optional width for right alignment.
    :return: Formatted percentage text.
    """
    if source == "ratio":
        text = f"{float(value):.{precision}%}"
    else:
        text = f"{float(value):.{precision}f}%"
    if width is None:
        return text
    return f"{text:>{width}}"


def format_metric_value(
    metric_name: str,
    value: float,
    precision: int = 2,
    width: Optional[int] = None,
) -> str:
    r"""
    Format metric display text using AKQuant metric unit mapping.

    :param metric_name: Metric field name.
    :param value: Raw metric value.
    :param precision: Decimal places.
    :param width: Optional width for right alignment.
    :return: Formatted metric text.
    """
    name = str(metric_name)
    numeric = float(value)
    if name in _RATIO_PERCENT_METRICS:
        return format_percentage(
            numeric,
            source="ratio",
            precision=precision,
            width=width,
        )
    if name in _PERCENT_VALUE_METRICS:
        return format_percentage(
            numeric,
            source="pct_value",
            precision=precision,
            width=width,
        )
    text = f"{numeric:.{precision}f}"
    if width is None:
        return text
    return f"{text:>{width}}"
