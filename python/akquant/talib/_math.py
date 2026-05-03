"""Pure math transform indicators."""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd

from ..akquant import ABS as RustABS
from ..akquant import ACOS as RustACOS
from ..akquant import ADD as RustADD
from ..akquant import ASIN as RustASIN
from ..akquant import ATAN as RustATAN
from ..akquant import CEIL as RustCEIL
from ..akquant import CLAMP01 as RustCLAMP01
from ..akquant import CLIP as RustCLIP
from ..akquant import COS as RustCOS
from ..akquant import COSH as RustCOSH
from ..akquant import CUBE as RustCUBE
from ..akquant import DEG2RAD as RustDEG2RAD
from ..akquant import DIV as RustDIV
from ..akquant import EXP as RustEXP
from ..akquant import EXPM1 as RustEXPM1
from ..akquant import FLOOR as RustFLOOR
from ..akquant import HT_DCPERIOD as RustHT_DCPERIOD
from ..akquant import HT_DCPHASE as RustHT_DCPHASE
from ..akquant import HT_PHASOR as RustHT_PHASOR
from ..akquant import HT_TRENDLINE as RustHT_TRENDLINE
from ..akquant import INV_SQRT as RustINV_SQRT
from ..akquant import LN as RustLN
from ..akquant import LOG1P as RustLOG1P
from ..akquant import LOG10 as RustLOG10
from ..akquant import MAX2 as RustMAX2
from ..akquant import MIN2 as RustMIN2
from ..akquant import MOD as RustMOD
from ..akquant import MULT as RustMULT
from ..akquant import POW as RustPOW
from ..akquant import RECIP as RustRECIP
from ..akquant import ROUND as RustROUND
from ..akquant import SIGN as RustSIGN
from ..akquant import SIN as RustSIN
from ..akquant import SINH as RustSINH
from ..akquant import SQ as RustSQ
from ..akquant import SQRT as RustSQRT
from ..akquant import SUB as RustSUB
from ..akquant import TAN as RustTAN
from ..akquant import TANH as RustTANH
from ._dispatch import (
    _batch_call,
    _run_rust_dual_series,
    _run_rust_single_pair_series,
    _run_rust_single_series,
)
from .backend import resolve_backend
from .core import SeriesLike, finalize_output, to_series


def LN(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return natural logarithm transform (LN)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustLN()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.log(close_series.where(close_series > 0.0, np.nan)))
    return finalize_output(out, as_series=as_series)


def LOG10(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return base-10 logarithm transform (LOG10)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustLOG10()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.log10(close_series.where(close_series > 0.0, np.nan)))
    return finalize_output(out, as_series=as_series)


def SQRT(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return square-root transform (SQRT)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustSQRT()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.sqrt(close_series.where(close_series >= 0.0, np.nan)))
    return finalize_output(out, as_series=as_series)


def CEIL(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return ceiling transform (CEIL)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCEIL()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.ceil(close_series))
    return finalize_output(out, as_series=as_series)


def FLOOR(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return floor transform (FLOOR)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustFLOOR()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.floor(close_series))
    return finalize_output(out, as_series=as_series)


def SIN(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return sine transform (SIN)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustSIN()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.sin(close_series))
    return finalize_output(out, as_series=as_series)


def COS(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return cosine transform (COS)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCOS()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.cos(close_series))
    return finalize_output(out, as_series=as_series)


def TAN(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return tangent transform (TAN)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustTAN()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.tan(close_series))
    return finalize_output(out, as_series=as_series)


