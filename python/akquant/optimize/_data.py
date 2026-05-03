"""数据准备、时间轴构建和标准化辅助函数."""

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from datetime import time as datetime_time
from typing import Any, Dict, Optional, Sequence, Union, cast

import numpy as np
import pandas as pd

OptimizationData = Union[pd.DataFrame, Dict[str, pd.DataFrame]]


def _normalize_backtest_symbol_kwargs(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(kwargs)
    has_symbol = "symbol" in normalized
    has_symbols = "symbols" in normalized
    if has_symbol and has_symbols:
        raise ValueError("pass only one of `symbol` or `symbols`")
    if has_symbol:
        normalized["symbols"] = normalized.pop("symbol")
    return normalized


def _normalize_symbol_values(symbols: Any) -> list[str]:
    """标准化 symbols 参数."""
    if symbols is None:
        return []
    if isinstance(symbols, str):
        normalized = [symbols]
    elif isinstance(symbols, (list, tuple, set)):
        normalized = [str(item) for item in symbols]
    else:
        raise TypeError("symbols must be a string, list, tuple, or set")

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in normalized:
        value = str(item).strip()
        if not value:
            raise ValueError("symbols cannot contain empty values")
        if value in seen:
            continue
        seen.add(value)
        cleaned.append(value)
    return cleaned


def _infer_symbols_from_data(data: Any) -> list[str]:
    """从优化输入数据中推断 symbols."""
    if isinstance(data, dict):
        return [str(symbol).strip() for symbol in data.keys() if str(symbol).strip()]
    if isinstance(data, pd.DataFrame) and "symbol" in data.columns:
        symbol_series = data["symbol"].dropna().astype(str).str.strip()
        return [symbol for symbol in symbol_series.unique().tolist() if symbol]
    return []


def _resolve_optimization_backtest_kwargs(
    data: Any,
    kwargs: Dict[str, Any],
) -> Dict[str, Any]:
    """解析优化入口的 symbols 参数并做数据一致性校验."""
    normalized = _normalize_backtest_symbol_kwargs(kwargs)
    requested_symbols = _normalize_symbol_values(normalized.get("symbols"))
    inferred_symbols = _infer_symbols_from_data(data)
    available_symbols = set(inferred_symbols)

    if not requested_symbols:
        if inferred_symbols:
            normalized["symbols"] = inferred_symbols
        return normalized

    if available_symbols:
        missing_symbols = [
            symbol for symbol in requested_symbols if symbol not in available_symbols
        ]
        if missing_symbols:
            raise ValueError(
                "Requested symbols are not available in optimization data: "
                f"{missing_symbols}"
            )

    normalized["symbols"] = requested_symbols
    return normalized


def _ensure_dataframe_time_index(df: pd.DataFrame) -> pd.DataFrame:
    """确保 DataFrame 使用 DatetimeIndex 并按时间排序."""
    prepared = df
    if not isinstance(prepared.index, pd.DatetimeIndex):
        for column in ["date", "timestamp", "datetime", "Date", "Timestamp"]:
            if column in prepared.columns:
                prepared = prepared.set_index(column)
                break
        prepared = prepared.copy()
        prepared.index = pd.to_datetime(prepared.index)
    elif not prepared.index.is_monotonic_increasing:
        prepared = prepared.copy()

    if not prepared.index.is_monotonic_increasing:
        prepared = prepared.sort_index()
    return cast(pd.DataFrame, prepared)


def _filter_optimization_data_by_symbols(
    data: OptimizationData,
    symbols: Sequence[str],
) -> OptimizationData:
    """按 symbols 过滤优化数据."""
    if not symbols:
        return data

    symbol_set = set(symbols)
    if isinstance(data, pd.DataFrame):
        if "symbol" not in data.columns:
            return data
        filtered = data[data["symbol"].astype(str).isin(symbol_set)]
        return cast(pd.DataFrame, filtered.copy())

    filtered_map: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        if symbol in data:
            filtered_map[symbol] = data[symbol]
    return filtered_map


def _prepare_optimization_data(data: OptimizationData) -> OptimizationData:
    """标准化优化数据的时间索引."""
    if isinstance(data, pd.DataFrame):
        return _ensure_dataframe_time_index(data)

    prepared: dict[str, pd.DataFrame] = {}
    for symbol, df in data.items():
        prepared[str(symbol)] = _ensure_dataframe_time_index(df)
    return prepared


def _build_optimization_timeline(data: OptimizationData) -> pd.DatetimeIndex:
    """提取优化切窗使用的统一时间轴."""
    if isinstance(data, pd.DataFrame):
        if not isinstance(data.index, pd.DatetimeIndex):
            raise TypeError(
                "Optimization data must use DatetimeIndex after preparation"
            )
        return cast(pd.DatetimeIndex, data.index.unique().sort_values())

    timeline = pd.DatetimeIndex([])
    for df in data.values():
        if df.empty:
            continue
        if not isinstance(df.index, pd.DatetimeIndex):
            raise TypeError(
                "Optimization data must use DatetimeIndex after preparation"
            )
        timeline = cast(pd.DatetimeIndex, timeline.union(df.index.unique()))
    return cast(pd.DatetimeIndex, timeline.sort_values())


def _slice_dataframe_by_time(
    df: pd.DataFrame,
    start_time: pd.Timestamp,
    end_time: Optional[pd.Timestamp],
) -> pd.DataFrame:
    """根据时间窗口切片 DataFrame."""
    mask = df.index >= start_time
    if end_time is not None:
        mask = mask & (df.index < end_time)
    return cast(pd.DataFrame, df.loc[mask].copy())


def _slice_optimization_data(
    data: OptimizationData,
    start_time: pd.Timestamp,
    end_time: Optional[pd.Timestamp],
) -> OptimizationData:
    """根据统一时间窗口切片优化数据."""
    if isinstance(data, pd.DataFrame):
        return _slice_dataframe_by_time(data, start_time, end_time)

    sliced: dict[str, pd.DataFrame] = {}
    for symbol, df in data.items():
        window_df = _slice_dataframe_by_time(df, start_time, end_time)
        if not window_df.empty:
            sliced[symbol] = window_df
    return sliced


@dataclass
class OptimizationResult:
    """
    单个优化结果.

    :param params: 参数组合
    :param metrics: 性能指标字典
    :param duration: 回测耗时 (秒)
    :param error: 错误信息 (可选)
    """

    params: Dict[str, Any]
    metrics: Dict[str, Any]
    duration: float = 0.0
    error: Optional[str] = None

    def __repr__(self) -> str:
        """Return string representation."""
        if self.error:
            return f"OptimizationResult(params={self.params}, error={self.error})"
        return f"OptimizationResult(params={self.params}, metrics={self.metrics})"


class JSONEncoder(json.JSONEncoder):
    """Custom JSON Encoder for numpy types."""

    def default(self, obj: Any) -> Any:
        """Encode object."""
        if obj is pd.NaT:
            return None
        if isinstance(obj, pd.Timestamp):
            if pd.isna(obj):
                return None
            return obj.isoformat()
        if isinstance(obj, pd.Timedelta):
            return obj.total_seconds()
        if isinstance(obj, (datetime, date, datetime_time)):
            return obj.isoformat()
        if isinstance(obj, timedelta):
            return obj.total_seconds()
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)
