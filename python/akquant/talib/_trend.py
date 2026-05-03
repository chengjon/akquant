"""Trend, direction, and regression indicators."""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd

from ..akquant import ADX as RustADX
from ..akquant import ADXR as RustADXR
from ..akquant import AROON as RustAROON
from ..akquant import AROONOSC as RustAROONOSC
from ..akquant import BETA as RustBETA
from ..akquant import CCI as RustCCI
from ..akquant import CORREL as RustCORREL
from ..akquant import COVAR as RustCOVAR
from ..akquant import DX as RustDX
from ..akquant import LINEARREG as RustLINEARREG
from ..akquant import LINEARREG_ANGLE as RustLINEARREG_ANGLE
from ..akquant import LINEARREG_INTERCEPT as RustLINEARREG_INTERCEPT
from ..akquant import LINEARREG_R2 as RustLINEARREG_R2
from ..akquant import LINEARREG_SLOPE as RustLINEARREG_SLOPE
from ..akquant import MINUS_DI as RustMINUS_DI
from ..akquant import PLUS_DI as RustPLUS_DI
from ..akquant import ROC as RustROC
from ..akquant import ROCP as RustROCP
from ..akquant import ROCR as RustROCR
from ..akquant import ROCR100 as RustROCR100
from ..akquant import TSF as RustTSF
from ..akquant import ULTOSC as RustULTOSC
from ..akquant import WILLR as RustWILLR
from ._dispatch import (
    _ensure_period,
    _rolling_mean,
    _run_rust_dual_series,
    _run_rust_hl_pair_series,
    _run_rust_hl_series,
    _run_rust_hlc_series,
    _run_rust_single_series,
)
from .backend import resolve_backend
from .core import SeriesLike, finalize_output, to_series


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


