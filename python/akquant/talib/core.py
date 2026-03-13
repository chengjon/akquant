"""TA-Lib compatibility core helpers."""

from collections.abc import Sequence
from typing import Union, cast

import numpy as np
import pandas as pd

SeriesLike = Union[pd.Series, np.ndarray, Sequence[float]]


def to_series(values: SeriesLike, name: str | None = None) -> pd.Series:
    """Convert input into float64 pandas Series."""
    if isinstance(values, pd.Series):
        series = values.astype(float)
        if name:
            series = series.rename(name)
        return series
    array = np.asarray(values, dtype=float)
    return pd.Series(array, name=name, dtype=float)


def to_numpy(values: pd.Series | np.ndarray) -> np.ndarray:
    """Convert series/array to float64 numpy array."""
    if isinstance(values, np.ndarray):
        return values.astype(float, copy=False)
    return cast(np.ndarray, values.to_numpy(dtype=float, copy=False))


def finalize_output(
    values: pd.Series | np.ndarray,
    *,
    as_series: bool,
) -> pd.Series | np.ndarray:
    """Finalize output as pandas Series or numpy array."""
    if as_series:
        if isinstance(values, pd.Series):
            return values
        return pd.Series(values, dtype=float)
    return to_numpy(values)
