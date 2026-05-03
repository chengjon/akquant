"""Backtest data loading helpers."""

from typing import Any, Dict, List, Optional, Union, cast

import pandas as pd

from ..feed_adapter import FeedSlice


def _index_to_local_trading_days(
    index: pd.DatetimeIndex, timezone: str
) -> pd.DatetimeIndex:
    local_index = index
    if local_index.tz is None:
        local_index = local_index.tz_localize("UTC")
    return cast(pd.DatetimeIndex, local_index.tz_convert(timezone))


def _is_data_feed_adapter(value: Any) -> bool:
    return hasattr(value, "load") and callable(getattr(value, "load"))


def _load_data_map_from_adapter(
    adapter: Any,
    symbols: List[str],
    start_time: Optional[Union[str, Any]],
    end_time: Optional[Union[str, Any]],
    timezone: Optional[str],
) -> Dict[str, pd.DataFrame]:
    request_start = pd.Timestamp(start_time) if start_time is not None else None
    request_end = pd.Timestamp(end_time) if end_time is not None else None
    requested_symbols = symbols or ["BENCHMARK"]
    data_map: Dict[str, pd.DataFrame] = {}

    for sym in requested_symbols:
        frame = adapter.load(
            FeedSlice(
                symbol=str(sym),
                start_time=request_start,
                end_time=request_end,
                timezone=timezone,
            )
        )
        if not isinstance(frame, pd.DataFrame):
            raise TypeError("DataFeedAdapter.load must return pandas.DataFrame")
        if frame.empty:
            continue

        if "symbol" in frame.columns:
            grouped = frame.groupby(frame["symbol"].astype(str), sort=False)
            for grouped_symbol, grouped_frame in grouped:
                data_map[str(grouped_symbol)] = grouped_frame.copy()
        else:
            normalized = frame.copy()
            normalized["symbol"] = str(sym)
            data_map[str(sym)] = normalized

    return data_map
