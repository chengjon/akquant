"""Internal dispatch helpers for Rust indicator backends."""

from collections.abc import Callable
from typing import cast

import numpy as np
import pandas as pd


def _ensure_period(value: int, name: str) -> int:
    """Validate integer period parameter."""
    period = int(value)
    if period <= 0:
        raise ValueError(f"{name} must be > 0")
    return period


def _rolling_mean(series: pd.Series, period: int) -> pd.Series:
    """Compute rolling mean with default pandas behavior."""
    return cast(pd.Series, series.rolling(period).mean())


def _batch_call(
    update_fn: Callable[..., object], method_name: str, *arrays: np.ndarray
) -> object | None:
    owner = getattr(update_fn, "__self__", None)
    if owner is None:
        return None
    method = getattr(owner, method_name, None)
    if method is None or not callable(method):
        return None
    return cast(object, method(*arrays))


def _run_rust_single_series(
    values: pd.Series,
    update_fn: Callable[[float], float | None],
) -> pd.Series:
    values_arr = values.to_numpy(dtype=float, copy=False)
    batch_out = _batch_call(update_fn, "update_many", values_arr)
    if batch_out is not None:
        arr = np.asarray(batch_out, dtype=float)
        if arr.shape[0] == values_arr.shape[0]:
            return pd.Series(arr, index=values.index, dtype=float)
    arr = np.full(len(values), np.nan, dtype=float)
    for idx, value in enumerate(values):
        out = update_fn(float(value))
        if out is not None:
            arr[idx] = float(out)
    return pd.Series(arr, index=values.index, dtype=float)


def _run_rust_hlc_series(
    high_values: pd.Series,
    low_values: pd.Series,
    close_values: pd.Series,
    update_fn: Callable[[float, float, float], float | None],
) -> pd.Series:
    highs_arr = high_values.to_numpy(dtype=float, copy=False)
    lows_arr = low_values.to_numpy(dtype=float, copy=False)
    closes_arr = close_values.to_numpy(dtype=float, copy=False)
    batch_out = _batch_call(
        update_fn, "update_many_hlc", highs_arr, lows_arr, closes_arr
    )
    if batch_out is not None:
        arr = np.asarray(batch_out, dtype=float)
        if arr.shape[0] == closes_arr.shape[0]:
            return pd.Series(arr, index=close_values.index, dtype=float)
    arr = np.full(len(close_values), np.nan, dtype=float)
    for idx, (high_v, low_v, close_v) in enumerate(
        zip(high_values, low_values, close_values)
    ):
        out = update_fn(float(high_v), float(low_v), float(close_v))
        if out is not None:
            arr[idx] = float(out)
    return pd.Series(arr, index=close_values.index, dtype=float)


def _run_rust_hlc_pair_series(
    high_values: pd.Series,
    low_values: pd.Series,
    close_values: pd.Series,
    update_fn: Callable[[float, float, float], tuple[float, float] | None],
) -> tuple[pd.Series, pd.Series]:
    highs_arr = high_values.to_numpy(dtype=float, copy=False)
    lows_arr = low_values.to_numpy(dtype=float, copy=False)
    closes_arr = close_values.to_numpy(dtype=float, copy=False)
    batch_out = _batch_call(
        update_fn, "update_many_hlc_pair", highs_arr, lows_arr, closes_arr
    )
    if isinstance(batch_out, (tuple, list)) and len(batch_out) == 2:
        first_arr = np.asarray(batch_out[0], dtype=float)
        second_arr = np.asarray(batch_out[1], dtype=float)
        if (
            first_arr.shape[0] == closes_arr.shape[0]
            and second_arr.shape[0] == closes_arr.shape[0]
        ):
            return (
                pd.Series(first_arr, index=close_values.index, dtype=float),
                pd.Series(second_arr, index=close_values.index, dtype=float),
            )
    first = np.full(len(close_values), np.nan, dtype=float)
    second = np.full(len(close_values), np.nan, dtype=float)
    for idx, (high_v, low_v, close_v) in enumerate(
        zip(high_values, low_values, close_values)
    ):
        out = update_fn(float(high_v), float(low_v), float(close_v))
        if out is not None:
            first[idx], second[idx] = float(out[0]), float(out[1])
    return (
        pd.Series(first, index=close_values.index, dtype=float),
        pd.Series(second, index=close_values.index, dtype=float),
    )


def _run_rust_dual_series(
    first_values: pd.Series,
    second_values: pd.Series,
    update_fn: Callable[[float, float], float | None],
) -> pd.Series:
    first_arr = first_values.to_numpy(dtype=float, copy=False)
    second_arr = second_values.to_numpy(dtype=float, copy=False)
    batch_out = _batch_call(update_fn, "update_many_dual", first_arr, second_arr)
    if batch_out is not None:
        arr = np.asarray(batch_out, dtype=float)
        if arr.shape[0] == first_arr.shape[0]:
            return pd.Series(arr, index=first_values.index, dtype=float)
    arr = np.full(len(first_values), np.nan, dtype=float)
    for idx, (first_v, second_v) in enumerate(zip(first_values, second_values)):
        out = update_fn(float(first_v), float(second_v))
        if out is not None:
            arr[idx] = float(out)
    return pd.Series(arr, index=first_values.index, dtype=float)


