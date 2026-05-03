"""Moving averages and basic statistical indicators."""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd

from ..akquant import APO as RustAPO
from ..akquant import AVGDEV as RustAVGDEV
from ..akquant import EMA as RustEMA
from ..akquant import MAX as RustMAX
from ..akquant import MAXINDEX as RustMAXINDEX
from ..akquant import MIDPOINT as RustMIDPOINT
from ..akquant import MIN as RustMIN
from ..akquant import MININDEX as RustMININDEX
from ..akquant import MINMAX as RustMINMAX
from ..akquant import MINMAXINDEX as RustMINMAXINDEX
from ..akquant import PPO as RustPPO
from ..akquant import RANGE as RustRANGE
from ..akquant import RSI as RustRSI
from ..akquant import SMA as RustSMA
from ..akquant import SUM as RustSUM
from ..akquant import TRIMA as RustTRIMA
from ..akquant import WMA as RustWMA
from ._dispatch import (
    _ensure_period,
    _rolling_mean,
    _run_rust_single_pair_series,
    _run_rust_single_series,
)
from .backend import resolve_backend
from .core import SeriesLike, finalize_output, to_series


def RSI(
    close: SeriesLike,
    timeperiod: int = 14,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Relative Strength Index (RSI)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustRSI(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    delta = cast(pd.Series, close_series.diff())
    gain = cast(pd.Series, delta.where(delta > 0.0, 0.0))
    loss = cast(pd.Series, -delta.where(delta < 0.0, 0.0))
    avg_gain = cast(
        pd.Series,
        gain.ewm(alpha=1.0 / use_period, adjust=False, min_periods=use_period).mean(),
    )
    avg_loss = cast(
        pd.Series,
        loss.ewm(alpha=1.0 / use_period, adjust=False, min_periods=use_period).mean(),
    )
    rs = cast(pd.Series, avg_gain / avg_loss)
    out = cast(pd.Series, 100.0 - (100.0 / (1.0 + rs)))
    return finalize_output(out, as_series=as_series)


def SMA(
    close: SeriesLike,
    timeperiod: int = 30,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Calculate simple moving average (SMA)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustSMA(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = _rolling_mean(close_series, use_period)
    return finalize_output(out, as_series=as_series)


def EMA(
    close: SeriesLike,
    timeperiod: int = 30,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Exponential Moving Average (EMA)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustEMA(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(
        pd.Series,
        close_series.ewm(alpha=2.0 / (use_period + 1.0), adjust=False).mean(),
    )
    out.iloc[: use_period - 1] = np.nan
    return finalize_output(out, as_series=as_series)


def APO(
    close: SeriesLike,
    fastperiod: int = 12,
    slowperiod: int = 26,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Absolute Price Oscillator (APO)."""
    backend_key = resolve_backend(backend)
    fast_p = _ensure_period(fastperiod, "fastperiod")
    slow_p = _ensure_period(slowperiod, "slowperiod")
    if slow_p <= fast_p:
        raise ValueError("slowperiod must be > fastperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustAPO(fast_p, slow_p)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    fast_ema = cast(
        pd.Series,
        close_series.ewm(alpha=2.0 / (fast_p + 1.0), adjust=False).mean(),
    )
    slow_ema = cast(
        pd.Series,
        close_series.ewm(alpha=2.0 / (slow_p + 1.0), adjust=False).mean(),
    )
    out = cast(pd.Series, fast_ema - slow_ema)
    out.iloc[: slow_p - 1] = np.nan
    return finalize_output(out, as_series=as_series)


def PPO(
    close: SeriesLike,
    fastperiod: int = 12,
    slowperiod: int = 26,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Percentage Price Oscillator (PPO)."""
    backend_key = resolve_backend(backend)
    fast_p = _ensure_period(fastperiod, "fastperiod")
    slow_p = _ensure_period(slowperiod, "slowperiod")
    if slow_p <= fast_p:
        raise ValueError("slowperiod must be > fastperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustPPO(fast_p, slow_p)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    fast_ema = cast(
        pd.Series,
        close_series.ewm(alpha=2.0 / (fast_p + 1.0), adjust=False).mean(),
    )
    slow_ema = cast(
        pd.Series,
        close_series.ewm(alpha=2.0 / (slow_p + 1.0), adjust=False).mean(),
    )
    out = cast(pd.Series, 100.0 * (fast_ema - slow_ema) / slow_ema)
    out = cast(pd.Series, out.where(slow_ema.abs() > 1e-12, np.nan))
    out.iloc[: slow_p - 1] = np.nan
    return finalize_output(out, as_series=as_series)


def WMA(
    close: SeriesLike,
    timeperiod: int = 30,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Weighted Moving Average (WMA)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustWMA(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    weights = np.arange(1.0, use_period + 1.0, dtype=float)
    denom = float(weights.sum())
    out = cast(
        pd.Series,
        close_series.rolling(use_period).apply(
            lambda arr: float(np.dot(arr, weights) / denom),
            raw=True,
        ),
    )
    return finalize_output(out, as_series=as_series)


def TRIMA(
    close: SeriesLike,
    timeperiod: int = 30,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Triangular Moving Average (TRIMA)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustTRIMA(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    if use_period % 2 == 1:
        peak = use_period // 2 + 1
        weights = np.array(
            [i + 1 if i < peak else use_period - i for i in range(use_period)],
            dtype=float,
        )
    else:
        peak = use_period // 2
        weights = np.array(
            [i + 1 if i < peak else use_period - i for i in range(use_period)],
            dtype=float,
        )
    denom = float(weights.sum())
    out = cast(
        pd.Series,
        close_series.rolling(use_period).apply(
            lambda arr: float(np.dot(arr, weights) / denom),
            raw=True,
        ),
    )
    return finalize_output(out, as_series=as_series)


def MIDPOINT(
    close: SeriesLike,
    timeperiod: int = 14,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """MidPoint over rolling high/low of close."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustMIDPOINT(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    roll_max = cast(pd.Series, close_series.rolling(use_period).max())
    roll_min = cast(pd.Series, close_series.rolling(use_period).min())
    out = cast(pd.Series, (roll_max + roll_min) / 2.0)
    return finalize_output(out, as_series=as_series)


def MAX(
    close: SeriesLike,
    timeperiod: int = 30,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Highest value over rolling window (MAX)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustMAX(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, close_series.rolling(use_period).max())
    return finalize_output(out, as_series=as_series)


def MIN(
    close: SeriesLike,
    timeperiod: int = 30,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Lowest value over rolling window (MIN)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustMIN(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, close_series.rolling(use_period).min())
    return finalize_output(out, as_series=as_series)


def MAXINDEX(
    close: SeriesLike,
    timeperiod: int = 30,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Absolute index of rolling maximum (MAXINDEX)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustMAXINDEX(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    local = cast(
        pd.Series,
        close_series.rolling(use_period).apply(
            lambda arr: float(len(arr) - 1 - int(np.argmax(arr[::-1]))),
            raw=True,
        ),
    )
    base = pd.Series(
        np.arange(len(close_series), dtype=float),
        index=close_series.index,
    )
    out = cast(pd.Series, local + (base - (use_period - 1)))
    return finalize_output(out, as_series=as_series)


def MININDEX(
    close: SeriesLike,
    timeperiod: int = 30,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Absolute index of rolling minimum (MININDEX)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustMININDEX(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    local = cast(
        pd.Series,
        close_series.rolling(use_period).apply(
            lambda arr: float(len(arr) - 1 - int(np.argmin(arr[::-1]))),
            raw=True,
        ),
    )
    base = pd.Series(
        np.arange(len(close_series), dtype=float),
        index=close_series.index,
    )
    out = cast(pd.Series, local + (base - (use_period - 1)))
    return finalize_output(out, as_series=as_series)


def MINMAXINDEX(
    close: SeriesLike,
    timeperiod: int = 30,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> tuple[pd.Series | object, pd.Series | object]:
    """Return rolling minimum and maximum index pair (MINMAXINDEX)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustMINMAXINDEX(use_period)
        min_s, max_s = _run_rust_single_pair_series(close_series, indicator.update)
        return (
            finalize_output(min_s, as_series=as_series),
            finalize_output(max_s, as_series=as_series),
        )
    local_min = cast(
        pd.Series,
        close_series.rolling(use_period).apply(
            lambda arr: float(len(arr) - 1 - int(np.argmin(arr[::-1]))),
            raw=True,
        ),
    )
    local_max = cast(
        pd.Series,
        close_series.rolling(use_period).apply(
            lambda arr: float(len(arr) - 1 - int(np.argmax(arr[::-1]))),
            raw=True,
        ),
    )
    base = pd.Series(
        np.arange(len(close_series), dtype=float),
        index=close_series.index,
    )
    out_min = cast(pd.Series, local_min + (base - (use_period - 1)))
    out_max = cast(pd.Series, local_max + (base - (use_period - 1)))
    return (
        finalize_output(out_min, as_series=as_series),
        finalize_output(out_max, as_series=as_series),
    )


def MINMAX(
    close: SeriesLike,
    timeperiod: int = 30,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> tuple[pd.Series | object, pd.Series | object]:
    """Return rolling minimum and maximum pair (MINMAX)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustMINMAX(use_period)
        min_s, max_s = _run_rust_single_pair_series(close_series, indicator.update)
        return (
            finalize_output(min_s, as_series=as_series),
            finalize_output(max_s, as_series=as_series),
        )
    min_s = cast(pd.Series, close_series.rolling(use_period).min())
    max_s = cast(pd.Series, close_series.rolling(use_period).max())
    return (
        finalize_output(min_s, as_series=as_series),
        finalize_output(max_s, as_series=as_series),
    )


def SUM(
    close: SeriesLike,
    timeperiod: int = 30,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return rolling sum (SUM)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustSUM(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, close_series.rolling(use_period).sum())
    return finalize_output(out, as_series=as_series)


def AVGDEV(
    close: SeriesLike,
    timeperiod: int = 5,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return average absolute deviation (AVGDEV)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustAVGDEV(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)

    def _avgdev(window: np.ndarray) -> float:
        mean = float(window.mean())
        return float(np.mean(np.abs(window - mean)))

    out = cast(pd.Series, close_series.rolling(use_period).apply(_avgdev, raw=True))
    return finalize_output(out, as_series=as_series)


def RANGE(
    close: SeriesLike,
    timeperiod: int = 30,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return rolling high-low range (RANGE)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustRANGE(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    roll_max = cast(pd.Series, close_series.rolling(use_period).max())
    roll_min = cast(pd.Series, close_series.rolling(use_period).min())
    out = cast(pd.Series, roll_max - roll_min)
    return finalize_output(out, as_series=as_series)


