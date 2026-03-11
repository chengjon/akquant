"""TA-Lib style indicator functions."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import numpy as np
import pandas as pd

from ..akquant import ADX as RustADX
from ..akquant import ATR as RustATR
from ..akquant import CCI as RustCCI
from ..akquant import DEMA as RustDEMA
from ..akquant import EMA as RustEMA
from ..akquant import KAMA as RustKAMA
from ..akquant import MACD as RustMACD
from ..akquant import MFI as RustMFI
from ..akquant import MOM as RustMOM
from ..akquant import NATR as RustNATR
from ..akquant import OBV as RustOBV
from ..akquant import ROC as RustROC
from ..akquant import RSI as RustRSI
from ..akquant import SAR as RustSAR
from ..akquant import SMA as RustSMA
from ..akquant import STOCH as RustSTOCH
from ..akquant import TEMA as RustTEMA
from ..akquant import TRIX as RustTRIX
from ..akquant import WILLR as RustWILLR
from ..akquant import BollingerBands as RustBollingerBands
from .backend import resolve_backend
from .core import SeriesLike, finalize_output, to_series


def _ensure_period(value: int, name: str) -> int:
    """Validate integer period parameter."""
    period = int(value)
    if period <= 0:
        raise ValueError(f"{name} must be > 0")
    return period


def _rolling_mean(series: pd.Series, period: int) -> pd.Series:
    """Compute rolling mean with default pandas behavior."""
    return cast(pd.Series, series.rolling(period).mean())


def _run_rust_single_series(
    values: pd.Series,
    update_fn: Callable[[float], float | None],
) -> pd.Series:
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
    arr = np.full(len(high_values), np.nan, dtype=float)
    for idx, (high_v, low_v) in enumerate(zip(high_values, low_values)):
        out = update_fn(float(high_v), float(low_v))
        if out is not None:
            arr[idx] = float(out)
    return pd.Series(arr, index=high_values.index, dtype=float)


def ROC(
    close: SeriesLike,
    timeperiod: int = 10,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Rate of Change (ROC)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustROC(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, close_series.pct_change(use_period) * 100.0)
    return finalize_output(out, as_series=as_series)


def WILLR(
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    timeperiod: int = 14,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Williams %R."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustWILLR(use_period)
        out = _run_rust_hlc_series(
            high_series,
            low_series,
            close_series,
            indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    highest = cast(pd.Series, high_series.rolling(use_period).max())
    lowest = cast(pd.Series, low_series.rolling(use_period).min())
    denominator = highest - lowest
    out = cast(pd.Series, -100.0 * (highest - close_series) / denominator)
    return finalize_output(out, as_series=as_series)


def CCI(
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    timeperiod: int = 14,
    *,
    period: int | None = None,
    c: float = 0.015,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Commodity Channel Index (CCI)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    if c <= 0:
        raise ValueError("c must be > 0")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCCI(use_period, float(c))
        out = _run_rust_hlc_series(
            high_series,
            low_series,
            close_series,
            indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    typical_price = (high_series + low_series + close_series) / 3.0
    sma = _rolling_mean(typical_price, use_period)
    mean_deviation = cast(
        pd.Series,
        (typical_price - sma).abs().rolling(use_period).mean(),
    )
    out = cast(pd.Series, (typical_price - sma) / (c * mean_deviation))
    return finalize_output(out, as_series=as_series)


def ADX(
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    timeperiod: int = 14,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Average Directional Index (ADX)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustADX(use_period)
        out = _run_rust_hlc_series(
            high_series,
            low_series,
            close_series,
            indicator.update,
        )
        return finalize_output(out, as_series=as_series)

    up_move = cast(pd.Series, high_series.diff())
    down_move = cast(pd.Series, -low_series.diff())
    plus_dm = cast(
        pd.Series,
        up_move.where((up_move > down_move) & (up_move > 0.0), 0.0),
    )
    minus_dm = cast(
        pd.Series,
        down_move.where((down_move > up_move) & (down_move > 0.0), 0.0),
    )
    tr_components = pd.concat(
        [
            high_series - low_series,
            (high_series - close_series.shift(1)).abs(),
            (low_series - close_series.shift(1)).abs(),
        ],
        axis=1,
    )
    tr = cast(pd.Series, tr_components.max(axis=1))
    atr = cast(
        pd.Series,
        tr.ewm(alpha=1.0 / use_period, adjust=False, min_periods=use_period).mean(),
    )
    plus_di = cast(
        pd.Series,
        100.0
        * plus_dm.ewm(
            alpha=1.0 / use_period,
            adjust=False,
            min_periods=use_period,
        ).mean()
        / atr,
    )
    minus_di = cast(
        pd.Series,
        100.0
        * minus_dm.ewm(
            alpha=1.0 / use_period,
            adjust=False,
            min_periods=use_period,
        ).mean()
        / atr,
    )
    dx = cast(pd.Series, 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di))
    out = cast(
        pd.Series,
        dx.ewm(alpha=1.0 / use_period, adjust=False, min_periods=use_period).mean(),
    )
    return finalize_output(out, as_series=as_series)


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


def ATR(
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    timeperiod: int = 14,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Average True Range (ATR)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustATR(use_period)
        arr = np.full(len(close_series), np.nan, dtype=float)
        for idx, (high_v, low_v, close_v) in enumerate(
            zip(high_series, low_series, close_series)
        ):
            out_val = indicator.update(float(high_v), float(low_v), float(close_v))
            if out_val is not None:
                arr[idx] = float(out_val)
        out_series = pd.Series(arr, index=close_series.index, dtype=float)
        return finalize_output(out_series, as_series=as_series)
    tr_components = pd.concat(
        [
            high_series - low_series,
            (high_series - close_series.shift(1)).abs(),
            (low_series - close_series.shift(1)).abs(),
        ],
        axis=1,
    )
    tr = cast(pd.Series, tr_components.max(axis=1))
    atr_series = cast(
        pd.Series,
        tr.ewm(alpha=1.0 / use_period, adjust=False, min_periods=use_period).mean(),
    )
    return finalize_output(atr_series, as_series=as_series)


def MACD(
    close: SeriesLike,
    fastperiod: int = 12,
    slowperiod: int = 26,
    signalperiod: int = 9,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> tuple[pd.Series | object, pd.Series | object, pd.Series | object]:
    """Calculate moving average convergence divergence."""
    backend_key = resolve_backend(backend)
    fast_p = _ensure_period(fastperiod, "fastperiod")
    slow_p = _ensure_period(slowperiod, "slowperiod")
    signal_p = _ensure_period(signalperiod, "signalperiod")
    close_series = to_series(close, name="close")
    if slow_p <= fast_p:
        raise ValueError("slowperiod must be > fastperiod")
    if backend_key == "rust":
        indicator = RustMACD(fast_p, slow_p, signal_p)
        dif = np.full(len(close_series), np.nan, dtype=float)
        dea = np.full(len(close_series), np.nan, dtype=float)
        hist = np.full(len(close_series), np.nan, dtype=float)
        for idx, value in enumerate(close_series):
            out = indicator.update(float(value))
            if out is not None:
                dif[idx], dea[idx], hist[idx] = (
                    float(out[0]),
                    float(out[1]),
                    float(out[2]),
                )
        dif_s = pd.Series(dif, index=close_series.index, dtype=float)
        dea_s = pd.Series(dea, index=close_series.index, dtype=float)
        hist_s = pd.Series(hist, index=close_series.index, dtype=float)
        return (
            finalize_output(dif_s, as_series=as_series),
            finalize_output(dea_s, as_series=as_series),
            finalize_output(hist_s, as_series=as_series),
        )
    fast_ema = cast(
        pd.Series,
        close_series.ewm(alpha=2.0 / (fast_p + 1.0), adjust=False).mean(),
    )
    slow_ema = cast(
        pd.Series,
        close_series.ewm(alpha=2.0 / (slow_p + 1.0), adjust=False).mean(),
    )
    dif_s = cast(pd.Series, fast_ema - slow_ema)
    dea_s = cast(
        pd.Series,
        dif_s.ewm(alpha=2.0 / (signal_p + 1.0), adjust=False).mean(),
    )
    hist_s = cast(pd.Series, dif_s - dea_s)
    warmup = slow_p + signal_p - 2
    dif_s.iloc[:warmup] = np.nan
    dea_s.iloc[:warmup] = np.nan
    hist_s.iloc[:warmup] = np.nan
    return (
        finalize_output(dif_s, as_series=as_series),
        finalize_output(dea_s, as_series=as_series),
        finalize_output(hist_s, as_series=as_series),
    )


def BBANDS(
    close: SeriesLike,
    timeperiod: int = 5,
    nbdevup: float = 2.0,
    nbdevdn: float = 2.0,
    matype: int = 0,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> tuple[pd.Series | object, pd.Series | object, pd.Series | object]:
    """Bollinger Bands returning (upper, middle, lower)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    if matype != 0:
        raise ValueError("only matype=0 (SMA) is supported")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        if abs(nbdevup - nbdevdn) > 1e-12:
            raise ValueError("rust backend currently requires nbdevup == nbdevdn")
        indicator = RustBollingerBands(use_period, float(nbdevup))
        upper = np.full(len(close_series), np.nan, dtype=float)
        middle = np.full(len(close_series), np.nan, dtype=float)
        lower = np.full(len(close_series), np.nan, dtype=float)
        for idx, value in enumerate(close_series):
            out = indicator.update(float(value))
            if out is not None:
                upper[idx], middle[idx], lower[idx] = (
                    float(out[0]),
                    float(out[1]),
                    float(out[2]),
                )
        upper_s = pd.Series(upper, index=close_series.index, dtype=float)
        middle_s = pd.Series(middle, index=close_series.index, dtype=float)
        lower_s = pd.Series(lower, index=close_series.index, dtype=float)
        return (
            finalize_output(upper_s, as_series=as_series),
            finalize_output(middle_s, as_series=as_series),
            finalize_output(lower_s, as_series=as_series),
        )
    middle_s = _rolling_mean(close_series, use_period)
    std = cast(pd.Series, close_series.rolling(use_period).std(ddof=0))
    upper_s = cast(pd.Series, middle_s + float(nbdevup) * std)
    lower_s = cast(pd.Series, middle_s - float(nbdevdn) * std)
    return (
        finalize_output(upper_s, as_series=as_series),
        finalize_output(middle_s, as_series=as_series),
        finalize_output(lower_s, as_series=as_series),
    )


