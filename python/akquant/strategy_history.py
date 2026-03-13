from typing import Any, Optional, cast

import numpy as np
import pandas as pd


def set_history_depth(strategy: Any, depth: int) -> None:
    """设置历史数据回溯长度."""
    strategy._history_depth = depth


def set_rolling_window(strategy: Any, train_window: int, step: int) -> None:
    """设置滚动训练窗口参数."""
    strategy._rolling_train_window = train_window
    strategy._rolling_step = step
    if strategy._history_depth < train_window:
        strategy._history_depth = train_window


def get_history(
    strategy: Any, count: int, symbol: Optional[str] = None, field: str = "close"
) -> np.ndarray:
    """获取历史数据 (类似 Zipline data.history)."""
    if strategy._history_depth == 0:
        raise RuntimeError(
            "History tracking is not enabled. Call set_history_depth() first."
        )

    if strategy.ctx is None:
        raise RuntimeError("Context not ready")

    symbol = strategy._resolve_symbol(symbol)

    arr = strategy.ctx.history(symbol, field.lower(), count)

    if arr is None:
        return cast(np.ndarray, np.full(count, np.nan))

    if len(arr) < count:
        padding = np.full(count - len(arr), np.nan)
        return cast(np.ndarray, np.concatenate((padding, arr)))

    return cast(np.ndarray, arr)


def get_history_df(
    strategy: Any, count: int, symbol: Optional[str] = None
) -> pd.DataFrame:
    """获取历史数据 DataFrame (Open, High, Low, Close, Volume)."""
    symbol = strategy._resolve_symbol(symbol)

    data = {
        "open": get_history(strategy, count, symbol, "open"),
        "high": get_history(strategy, count, symbol, "high"),
        "low": get_history(strategy, count, symbol, "low"),
        "close": get_history(strategy, count, symbol, "close"),
        "volume": get_history(strategy, count, symbol, "volume"),
    }
    return pd.DataFrame(data)


def get_rolling_data(
    strategy: Any, length: Optional[int] = None, symbol: Optional[str] = None
) -> tuple[pd.DataFrame, Optional[pd.Series]]:
    """获取滚动训练数据."""
    if length is None:
        length = strategy._rolling_train_window

    if length <= 0:
        raise ValueError("Invalid rolling window length")

    df = get_history_df(strategy, length, symbol)
    return df, None
