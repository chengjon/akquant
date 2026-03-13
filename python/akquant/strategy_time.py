from typing import Any, Optional, cast

import pandas as pd


def to_local_time(strategy: Any, timestamp: int) -> pd.Timestamp:
    """将 UTC 纳秒时间戳转换为本地时间 (Timestamp)."""
    ts_utc = pd.to_datetime(timestamp, unit="ns", utc=True)
    return cast(pd.Timestamp, ts_utc.tz_convert(strategy.timezone))


def format_time(strategy: Any, timestamp: int, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """将 UTC 纳秒时间戳格式化为本地时间字符串."""
    return to_local_time(strategy, timestamp).strftime(fmt)


def now(strategy: Any) -> Optional[pd.Timestamp]:
    """获取当前回测时间的本地时间表示."""
    ts = None
    if strategy.current_bar:
        ts = strategy.current_bar.timestamp
    elif strategy.current_tick:
        ts = strategy.current_tick.timestamp

    if ts is not None:
        return to_local_time(strategy, ts)
    return None