def STOCH(
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    fastk_period: int = 5,
    slowk_period: int = 3,
    slowk_matype: int = 0,
    slowd_period: int = 3,
    slowd_matype: int = 0,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> tuple[pd.Series | object, pd.Series | object]:
    """Stochastic oscillator returning (slowk, slowd)."""
    backend_key = resolve_backend(backend)
    if slowk_matype != 0 or slowd_matype != 0:
        raise ValueError("only matype=0 (SMA) is supported")
    k_period = _ensure_period(fastk_period, "fastk_period")
    k_smooth = _ensure_period(slowk_period, "slowk_period")
    d_period = _ensure_period(slowd_period, "slowd_period")

    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustSTOCH(k_period, k_smooth, d_period)
        slow_k, slow_d = _run_rust_hlc_pair_series(
            high_series,
            low_series,
            close_series,
            indicator.update,
        )
        return (
            finalize_output(slow_k, as_series=as_series),
            finalize_output(slow_d, as_series=as_series),
        )

    highest = cast(pd.Series, high_series.rolling(k_period).max())
    lowest = cast(pd.Series, low_series.rolling(k_period).min())
    fast_k = cast(pd.Series, 100.0 * (close_series - lowest) / (highest - lowest))
    slow_k = _rolling_mean(fast_k, k_smooth)
    slow_d = _rolling_mean(slow_k, d_period)
    return (
        finalize_output(slow_k, as_series=as_series),
        finalize_output(slow_d, as_series=as_series),
    )


def MOM(
    close: SeriesLike,
    timeperiod: int = 10,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Momentum (MOM)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustMOM(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, close_series.diff(use_period))
    return finalize_output(out, as_series=as_series)


def OBV(
    close: SeriesLike,
    volume: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """On Balance Volume (OBV)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    volume_series = to_series(volume, name="volume")
    if backend_key == "rust":
        indicator = RustOBV()
        out = _run_rust_dual_series(close_series, volume_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    direction = cast(
        pd.Series,
        pd.Series(
            np.sign(close_series.diff().to_numpy(dtype=float)),
            index=close_series.index,
            dtype=float,
        ).fillna(0.0),
    )
    out = cast(pd.Series, (direction * volume_series).cumsum())
    return finalize_output(out, as_series=as_series)


def DEMA(
    close: SeriesLike,
    timeperiod: int = 30,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Double Exponential Moving Average (DEMA)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustDEMA(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    ema1 = cast(
        pd.Series,
        close_series.ewm(alpha=2.0 / (use_period + 1.0), adjust=False).mean(),
    )
    ema2 = cast(
        pd.Series,
        ema1.ewm(alpha=2.0 / (use_period + 1.0), adjust=False).mean(),
    )
    out = cast(pd.Series, 2.0 * ema1 - ema2)
    warmup = 2 * use_period - 2
    out.iloc[:warmup] = np.nan
    return finalize_output(out, as_series=as_series)


def TRIX(
    close: SeriesLike,
    timeperiod: int = 30,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Triple Exponential Moving Average Rate of Change (TRIX)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustTRIX(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    ema1 = cast(
        pd.Series,
        close_series.ewm(alpha=2.0 / (use_period + 1.0), adjust=False).mean(),
    )
    ema2 = cast(
        pd.Series,
        ema1.ewm(alpha=2.0 / (use_period + 1.0), adjust=False).mean(),
    )
    ema3 = cast(
        pd.Series,
        ema2.ewm(alpha=2.0 / (use_period + 1.0), adjust=False).mean(),
    )
    out = cast(pd.Series, ema3.pct_change() * 100.0)
    warmup = 3 * use_period - 2
    out.iloc[:warmup] = np.nan
    return finalize_output(out, as_series=as_series)


def MFI(
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    volume: SeriesLike,
    timeperiod: int = 14,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Money Flow Index (MFI)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    volume_series = to_series(volume, name="volume")
    if backend_key == "rust":
        indicator = RustMFI(use_period)
        out = _run_rust_hlcv_series(
            high_series,
            low_series,
            close_series,
            volume_series,
            indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    typical = cast(pd.Series, (high_series + low_series + close_series) / 3.0)
    raw_flow = cast(pd.Series, typical * volume_series)
    delta = cast(pd.Series, typical.diff())
    pos_flow = cast(pd.Series, raw_flow.where(delta > 0.0, 0.0))
    neg_flow = cast(pd.Series, raw_flow.where(delta < 0.0, 0.0))
    pos_sum = cast(pd.Series, pos_flow.rolling(use_period).sum())
    neg_sum = cast(pd.Series, neg_flow.rolling(use_period).sum())
    ratio = cast(pd.Series, pos_sum / neg_sum)
    out = cast(pd.Series, 100.0 - (100.0 / (1.0 + ratio)))
    out = cast(pd.Series, out.where(neg_sum > 0.0, 100.0))
    out = cast(pd.Series, out.where((neg_sum > 0.0) | (pos_sum > 0.0), 50.0))
    return finalize_output(out, as_series=as_series)


def TEMA(
    close: SeriesLike,
    timeperiod: int = 30,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Triple Exponential Moving Average (TEMA)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustTEMA(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    ema1 = cast(
        pd.Series,
        close_series.ewm(alpha=2.0 / (use_period + 1.0), adjust=False).mean(),
    )
    ema2 = cast(
        pd.Series,
        ema1.ewm(alpha=2.0 / (use_period + 1.0), adjust=False).mean(),
    )
    ema3 = cast(
        pd.Series,
        ema2.ewm(alpha=2.0 / (use_period + 1.0), adjust=False).mean(),
    )
    out = cast(pd.Series, 3.0 * ema1 - 3.0 * ema2 + ema3)
    warmup = 3 * use_period - 2
    out.iloc[:warmup] = np.nan
    return finalize_output(out, as_series=as_series)


def KAMA(
    close: SeriesLike,
    timeperiod: int = 30,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Kaufman Adaptive Moving Average (KAMA)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustKAMA(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    fast_sc = 2.0 / 3.0
    slow_sc = 2.0 / 31.0
    out = pd.Series(np.nan, index=close_series.index, dtype=float)
    if len(close_series) <= use_period:
        return finalize_output(out, as_series=as_series)
    for idx in range(use_period, len(close_series)):
        window = close_series.iloc[idx - use_period : idx + 1]
        change = abs(float(window.iloc[-1] - window.iloc[0]))
        volatility = float(window.diff().abs().sum())
        er = 0.0 if volatility <= 1e-12 else change / volatility
        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
        prev = float(window.iloc[-1]) if idx == use_period else float(out.iloc[idx - 1])
        out.iloc[idx] = prev + sc * (float(close_series.iloc[idx]) - prev)
    return finalize_output(cast(pd.Series, out), as_series=as_series)


def NATR(
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    timeperiod: int = 14,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Calculate normalized average true range (NATR)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustNATR(use_period)
        out = _run_rust_hlc_series(
            high_series,
            low_series,
            close_series,
            indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    tr_components = pd.concat(
        [
            high_series - low_series,
            (high_series - close_series.shift(1)).abs(),
            (low_series - close_series.shift(1)).abs(),
        ],
        axis=1,
    )
    tr = cast(pd.Series, tr_components.max(axis=1))
    atr = cast(
        pd.Series,
        tr.ewm(alpha=1.0 / use_period, adjust=False, min_periods=use_period).mean(),
    )
    out = cast(pd.Series, 100.0 * atr / close_series)
    return finalize_output(out, as_series=as_series)


def SAR(
    high: SeriesLike,
    low: SeriesLike,
    acceleration: float = 0.02,
    maximum: float = 0.2,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Parabolic SAR."""
    if acceleration <= 0.0 or maximum <= 0.0:
        raise ValueError("acceleration and maximum must be > 0")
    if acceleration > maximum:
        raise ValueError("acceleration must be <= maximum")
    backend_key = resolve_backend(backend)
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    if backend_key == "rust":
        indicator = RustSAR(float(acceleration), float(maximum))
        out = _run_rust_hl_series(high_series, low_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = pd.Series(np.nan, index=high_series.index, dtype=float)
    if len(high_series) < 2:
        return finalize_output(out, as_series=as_series)
    trend_up = float(high_series.iloc[1]) >= float(high_series.iloc[0])
    af = float(acceleration)
    ep = (
        max(float(high_series.iloc[0]), float(high_series.iloc[1]))
        if trend_up
        else min(float(low_series.iloc[0]), float(low_series.iloc[1]))
    )
    sar = (
        min(float(low_series.iloc[0]), float(low_series.iloc[1]))
        if trend_up
        else max(float(high_series.iloc[0]), float(high_series.iloc[1]))
    )
    out.iloc[1] = sar
    for idx in range(2, len(high_series)):
        high_v = float(high_series.iloc[idx])
        low_v = float(low_series.iloc[idx])
        prev_high = float(high_series.iloc[idx - 1])
        prev_low = float(low_series.iloc[idx - 1])
        sar_next = sar + af * (ep - sar)
        if trend_up:
            sar_next = min(sar_next, prev_low, low_v)
            if low_v < sar_next:
                trend_up = False
                sar_next = ep
                ep = low_v
                af = float(acceleration)
            elif high_v > ep:
                ep = high_v
                af = min(af + float(acceleration), float(maximum))
        else:
            sar_next = max(sar_next, prev_high, high_v)
            if high_v > sar_next:
                trend_up = True
                sar_next = ep
                ep = high_v
                af = float(acceleration)
            elif low_v < ep:
                ep = low_v
                af = min(af + float(acceleration), float(maximum))
        sar = sar_next
        out.iloc[idx] = sar
    return finalize_output(cast(pd.Series, out), as_series=as_series)
