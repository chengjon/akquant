"""Candlestick pattern indicator wrappers."""

from __future__ import annotations

from typing import cast

import pandas as pd

from ..akquant import CDL2CROWS as RustCDL2CROWS
from ..akquant import CDL3INSIDE as RustCDL3INSIDE
from ..akquant import CDL3OUTSIDE as RustCDL3OUTSIDE
from ..akquant import CDLBELTHOLD as RustCDLBELTHOLD
from ..akquant import CDLCLOSINGMARUBOZU as RustCDLCLOSINGMARUBOZU
from ..akquant import CDLDRAGONFLYDOJI as RustCDLDRAGONFLYDOJI
from ..akquant import CDLGRAVESTONEDOJI as RustCDLGRAVESTONEDOJI
from ..akquant import CDLLONGLINE as RustCDLLONGLINE
from ..akquant import CDLSHORTLINE as RustCDLSHORTLINE
from ..akquant import CDLSTALLEDPATTERN as RustCDLSTALLEDPATTERN
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
from ..akquant import CDLTRISTAR as RustCDLTRISTAR
from ..akquant import CDL3LINESTRIKE as RustCDL3LINESTRIKE
from ..akquant import CDLADVANCEBLOCK as RustCDLADVANCEBLOCK
from ..akquant import CDLTASUKIGAP as RustCDLTASUKIGAP
from ..akquant import CDLIDENTICAL3CROWS as RustCDLIDENTICAL3CROWS
from ..akquant import CDLBREAKAWAY as RustCDLBREAKAWAY
from ..akquant import CDLCONCEALBABYSWALL as RustCDLCONCEALBABYSWALL
from ..akquant import CDLMATHOLD as RustCDLMATHOLD
from ..akquant import CDLSEPARATINGLINES as RustCDLSEPARATINGLINES
from ..akquant import CDLXSIDEGAP3METHODS as RustCDLXSIDEGAP3METHODS
from ..akquant import CDL3STARSINSOUTH as RustCDL3STARSINSOUTH
from ..akquant import CDLCOUNTERATTACK as RustCDLCOUNTERATTACK
from ..akquant import CDLGAPSIDESIDEWHITE as RustCDLGAPSIDESIDEWHITE
from ..akquant import CDLHOMINGPIGEON as RustCDLHOMINGPIGEON
from ..akquant import CDLLADDERBOTTOM as RustCDLLADDERBOTTOM
from ..akquant import CDLMATCHINGLOW as RustCDLMATCHINGLOW
from ..akquant import CDLRICKSHAWMAN as RustCDLRICKSHAWMAN
from ..akquant import CDLTAKURI as RustCDLTAKURI
from ..akquant import CDLUNIQUE3RIVER as RustCDLUNIQUE3RIVER
from ..akquant import CDLMATCHINGHIGH as RustCDLMATCHINGHIGH
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


def CDL2CROWS(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Two Crows candlestick pattern (bearish reversal, 3-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDL2CROWS()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDL3INSIDE(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Three Inside Up/Down candlestick pattern (3-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDL3INSIDE()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDL3OUTSIDE(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Three Outside Up/Down candlestick pattern (3-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDL3OUTSIDE()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLBELTHOLD(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Belt-hold candlestick pattern (1-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLBELTHOLD()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLCLOSINGMARUBOZU(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Closing Marubozu candlestick pattern (1-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLCLOSINGMARUBOZU()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLDRAGONFLYDOJI(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Dragonfly Doji candlestick pattern (bullish, 1-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLDRAGONFLYDOJI()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLGRAVESTONEDOJI(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Gravestone Doji candlestick pattern (bearish, 1-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLGRAVESTONEDOJI()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLLONGLINE(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Long Line candlestick pattern (1-bar, body > 70% of range)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLLONGLINE()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLSHORTLINE(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Short Line candlestick pattern (1-bar, body < 30% of range)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLSHORTLINE()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLSTALLEDPATTERN(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Stalled Pattern candlestick pattern (bearish, 3-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLSTALLEDPATTERN()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLTRISTAR(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Tristar pattern (reversal, 3-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLTRISTAR()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDL3LINESTRIKE(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Three Line Strike pattern (reversal, 4-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDL3LINESTRIKE()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLADVANCEBLOCK(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Advance Block pattern (bearish reversal, 3-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLADVANCEBLOCK()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLTASUKIGAP(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Tasuki Gap pattern (continuation, 3-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLTASUKIGAP()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLIDENTICAL3CROWS(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Identical Three Crows pattern (bearish, 3-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLIDENTICAL3CROWS()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLBREAKAWAY(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Breakaway pattern (reversal, 5-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLBREAKAWAY()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLCONCEALBABYSWALL(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Concealing Baby Swallow pattern (bullish, 4-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLCONCEALBABYSWALL()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLMATHOLD(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Mat Hold pattern (bullish continuation, 5-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLMATHOLD()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLSEPARATINGLINES(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Separating Lines pattern (continuation, 2-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLSEPARATINGLINES()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLXSIDEGAP3METHODS(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Upside/Downside Gap Three Methods pattern (3-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLXSIDEGAP3METHODS()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDL3STARSINSOUTH(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Three Stars In The South (bullish reversal, 3-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDL3STARSINSOUTH()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLCOUNTERATTACK(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Counterattack pattern (reversal, 2-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLCOUNTERATTACK()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLGAPSIDESIDEWHITE(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Up/Down-gap Side-by-Side White Lines (continuation, 3-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLGAPSIDESIDEWHITE()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLHOMINGPIGEON(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Homing Pigeon (bullish reversal, 2-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLHOMINGPIGEON()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLLADDERBOTTOM(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Ladder Bottom (bullish reversal, 5-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLLADDERBOTTOM()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLMATCHINGLOW(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Matching Low (bullish reversal, 2-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLMATCHINGLOW()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLRICKSHAWMAN(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Rickshaw Man (indecision, 1-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLRICKSHAWMAN()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLTAKURI(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Takuri Line (bullish, 1-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLTAKURI()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLUNIQUE3RIVER(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Unique Three River Bottom (bullish, 3-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLUNIQUE3RIVER()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)


def CDLMATCHINGHIGH(
    open: SeriesLike,
    high: SeriesLike,
    low: SeriesLike,
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Matching High (bearish reversal, 2-bar)."""
    backend_key = resolve_backend(backend)
    open_series = to_series(open, name="open")
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCDLMATCHINGHIGH()
        out = _run_rust_ohlc_series(
            open_series, high_series, low_series, close_series, indicator.update,
        )
        return finalize_output(out, as_series=as_series)
    out = pd.Series(0.0, index=open_series.index)
    return finalize_output(out, as_series=as_series)