def _run_rust_hlcv_series(
    high_values: pd.Series,
    low_values: pd.Series,
    close_values: pd.Series,
    volume_values: pd.Series,
    update_fn: Callable[[float, float, float, float], float | None],
) -> pd.Series:
    highs_arr = high_values.to_numpy(dtype=float, copy=False)
    lows_arr = low_values.to_numpy(dtype=float, copy=False)
    closes_arr = close_values.to_numpy(dtype=float, copy=False)
    volumes_arr = volume_values.to_numpy(dtype=float, copy=False)
    batch_out = _batch_call(
        update_fn, "update_many_hlcv", highs_arr, lows_arr, closes_arr, volumes_arr
    )
    if batch_out is not None:
        arr = np.asarray(batch_out, dtype=float)
        if arr.shape[0] == closes_arr.shape[0]:
            return pd.Series(arr, index=close_values.index, dtype=float)
    arr = np.full(len(close_values), np.nan, dtype=float)
    for idx, (high_v, low_v, close_v, volume_v) in enumerate(
        zip(high_values, low_values, close_values, volume_values)
    ):
        out = update_fn(float(high_v), float(low_v), float(close_v), float(volume_v))
        if out is not None:
            arr[idx] = float(out)
    return pd.Series(arr, index=close_values.index, dtype=float)


def _run_rust_hl_series(
    high_values: pd.Series,
    low_values: pd.Series,
    update_fn: Callable[[float, float], float | None],
) -> pd.Series:
    highs_arr = high_values.to_numpy(dtype=float, copy=False)
    lows_arr = low_values.to_numpy(dtype=float, copy=False)
    batch_out = _batch_call(update_fn, "update_many_hl", highs_arr, lows_arr)
    if batch_out is not None:
        arr = np.asarray(batch_out, dtype=float)
        if arr.shape[0] == highs_arr.shape[0]:
            return pd.Series(arr, index=high_values.index, dtype=float)
    arr = np.full(len(high_values), np.nan, dtype=float)
    for idx, (high_v, low_v) in enumerate(zip(high_values, low_values)):
        out = update_fn(float(high_v), float(low_v))
        if out is not None:
            arr[idx] = float(out)
    return pd.Series(arr, index=high_values.index, dtype=float)


def _run_rust_hl_pair_series(
    high_values: pd.Series,
    low_values: pd.Series,
    update_fn: Callable[[float, float], tuple[float, float] | None],
) -> tuple[pd.Series, pd.Series]:
    highs_arr = high_values.to_numpy(dtype=float, copy=False)
    lows_arr = low_values.to_numpy(dtype=float, copy=False)
    batch_out = _batch_call(update_fn, "update_many_hl_pair", highs_arr, lows_arr)
    if isinstance(batch_out, (tuple, list)) and len(batch_out) == 2:
        first_arr = np.asarray(batch_out[0], dtype=float)
        second_arr = np.asarray(batch_out[1], dtype=float)
        if (
            first_arr.shape[0] == highs_arr.shape[0]
            and second_arr.shape[0] == highs_arr.shape[0]
        ):
            return (
                pd.Series(first_arr, index=high_values.index, dtype=float),
                pd.Series(second_arr, index=high_values.index, dtype=float),
            )
    first = np.full(len(high_values), np.nan, dtype=float)
    second = np.full(len(high_values), np.nan, dtype=float)
    for idx, (high_v, low_v) in enumerate(zip(high_values, low_values)):
        out = update_fn(float(high_v), float(low_v))
        if out is not None:
            first[idx], second[idx] = float(out[0]), float(out[1])
    return (
        pd.Series(first, index=high_values.index, dtype=float),
        pd.Series(second, index=high_values.index, dtype=float),
    )


def _run_rust_ohlc_series(
    open_values: pd.Series,
    high_values: pd.Series,
    low_values: pd.Series,
    close_values: pd.Series,
    update_fn: Callable[[float, float, float, float], float | None],
) -> pd.Series:
    opens_arr = open_values.to_numpy(dtype=float, copy=False)
    highs_arr = high_values.to_numpy(dtype=float, copy=False)
    lows_arr = low_values.to_numpy(dtype=float, copy=False)
    closes_arr = close_values.to_numpy(dtype=float, copy=False)
    batch_out = _batch_call(
        update_fn, "update_many_ohlc", opens_arr, highs_arr, lows_arr, closes_arr
    )
    if batch_out is not None:
        arr = np.asarray(batch_out, dtype=float)
        if arr.shape[0] == closes_arr.shape[0]:
            return pd.Series(arr, index=close_values.index, dtype=float)
    arr = np.full(len(close_values), np.nan, dtype=float)
    for idx, (open_v, high_v, low_v, close_v) in enumerate(
        zip(open_values, high_values, low_values, close_values)
    ):
        out = update_fn(float(open_v), float(high_v), float(low_v), float(close_v))
        if out is not None:
            arr[idx] = float(out)
    return pd.Series(arr, index=close_values.index, dtype=float)


def _run_rust_single_pair_series(
    values: pd.Series,
    update_fn: Callable[[float], tuple[float, float] | None],
) -> tuple[pd.Series, pd.Series]:
    values_arr = values.to_numpy(dtype=float, copy=False)
    batch_out = _batch_call(update_fn, "update_many_pair", values_arr)
    if isinstance(batch_out, (tuple, list)) and len(batch_out) == 2:
        first_arr = np.asarray(batch_out[0], dtype=float)
        second_arr = np.asarray(batch_out[1], dtype=float)
        if (
            first_arr.shape[0] == values_arr.shape[0]
            and second_arr.shape[0] == values_arr.shape[0]
        ):
            return (
                pd.Series(first_arr, index=values.index, dtype=float),
                pd.Series(second_arr, index=values.index, dtype=float),
            )
    first = np.full(len(values), np.nan, dtype=float)
    second = np.full(len(values), np.nan, dtype=float)
    for idx, value in enumerate(values):
        out = update_fn(float(value))
        if out is not None:
            first[idx], second[idx] = float(out[0]), float(out[1])
    return (
        pd.Series(first, index=values.index, dtype=float),
        pd.Series(second, index=values.index, dtype=float),
    )
