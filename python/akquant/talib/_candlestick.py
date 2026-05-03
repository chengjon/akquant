"""Candlestick pattern indicator wrappers."""

from __future__ import annotations

from typing import cast

import pandas as pd

from ..akquant import CDL_3BLACKCROWS as RustCDL_3BLACKCROWS
from ..akquant import CDL_3WHITESOLDIERS as RustCDL_3WHITESOLDIERS
from ..akquant import CDL_ENGULFING as RustCDL_ENGULFING
from ..akquant import CDL_EVENINGSTAR as RustCDL_EVENINGSTAR
from ..akquant import CDL_HARAMI as RustCDL_HARAMI
from ..akquant import CDL_MORNINGSTAR as RustCDL_MORNINGSTAR
from ..akquant import CDL_SHOOTINGSTAR as RustCDL_SHOOTINGSTAR
from ..akquant import CDLDARKCLOUDCOVER as RustCDLDARKCLOUDCOVER
from ..akquant import CDLDOJI as RustCDLDOJI
from ..akquant import CDLHAMMER as RustCDLHAMMER
from ..akquant import CDLHANGINGMAN as RustCDLHANGINGMAN
from ..akquant import CDLHARAMICROSS as RustCDLHARAMICROSS
from ..akquant import CDLINNECK as RustCDLINNECK
from ..akquant import CDLKICKING as RustCDLKICKING
from ..akquant import CDLMARUBOZU as RustCDLMARUBOZU
from ..akquant import CDLONNECK as RustCDLONNECK
from ..akquant import CDLPIERCING as RustCDLPIERCING
from ..akquant import CDLRISEFALL3METHODS as RustCDLRISEFALL3METHODS
from ..akquant import CDLSPINNINGTOP as RustCDLSPINNINGTOP
from ..akquant import CDLTHRUSTING as RustCDLTHRUSTING
from ._dispatch import (
    _run_rust_ohlc_series,
)
from .backend import resolve_backend
from .core import SeriesLike, finalize_output, to_series


def CDLDOJI(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Doji candlestick pattern."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLDOJI()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    r = high_series - low_series
    b = (close_series - open_series).abs()
    out = cast(pd.Series, b.where(r > 1e-12, 0.0) <= r * 0.1).astype(float)
    return finalize_output(out, as_series=as_series)


def CDLHAMMER(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Hammer candlestick pattern (bullish reversal)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLHAMMER()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLHANGINGMAN(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Hanging Man candlestick pattern (bearish reversal)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLHANGINGMAN()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDL_ENGULFING(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Engulfing candlestick pattern."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDL_ENGULFING()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDL_HARAMI(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Harami candlestick pattern."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDL_HARAMI()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDL_MORNINGSTAR(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Morning Star candlestick pattern (bullish reversal)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDL_MORNINGSTAR()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDL_EVENINGSTAR(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Evening Star candlestick pattern (bearish reversal)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDL_EVENINGSTAR()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDL_3BLACKCROWS(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Three Black Crows candlestick pattern (bearish)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDL_3BLACKCROWS()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDL_3WHITESOLDIERS(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Three White Soldiers candlestick pattern (bullish)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDL_3WHITESOLDIERS()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLPIERCING(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Piercing Line candlestick pattern (bullish reversal)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLPIERCING()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLDARKCLOUDCOVER(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Dark Cloud Cover candlestick pattern (bearish reversal)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLDARKCLOUDCOVER()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLHARAMICROSS(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Harami Cross candlestick pattern (doji inside prior body)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLHARAMICROSS()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLMARUBOZU(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Marubozu candlestick pattern (no/minimal shadows)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLMARUBOZU()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLKICKING(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Kicking candlestick pattern (gap with opposite marubozu)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLKICKING()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLSPINNINGTOP(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Spinning Top candlestick pattern (small body, similar shadows)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLSPINNINGTOP()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLRISEFALL3METHODS(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Rising/Falling Three Methods candlestick pattern."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLRISEFALL3METHODS()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLTHRUSTING(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Thrusting candlestick pattern (bearish continuation)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLTHRUSTING()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLINNECK(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """In-Neck candlestick pattern (bearish continuation)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLINNECK()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLONNECK(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """On-Neck candlestick pattern (bearish continuation)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLONNECK()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDL_SHOOTINGSTAR(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Shooting Star candlestick pattern (bearish reversal)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDL_SHOOTINGSTAR()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)