def ASIN(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return arcsine transform (ASIN)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustASIN()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    valid = close_series.where(close_series.abs() <= 1.0, np.nan)
    out = cast(pd.Series, np.arcsin(valid))
    return finalize_output(out, as_series=as_series)


def ACOS(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return arccosine transform (ACOS)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustACOS()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    valid = close_series.where(close_series.abs() <= 1.0, np.nan)
    out = cast(pd.Series, np.arccos(valid))
    return finalize_output(out, as_series=as_series)


def ATAN(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return arctangent transform (ATAN)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustATAN()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.arctan(close_series))
    return finalize_output(out, as_series=as_series)


def SINH(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return hyperbolic sine transform (SINH)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustSINH()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.sinh(close_series))
    return finalize_output(out, as_series=as_series)


def COSH(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return hyperbolic cosine transform (COSH)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCOSH()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.cosh(close_series))
    return finalize_output(out, as_series=as_series)


def TANH(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return hyperbolic tangent transform (TANH)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustTANH()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.tanh(close_series))
    return finalize_output(out, as_series=as_series)


def EXP(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return exponential transform (EXP)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustEXP()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.exp(close_series))
    return finalize_output(out, as_series=as_series)


def ABS(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return absolute-value transform (ABS)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustABS()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.abs(close_series))
    return finalize_output(out, as_series=as_series)


def SIGN(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return sign transform (SIGN)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustSIGN()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.sign(close_series))
    return finalize_output(out, as_series=as_series)


def ADD(
    real0: SeriesLike,
    real1: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return element-wise addition (ADD)."""
    backend_key = resolve_backend(backend)
    series0 = to_series(real0, name="real0")
    series1 = to_series(real1, name="real1")
    if backend_key == "rust":
        indicator = RustADD()
        out = _run_rust_dual_series(series0, series1, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, series0 + series1)
    return finalize_output(out, as_series=as_series)


def SUB(
    real0: SeriesLike,
    real1: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return element-wise subtraction (SUB)."""
    backend_key = resolve_backend(backend)
    series0 = to_series(real0, name="real0")
    series1 = to_series(real1, name="real1")
    if backend_key == "rust":
        indicator = RustSUB()
        out = _run_rust_dual_series(series0, series1, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, series0 - series1)
    return finalize_output(out, as_series=as_series)


def MULT(
    real0: SeriesLike,
    real1: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return element-wise multiplication (MULT)."""
    backend_key = resolve_backend(backend)
    series0 = to_series(real0, name="real0")
    series1 = to_series(real1, name="real1")
    if backend_key == "rust":
        indicator = RustMULT()
        out = _run_rust_dual_series(series0, series1, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, series0 * series1)
    return finalize_output(out, as_series=as_series)


def DIV(
    real0: SeriesLike,
    real1: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return element-wise division (DIV)."""
    backend_key = resolve_backend(backend)
    series0 = to_series(real0, name="real0")
    series1 = to_series(real1, name="real1")
    if backend_key == "rust":
        indicator = RustDIV()
        out = _run_rust_dual_series(series0, series1, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, series0 / series1)
    out = cast(pd.Series, out.where(series1.abs() > 1e-12, np.nan))
    return finalize_output(out, as_series=as_series)


def MAX2(
    real0: SeriesLike,
    real1: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return element-wise maximum (MAX2)."""
    backend_key = resolve_backend(backend)
    series0 = to_series(real0, name="real0")
    series1 = to_series(real1, name="real1")
    if backend_key == "rust":
        indicator = RustMAX2()
        out = _run_rust_dual_series(series0, series1, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.maximum(series0, series1))
    return finalize_output(out, as_series=as_series)


def MIN2(
    real0: SeriesLike,
    real1: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return element-wise minimum (MIN2)."""
    backend_key = resolve_backend(backend)
    series0 = to_series(real0, name="real0")
    series1 = to_series(real1, name="real1")
    if backend_key == "rust":
        indicator = RustMIN2()
        out = _run_rust_dual_series(series0, series1, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.minimum(series0, series1))
    return finalize_output(out, as_series=as_series)


def CLIP(
    real: SeriesLike,
    min_value: SeriesLike,
    max_value: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return element-wise clipping (CLIP)."""
    backend_key = resolve_backend(backend)
    series = to_series(real, name="real")
    min_series = to_series(min_value, name="min_value")
    max_series = to_series(max_value, name="max_value")
    if backend_key == "rust":
        indicator = RustCLIP()
        values_arr = series.to_numpy(dtype=float, copy=False)
        min_arr = min_series.to_numpy(dtype=float, copy=False)
        max_arr = max_series.to_numpy(dtype=float, copy=False)
        batch_out = _batch_call(
            indicator.update, "update_many_clip", values_arr, min_arr, max_arr
        )
        if batch_out is not None:
            arr = np.asarray(batch_out, dtype=float)
            if arr.shape[0] != len(series):
                arr = np.full(len(series), np.nan, dtype=float)
        else:
            arr = np.full(len(series), np.nan, dtype=float)
            for idx, (value, min_v, max_v) in enumerate(
                zip(series, min_series, max_series)
            ):
                out_val = indicator.update(float(value), float(min_v), float(max_v))
                if out_val is not None:
                    arr[idx] = float(out_val)
        out_series = pd.Series(arr, index=series.index, dtype=float)
        return finalize_output(out_series, as_series=as_series)
    lo = cast(pd.Series, np.minimum(min_series, max_series))
    hi = cast(pd.Series, np.maximum(min_series, max_series))
    out = cast(pd.Series, np.minimum(np.maximum(series, lo), hi))
    return finalize_output(out, as_series=as_series)


def ROUND(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return element-wise round (ROUND)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustROUND()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.round(close_series))
    return finalize_output(out, as_series=as_series)


def POW(
    real0: SeriesLike,
    real1: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return element-wise power (POW)."""
    backend_key = resolve_backend(backend)
    series0 = to_series(real0, name="real0")
    series1 = to_series(real1, name="real1")
    if backend_key == "rust":
        indicator = RustPOW()
        out = _run_rust_dual_series(series0, series1, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.power(series0, series1))
    return finalize_output(out, as_series=as_series)


def MOD(
    real0: SeriesLike,
    real1: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return element-wise modulo (MOD)."""
    backend_key = resolve_backend(backend)
    series0 = to_series(real0, name="real0")
    series1 = to_series(real1, name="real1")
    if backend_key == "rust":
        indicator = RustMOD()
        out = _run_rust_dual_series(series0, series1, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.mod(series0, series1))
    out = cast(pd.Series, out.where(series1.abs() > 1e-12, np.nan))
    return finalize_output(out, as_series=as_series)


def CLAMP01(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return clamp-to-[0,1] transform (CLAMP01)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCLAMP01()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.clip(close_series, 0.0, 1.0))
    return finalize_output(out, as_series=as_series)


def SQ(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return element-wise square (SQ)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustSQ()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.square(close_series))
    return finalize_output(out, as_series=as_series)


def CUBE(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return element-wise cube (CUBE)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustCUBE()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.power(close_series, 3.0))
    return finalize_output(out, as_series=as_series)


def RECIP(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return reciprocal transform (RECIP)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustRECIP()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, 1.0 / close_series)
    out = cast(pd.Series, out.where(close_series.abs() > 1e-12, np.nan))
    return finalize_output(out, as_series=as_series)


def INV_SQRT(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return inverse square-root transform (INV_SQRT)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustINV_SQRT()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    valid = close_series.where(close_series > 0.0, np.nan)
    out = cast(pd.Series, 1.0 / np.sqrt(valid))
    return finalize_output(out, as_series=as_series)


def LOG1P(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return natural logarithm of one plus input (LOG1P)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustLOG1P()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.log1p(close_series))
    return finalize_output(out, as_series=as_series)


def EXPM1(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return exponential minus one transform (EXPM1)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustEXPM1()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.expm1(close_series))
    return finalize_output(out, as_series=as_series)


def DEG2RAD(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Return degree-to-radian transform (DEG2RAD)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustDEG2RAD()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = cast(pd.Series, np.deg2rad(close_series))
    return finalize_output(out, as_series=as_series)


def HT_TRENDLINE(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Hilbert Transform trendline approximation."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustHT_TRENDLINE()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    weights = np.array([1.0, 2.0, 3.0, 4.0, 3.0, 2.0, 1.0], dtype=float)
    denom = float(weights.sum())
    out = cast(
        pd.Series,
        close_series.rolling(7).apply(
            lambda arr: float(np.dot(arr, weights) / denom),
            raw=True,
        ),
    )
    return finalize_output(out, as_series=as_series)


def HT_DCPERIOD(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Hilbert Transform - Dominant Cycle Period."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustHT_DCPERIOD()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = pd.Series(np.nan, index=close_series.index)
    return finalize_output(out, as_series=as_series)


def HT_DCPHASE(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> pd.Series | object:
    """Hilbert Transform - Dominant Cycle Phase (degrees, 0-360)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustHT_DCPHASE()
        out = _run_rust_single_series(close_series, indicator.update)
        return finalize_output(out, as_series=as_series)
    out = pd.Series(np.nan, index=close_series.index)
    return finalize_output(out, as_series=as_series)


def HT_PHASOR(
    close: SeriesLike,
    *,
    as_series: bool = False,
    backend: str = "auto",
) -> tuple[pd.Series | object, pd.Series | object]:
    """Hilbert Transform - Phasor Components (in_phase, quadrature)."""
    backend_key = resolve_backend(backend)
    close_series = to_series(close, name="close")
    if backend_key == "rust":
        indicator = RustHT_PHASOR()
        in_phase_s, quadrature_s = _run_rust_single_pair_series(
            close_series, indicator.update
        )
        return (
            finalize_output(in_phase_s, as_series=as_series),
            finalize_output(quadrature_s, as_series=as_series),
        )
    nan_s = pd.Series(np.nan, index=close_series.index)
    return (
        finalize_output(nan_s, as_series=as_series),
        finalize_output(nan_s.copy(), as_series=as_series),
    )