def ROCP(
    close: SeriesLike,
    timeperiod: int = 10,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Rate of change percentage (ROCP)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustROCP(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, close_series.pct_change(use_period))
    return finalize_output(out, as_series=as_series)


def ROCR(
    close: SeriesLike,
    timeperiod: int = 10,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Rate of change ratio (ROCR)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustROCR(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    shifted = cast(pd.Series, close_series.shift(use_period))
    out = cast(pd.Series, close_series / shifted)
    out = cast(pd.Series, out.where(shifted.abs() > 1e-12, np.nan))
    return finalize_output(out, as_series=as_series)


def ROCR100(
    close: SeriesLike,
    timeperiod: int = 10,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Rate of change ratio scaled by 100 (ROCR100)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustROCR100(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    shifted = cast(pd.Series, close_series.shift(use_period))
    out = cast(pd.Series, (close_series / shifted) * 100.0)
    out = cast(pd.Series, out.where(shifted.abs() > 1e-12, np.nan))
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


def DX(
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    timeperiod: int = 14,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Directional Movement Index (DX)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustDX(use_period)
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
    out = cast(pd.Series, 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di))
    return finalize_output(out, as_series=as_series)


def PLUS_DI(
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    timeperiod: int = 14,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Plus Directional Indicator (+DI)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustPLUS_DI(use_period)
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
    out = cast(
        pd.Series,
        100.0
        * plus_dm.ewm(
            alpha=1.0 / use_period,
            adjust=False,
            min_periods=use_period,
        ).mean()
        / atr,
    )
    return finalize_output(out, as_series=as_series)


def MINUS_DI(
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    timeperiod: int = 14,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Minus Directional Indicator (-DI)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustMINUS_DI(use_period)
        out = _run_rust_hlc_series(
            high_series,
            low_series,
            close_series,
            indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    up_move = cast(pd.Series, high_series.diff())
    down_move = cast(pd.Series, -low_series.diff())
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
    out = cast(
        pd.Series,
        100.0
        * minus_dm.ewm(
            alpha=1.0 / use_period,
            adjust=False,
            min_periods=use_period,
        ).mean()
        / atr,
    )
    return finalize_output(out, as_series=as_series)


def ULTOSC(
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    timeperiod1: int = 7,
    timeperiod2: int = 14,
    timeperiod3: int = 28,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Ultimate Oscillator (ULTOSC)."""
    backend_key = resolve_backend(backend)
    p1 = _ensure_period(timeperiod1, "timeperiod1")
    p2 = _ensure_period(timeperiod2, "timeperiod2")
    p3 = _ensure_period(timeperiod3, "timeperiod3")
    if not (p1 < p2 < p3):
        raise ValueError("require timeperiod1 < timeperiod2 < timeperiod3")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustULTOSC(p1, p2, p3)
        out = _run_rust_hlc_series(
            high_series,
            low_series,
            close_series,
            indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    prev_close = cast(pd.Series, close_series.shift(1))
    low_or_prev = cast(
        pd.Series,
        pd.concat([low_series, prev_close], axis=1).min(axis=1),
    )
    high_or_prev = cast(
        pd.Series,
        pd.concat([high_series, prev_close], axis=1).max(axis=1),
    )
    bp = cast(pd.Series, close_series - low_or_prev)
    tr = cast(pd.Series, high_or_prev - low_or_prev)
    bp1 = cast(pd.Series, bp.rolling(p1).sum())
    tr1 = cast(pd.Series, tr.rolling(p1).sum())
    bp2 = cast(pd.Series, bp.rolling(p2).sum())
    tr2 = cast(pd.Series, tr.rolling(p2).sum())
    bp3 = cast(pd.Series, bp.rolling(p3).sum())
    tr3 = cast(pd.Series, tr.rolling(p3).sum())
    avg1 = cast(pd.Series, bp1 / tr1)
    avg2 = cast(pd.Series, bp2 / tr2)
    avg3 = cast(pd.Series, bp3 / tr3)
    out = cast(pd.Series, 100.0 * (4.0 * avg1 + 2.0 * avg2 + avg3) / 7.0)
    out = cast(
        pd.Series,
        out.where((tr1 > 1e-12) & (tr2 > 1e-12) & (tr3 > 1e-12), np.nan),
    )
    return finalize_output(out, as_series=as_series)


def AROON(
    high: SeriesLike,
    low: SeriesLike,
    timeperiod: int = 14,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> tuple[pd.Series | object, pd.Series | object]:
    """Aroon oscillator components returning (aroondown, aroonup)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    if backend_key == "rust":
        indicator = RustAROON(use_period)
        down_s, up_s = _run_rust_hl_pair_series(
            high_series,
            low_series,
            indicator.update,
        )
        return (
            finalize_output(down_s, as_series=as_series),
            finalize_output(up_s, as_series=as_series),
        )

    def _down(window: np.ndarray) -> float:
        low_idx = int(np.argmin(window))
        days_since_low = use_period - 1 - low_idx
        return 100.0 * (use_period - days_since_low) / use_period

    def _up(window: np.ndarray) -> float:
        high_idx = int(np.argmax(window))
        days_since_high = use_period - 1 - high_idx
        return 100.0 * (use_period - days_since_high) / use_period

    down_s = cast(
        pd.Series,
        low_series.rolling(use_period).apply(_down, raw=True),
    )
    up_s = cast(
        pd.Series,
        high_series.rolling(use_period).apply(_up, raw=True),
    )
    return (
        finalize_output(down_s, as_series=as_series),
        finalize_output(up_s, as_series=as_series),
    )


def AROONOSC(
    high: SeriesLike,
    low: SeriesLike,
    timeperiod: int = 14,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Aroon oscillator (aroonup - aroondown)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    if backend_key == "rust":
        indicator = RustAROONOSC(use_period)
        out = _run_rust_hl_series(high_series, low_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    aroon_down, aroon_up = cast(
        tuple[pd.Series, pd.Series],
        AROON(
            high_series,
            low_series,
            timeperiod=use_period,
            as_series=True,
            backend="python",
        ),
    )
    out = cast(pd.Series, aroon_up - aroon_down)
    return finalize_output(out, as_series=as_series)


def LINEARREG(
    close: SeriesLike,
    timeperiod: int = 14,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Linear Regression endpoint value."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustLINEARREG(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    n = float(use_period)
    sum_x = n * (n - 1.0) / 2.0
    sum_x2 = n * (n - 1.0) * (2.0 * n - 1.0) / 6.0
    denom = n * sum_x2 - sum_x * sum_x

    def _linreg(window: np.ndarray) -> float:
        sum_y = float(window.sum())
        sum_xy = float(np.dot(np.arange(use_period, dtype=float), window))
        if abs(denom) <= 1e-12:
            return float("nan")
        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n
        return float(intercept + slope * (n - 1.0))

    out = cast(pd.Series, close_series.rolling(use_period).apply(_linreg, raw=True))
    return finalize_output(out, as_series=as_series)


def LINEARREG_SLOPE(
    close: SeriesLike,
    timeperiod: int = 14,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Linear Regression slope."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustLINEARREG_SLOPE(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    n = float(use_period)
    sum_x = n * (n - 1.0) / 2.0
    sum_x2 = n * (n - 1.0) * (2.0 * n - 1.0) / 6.0
    denom = n * sum_x2 - sum_x * sum_x

    def _slope(window: np.ndarray) -> float:
        sum_y = float(window.sum())
        sum_xy = float(np.dot(np.arange(use_period, dtype=float), window))
        if abs(denom) <= 1e-12:
            return float("nan")
        return float((n * sum_xy - sum_x * sum_y) / denom)

    out = cast(pd.Series, close_series.rolling(use_period).apply(_slope, raw=True))
    return finalize_output(out, as_series=as_series)


def LINEARREG_R2(
    close: SeriesLike,
    timeperiod: int = 14,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Linear Regression R-squared."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustLINEARREG_R2(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    x = pd.Series(np.arange(len(close_series), dtype=float), index=close_series.index)
    out = cast(pd.Series, close_series.rolling(use_period).corr(x) ** 2)
    return finalize_output(out, as_series=as_series)


def LINEARREG_INTERCEPT(
    close: SeriesLike,
    timeperiod: int = 14,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Linear Regression intercept."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustLINEARREG_INTERCEPT(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    n = float(use_period)
    sum_x = n * (n - 1.0) / 2.0
    sum_x2 = n * (n - 1.0) * (2.0 * n - 1.0) / 6.0
    denom = n * sum_x2 - sum_x * sum_x

    def _intercept(window: np.ndarray) -> float:
        sum_y = float(window.sum())
        sum_xy = float(np.dot(np.arange(use_period, dtype=float), window))
        if abs(denom) <= 1e-12:
            return float("nan")
        slope = (n * sum_xy - sum_x * sum_y) / denom
        return float((sum_y - slope * sum_x) / n)

    out = cast(
        pd.Series,
        close_series.rolling(use_period).apply(_intercept, raw=True),
    )
    return finalize_output(out, as_series=as_series)


def LINEARREG_ANGLE(
    close: SeriesLike,
    timeperiod: int = 14,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Linear Regression angle in degrees."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustLINEARREG_ANGLE(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    slope = cast(
        pd.Series,
        LINEARREG_SLOPE(
            close_series,
            timeperiod=use_period,
            as_series=True,
            backend="python",
        ),
    )
    out = cast(pd.Series, np.degrees(np.arctan(slope)))
    return finalize_output(out, as_series=as_series)


def TSF(
    close: SeriesLike,
    timeperiod: int = 14,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Time Series Forecast (TSF)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustTSF(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    n = float(use_period)
    sum_x = n * (n - 1.0) / 2.0
    sum_x2 = n * (n - 1.0) * (2.0 * n - 1.0) / 6.0
    denom = n * sum_x2 - sum_x * sum_x

    def _tsf(window: np.ndarray) -> float:
        sum_y = float(window.sum())
        sum_xy = float(np.dot(np.arange(use_period, dtype=float), window))
        if abs(denom) <= 1e-12:
            return float("nan")
        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n
        return float(intercept + slope * n)

    out = cast(pd.Series, close_series.rolling(use_period).apply(_tsf, raw=True))
    return finalize_output(out, as_series=as_series)


def CORREL(
    real0: SeriesLike,
    real1: SeriesLike,
    timeperiod: int = 30,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Pearson correlation coefficient (CORREL)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    series0 = to_series(real0, name="real0")
    series1 = to_series(real1, name="real1")
    if backend_key == "rust":
        indicator = RustCORREL(use_period)
        out = _run_rust_dual_series(series0, series1, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, series0.rolling(use_period).corr(series1))
    return finalize_output(out, as_series=as_series)


def BETA(
    real0: SeriesLike,
    real1: SeriesLike,
    timeperiod: int = 5,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Beta coefficient of real0 relative to real1."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    series0 = to_series(real0, name="real0")
    series1 = to_series(real1, name="real1")
    if backend_key == "rust":
        indicator = RustBETA(use_period)
        out = _run_rust_dual_series(series0, series1, indicator.update)
        return finalize_output(out, as_series=as_series)
    mean0 = cast(pd.Series, series0.rolling(use_period).mean())
    mean1 = cast(pd.Series, series1.rolling(use_period).mean())
    cov = cast(
        pd.Series,
        (series0 * series1).rolling(use_period).mean() - mean0 * mean1,
    )
    var1 = cast(
        pd.Series,
        (series1 * series1).rolling(use_period).mean() - mean1 * mean1,
    )
    out = cast(pd.Series, cov / var1)
    out = cast(pd.Series, out.where(var1.abs() > 1e-12, np.nan))
    return finalize_output(out, as_series=as_series)


def COVAR(
    real0: SeriesLike,
    real1: SeriesLike,
    timeperiod: int = 5,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return rolling covariance (COVAR)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    series0 = to_series(real0, name="real0")
    series1 = to_series(real1, name="real1")
    if backend_key == "rust":
        indicator = RustCOVAR(use_period)
        out = _run_rust_dual_series(series0, series1, indicator.update)
        return finalize_output(out, as_series=as_series)
    mean0 = cast(pd.Series, series0.rolling(use_period).mean())
    mean1 = cast(pd.Series, series1.rolling(use_period).mean())
    out = cast(
        pd.Series,
        ((series0 - mean0) * (series1 - mean1)).rolling(use_period).mean(),
    )
    return finalize_output(out, as_series=as_series)


def ADXR(
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    timeperiod: int = 14,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Average Directional Movement Index Rating (ADXR)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustADXR(use_period)
        out = _run_rust_hlc_series(
            high_series,
            low_series,
            close_series,
            indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    adx_series = cast(
        pd.Series,
        ADX(
            high_series,
            low_series,
            close_series,
            timeperiod=use_period,
            as_series=True,
            backend="python",
        ),
    )
    out = cast(pd.Series, (adx_series + adx_series.shift(use_period)) / 2.0)
    return finalize_output(out, as_series=as_series)


