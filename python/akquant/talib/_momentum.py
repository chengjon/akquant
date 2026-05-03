"""Price, momentum, volume, and advanced overlay indicators."""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd

from ..akquant import AD as RustAD
from ..akquant import ADOSC as RustADOSC
from ..akquant import ATR as RustATR
from ..akquant import AVGPRICE as RustAVGPRICE
from ..akquant import BOP as RustBOP
from ..akquant import CMO as RustCMO
from ..akquant import DEMA as RustDEMA
from ..akquant import KAMA as RustKAMA
from ..akquant import MACD as RustMACD
from ..akquant import MAMA as RustMAMA
from ..akquant import MEDPRICE as RustMEDPRICE
from ..akquant import MFI as RustMFI
from ..akquant import MIDPRICE as RustMIDPRICE
from ..akquant import MOM as RustMOM
from ..akquant import NATR as RustNATR
from ..akquant import OBV as RustOBV
from ..akquant import SAR as RustSAR
from ..akquant import STDDEV as RustSTDDEV
from ..akquant import STOCH as RustSTOCH
from ..akquant import T3 as RustT3
from ..akquant import TEMA as RustTEMA
from ..akquant import TRANGE as RustTRANGE
from ..akquant import TRIX as RustTRIX
from ..akquant import TYPPRICE as RustTYPPRICE
from ..akquant import VAR as RustVAR
from ..akquant import WCLPRICE as RustWCLPRICE
from ..akquant import BollingerBands as RustBollingerBands
from ._dispatch import (
    _batch_call,
    _ensure_period,
    _rolling_mean,
    _run_rust_dual_series,
    _run_rust_hl_series,
    _run_rust_hlc_pair_series,
    _run_rust_hlc_series,
    _run_rust_hlcv_series,
    _run_rust_ohlc_series,
    _run_rust_single_pair_series,
    _run_rust_single_series,
)
from .backend import resolve_backend
from .core import SeriesLike, finalize_output, to_series


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
        out_series = _run_rust_hlc_series(
            high_series, low_series, close_series, indicator.update
        )
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


