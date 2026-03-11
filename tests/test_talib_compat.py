from __future__ import annotations

import numpy as np
import pandas as pd
from akquant import talib as ta


def _sample_ohlc(size: int = 30) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Build deterministic OHLC sample series."""
    idx = pd.date_range("2024-01-01", periods=size, freq="D", tz="UTC")
    close = pd.Series(np.linspace(10.0, 25.0, size), index=idx)
    high = close + 1.0
    low = close - 1.0
    return high, low, close


def test_talib_roc_period_alias_matches_timeperiod() -> None:
    """ROC should support both timeperiod and period alias."""
    _, _, close = _sample_ohlc(size=20)
    a = ta.ROC(close, timeperiod=5)
    b = ta.ROC(close, period=5)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_talib_cci_supports_series_output_with_index() -> None:
    """as_series should preserve pandas index for indicator output."""
    high, low, close = _sample_ohlc(size=40)
    cci = ta.CCI(high, low, close, timeperiod=14, as_series=True)
    assert isinstance(cci, pd.Series)
    assert cci.index.equals(close.index)


def test_talib_stoch_returns_slowk_then_slowd() -> None:
    """STOCH should return (slowk, slowd) with identical shape."""
    high, low, close = _sample_ohlc(size=40)
    slowk, slowd = ta.STOCH(high, low, close)
    assert isinstance(slowk, np.ndarray)
    assert isinstance(slowd, np.ndarray)
    assert slowk.shape == close.shape
    assert slowd.shape == close.shape
    valid_k = np.where(~np.isnan(slowk))[0]
    valid_d = np.where(~np.isnan(slowd))[0]
    assert len(valid_k) > 0
    assert len(valid_d) > 0
    assert int(valid_d[0]) >= int(valid_k[0])


def test_talib_adx_has_warmup_nans() -> None:
    """ADX output should contain warmup NaNs before valid values appear."""
    high, low, close = _sample_ohlc(size=60)
    adx = ta.ADX(high, low, close, timeperiod=14)
    assert isinstance(adx, np.ndarray)
    assert np.isnan(adx[:14]).all()
    assert np.isfinite(adx[30:]).any()


def test_talib_mom_period_alias_matches_timeperiod() -> None:
    """MOM should support both timeperiod and period alias."""
    _, _, close = _sample_ohlc(size=30)
    a = ta.MOM(close, timeperiod=10)
    b = ta.MOM(close, period=10)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_talib_mfi_supports_series_output_with_index() -> None:
    """MFI as_series should preserve pandas index for output."""
    high, low, close = _sample_ohlc(size=40)
    volume = pd.Series(np.linspace(1000.0, 3000.0, 40), index=close.index)
    mfi = ta.MFI(high, low, close, volume, timeperiod=14, as_series=True)
    assert isinstance(mfi, pd.Series)
    assert mfi.index.equals(close.index)


def test_talib_tema_period_alias_matches_timeperiod() -> None:
    """TEMA should support both timeperiod and period alias."""
    _, _, close = _sample_ohlc(size=80)
    a = ta.TEMA(close, timeperiod=20)
    b = ta.TEMA(close, period=20)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_talib_kama_period_alias_matches_timeperiod() -> None:
    """KAMA should support both timeperiod and period alias."""
    _, _, close = _sample_ohlc(size=60)
    a = ta.KAMA(close, timeperiod=10)
    b = ta.KAMA(close, period=10)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_talib_natr_period_alias_matches_timeperiod() -> None:
    """NATR should support both timeperiod and period alias."""
    high, low, close = _sample_ohlc(size=60)
    a = ta.NATR(high, low, close, timeperiod=14)
    b = ta.NATR(high, low, close, period=14)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)