def TRANGE(
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Calculate True Range (TRANGE)."""
    backend_key = resolve_backend(backend)
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustTRANGE()
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
    out = cast(pd.Series, tr_components.max(axis=1))
    return finalize_output(out, as_series=as_series)


def MEDPRICE(
    high: SeriesLike,
    low: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Median Price (MEDPRICE)."""
    backend_key = resolve_backend(backend)
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    if backend_key == "rust":
        indicator = RustMEDPRICE()
        out = _run_rust_hl_series(high_series, low_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, (high_series + low_series) / 2.0)
    return finalize_output(out, as_series=as_series)


def AVGPRICE(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Average Price (AVGPRICE)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustAVGPRICE()
        out = _run_rust_ohlc_series(
            open_series,
            high_series,
            low_series,
            close_series,
            indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, (open_series + high_series + low_series + close_series) / 4.0)
    return finalize_output(out, as_series=as_series)


def TYPPRICE(
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Typical Price (TYPPRICE)."""
    backend_key = resolve_backend(backend)
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustTYPPRICE()
        out = _run_rust_hlc_series(
            high_series,
            low_series,
            close_series,
            indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, (high_series + low_series + close_series) / 3.0)
    return finalize_output(out, as_series=as_series)


def WCLPRICE(
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Weighted Close Price (WCLPRICE)."""
    backend_key = resolve_backend(backend)
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustWCLPRICE()
        out = _run_rust_hlc_series(
            high_series,
            low_series,
            close_series,
            indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, (high_series + low_series + 2.0 * close_series) / 4.0)
    return finalize_output(out, as_series=as_series)


def MIDPRICE(
    high: SeriesLike,
    low: SeriesLike,
    timeperiod: int = 14,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """MidPrice over rolling high/low."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    if backend_key == "rust":
        indicator = RustMIDPRICE(use_period)
        out = _run_rust_hl_series(high_series, low_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    roll_high = cast(pd.Series, high_series.rolling(use_period).max())
    roll_low = cast(pd.Series, low_series.rolling(use_period).min())
    out = cast(pd.Series, (roll_high + roll_low) / 2.0)
    return finalize_output(out, as_series=as_series)


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
        close_arr = close_series.to_numpy(dtype=float, copy=False)
        batch_out = _batch_call(indicator.update, "update_many", close_arr)
        dif = np.full(len(close_series), np.nan, dtype=float)
        dea = np.full(len(close_series), np.nan, dtype=float)
        hist = np.full(len(close_series), np.nan, dtype=float)
        if isinstance(batch_out, (tuple, list)) and len(batch_out) == 3:
            dif_arr = np.asarray(batch_out[0], dtype=float)
            dea_arr = np.asarray(batch_out[1], dtype=float)
            hist_arr = np.asarray(batch_out[2], dtype=float)
            if (
                dif_arr.shape[0] == len(close_series)
                and dea_arr.shape[0] == len(close_series)
                and hist_arr.shape[0] == len(close_series)
            ):
                dif, dea, hist = dif_arr, dea_arr, hist_arr
        else:
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


def MAMA(
    close: SeriesLike,
    fastlimit: float = 0.5,
    slowlimit: float = 0.05,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> tuple[pd.Series | object, pd.Series | object]:
    """MESA Adaptive Moving Average returning (mama, fama)."""
    backend_key = resolve_backend(backend)
    if fastlimit <= 0.0 or slowlimit <= 0.0:
        raise ValueError("fastlimit and slowlimit must be > 0")
    if fastlimit < slowlimit:
        raise ValueError("fastlimit must be >= slowlimit")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustMAMA(float(fastlimit), float(slowlimit))
        mama_s, fama_s = _run_rust_single_pair_series(close_series, indicator.update)
        return (
            finalize_output(mama_s, as_series=as_series),
            finalize_output(fama_s, as_series=as_series),
        )
    prev = cast(pd.Series, close_series.shift(1))
    base = cast(pd.Series, prev.abs().clip(lower=1e-12))
    ratio = cast(
        pd.Series,
        ((close_series - prev).abs() / base).clip(lower=0.0, upper=1.0),
    )
    alpha = cast(pd.Series, (fastlimit * ratio).clip(lower=slowlimit, upper=fastlimit))
    mama = pd.Series(np.nan, index=close_series.index, dtype=float)
    fama = pd.Series(np.nan, index=close_series.index, dtype=float)
    for idx in range(len(close_series)):
        value_i = float(close_series.iloc[idx])
        alpha_i = (
            float(alpha.iloc[idx]) if np.isfinite(alpha.iloc[idx]) else float(slowlimit)
        )
        prev_mama = (
            value_i
            if idx == 0 or not np.isfinite(mama.iloc[idx - 1])
            else float(mama.iloc[idx - 1])
        )
        mama.iloc[idx] = alpha_i * value_i + (1.0 - alpha_i) * prev_mama
        prev_fama = (
            float(mama.iloc[idx])
            if idx == 0 or not np.isfinite(fama.iloc[idx - 1])
            else float(fama.iloc[idx - 1])
        )
        fama.iloc[idx] = (0.5 * alpha_i) * float(mama.iloc[idx]) + (
            1.0 - 0.5 * alpha_i
        ) * prev_fama
    mama.iloc[0] = np.nan
    fama.iloc[0] = np.nan
    return (
        finalize_output(cast(pd.Series, mama), as_series=as_series),
        finalize_output(cast(pd.Series, fama), as_series=as_series),
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
        close_arr = close_series.to_numpy(dtype=float, copy=False)
        batch_out = _batch_call(indicator.update, "update_many", close_arr)
        upper = np.full(len(close_series), np.nan, dtype=float)
        middle = np.full(len(close_series), np.nan, dtype=float)
        lower = np.full(len(close_series), np.nan, dtype=float)
        if isinstance(batch_out, (tuple, list)) and len(batch_out) == 3:
            upper_arr = np.asarray(batch_out[0], dtype=float)
            middle_arr = np.asarray(batch_out[1], dtype=float)
            lower_arr = np.asarray(batch_out[2], dtype=float)
            if (
                upper_arr.shape[0] == len(close_series)
                and middle_arr.shape[0] == len(close_series)
                and lower_arr.shape[0] == len(close_series)
            ):
                upper, middle, lower = upper_arr, middle_arr, lower_arr
        else:
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


def STDDEV(
    close: SeriesLike,
    timeperiod: int = 5,
    nbdev: float = 1.0,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Compute standard deviation (STDDEV)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustSTDDEV(use_period, float(nbdev))
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(
        pd.Series,
        close_series.rolling(use_period).std(ddof=0) * float(nbdev),
    )
    return finalize_output(out, as_series=as_series)


def VAR(
    close: SeriesLike,
    timeperiod: int = 5,
    nbdev: float = 1.0,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Variance (VAR)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustVAR(use_period, float(nbdev))
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(
        pd.Series,
        close_series.rolling(use_period).var(ddof=0) * float(nbdev) * float(nbdev),
    )
    return finalize_output(out, as_series=as_series)


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


def CMO(
    close: SeriesLike,
    timeperiod: int = 14,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Chande Momentum Oscillator (CMO)."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCMO(use_period)
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    delta = cast(pd.Series, close_series.diff())
    gains = cast(pd.Series, delta.clip(lower=0.0))
    losses = cast(pd.Series, (-delta).clip(lower=0.0))
    gain_sum = cast(pd.Series, gains.rolling(use_period).sum())
    loss_sum = cast(pd.Series, losses.rolling(use_period).sum())
    denom = cast(pd.Series, gain_sum + loss_sum)
    out = cast(pd.Series, 100.0 * (gain_sum - loss_sum) / denom)
    out = cast(pd.Series, out.where(denom > 1e-12, 0.0))
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


def AD(
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    volume: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Chaikin A/D Line (AD)."""
    backend_key = resolve_backend(backend)
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    volume_series = to_series(volume, name="volume")
    if backend_key == "rust":
        indicator = RustAD()
        out = _run_rust_hlcv_series(
            high_series,
            low_series,
            close_series,
            volume_series,
            indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    denom = cast(pd.Series, high_series - low_series)
    mfm = cast(
        pd.Series,
        ((close_series - low_series) - (high_series - close_series)) / denom,
    )
    mfm = cast(pd.Series, mfm.where(denom.abs() > 1e-12, 0.0))
    out = cast(pd.Series, (mfm * volume_series).cumsum())
    return finalize_output(out, as_series=as_series)


def ADOSC(
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    volume: SeriesLike,
    fastperiod: int = 3,
    slowperiod: int = 10,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Chaikin A/D Oscillator (ADOSC)."""
    backend_key = resolve_backend(backend)
    fast_p = _ensure_period(fastperiod, "fastperiod")
    slow_p = _ensure_period(slowperiod, "slowperiod")
    if slow_p <= fast_p:
        raise ValueError("slowperiod must be > fastperiod")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    volume_series = to_series(volume, name="volume")
    if backend_key == "rust":
        indicator = RustADOSC(fast_p, slow_p)
        out = _run_rust_hlcv_series(
            high_series,
            low_series,
            close_series,
            volume_series,
            indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    ad_line = cast(
        pd.Series,
        AD(
            high_series,
            low_series,
            close_series,
            volume_series,
            as_series=True,
            backend="python",
        ),
    )
    fast_ema = cast(
        pd.Series,
        ad_line.ewm(alpha=2.0 / (fast_p + 1.0), adjust=False).mean(),
    )
    slow_ema = cast(
        pd.Series,
        ad_line.ewm(alpha=2.0 / (slow_p + 1.0), adjust=False).mean(),
    )
    out = cast(pd.Series, fast_ema - slow_ema)
    out.iloc[: slow_p - 1] = np.nan
    return finalize_output(out, as_series=as_series)


def BOP(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Balance Of Power (BOP)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustBOP()
        out = _run_rust_ohlc_series(
            open_series,
            high_series,
            low_series,
            close_series,
            indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    denominator = cast(pd.Series, high_series - low_series)
    out = cast(pd.Series, (close_series - open_series) / denominator)
    out = cast(pd.Series, out.where(denominator.abs() > 1e-12, 0.0))
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


def T3(
    close: SeriesLike,
    timeperiod: int = 5,
    vfactor: float = 0.7,
    *,
    period: int | None = None,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Triple Exponential Moving Average T3."""
    backend_key = resolve_backend(backend)
    use_period = _ensure_period(period or timeperiod, "timeperiod")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustT3(use_period, float(vfactor))
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    e1 = cast(
        pd.Series,
        close_series.ewm(alpha=2.0 / (use_period + 1.0), adjust=False).mean(),
    )
    e2 = cast(pd.Series, e1.ewm(alpha=2.0 / (use_period + 1.0), adjust=False).mean())
    e3 = cast(pd.Series, e2.ewm(alpha=2.0 / (use_period + 1.0), adjust=False).mean())
    e4 = cast(pd.Series, e3.ewm(alpha=2.0 / (use_period + 1.0), adjust=False).mean())
    e5 = cast(pd.Series, e4.ewm(alpha=2.0 / (use_period + 1.0), adjust=False).mean())
    e6 = cast(pd.Series, e5.ewm(alpha=2.0 / (use_period + 1.0), adjust=False).mean())
    a = float(vfactor)
    c1 = -(a**3)
    c2 = 3.0 * a * a + 3.0 * (a**3)
    c3 = -6.0 * a * a - 3.0 * a - 3.0 * (a**3)
    c4 = 1.0 + 3.0 * a + (a**3) + 3.0 * a * a
    out = cast(pd.Series, c1 * e6 + c2 * e5 + c3 * e4 + c4 * e3)
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


# ---------------------------------------------------------------------------
# Candlestick Pattern Recognition (CDL series)
# Each returns: +100 (bullish), -100 (bearish), 0 (no pattern)
# ---------------------------------------------------------------------------


