from __future__ import annotations

import numpy as np
import pytest
from akquant import talib as ta


def test_talib_backend_auto_uses_python_path() -> None:
    """Auto backend should execute successfully without TA-Lib dependency."""
    close = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], dtype=float)
    roc = ta.ROC(close, timeperiod=3, backend="auto")
    assert isinstance(roc, np.ndarray)
    assert roc.shape == close.shape


def test_talib_backend_rust_roc_runs() -> None:
    """Rust backend should run for ROC and return ndarray."""
    close = np.linspace(10.0, 20.0, 40)
    roc = ta.ROC(close, timeperiod=10, backend="rust")
    assert isinstance(roc, np.ndarray)
    assert roc.shape == close.shape
    assert np.isfinite(roc[15:]).any()


def test_talib_backend_invalid_value_raises() -> None:
    """Invalid backend key should raise ValueError."""
    close = np.array([1.0, 2.0, 3.0], dtype=float)
    with pytest.raises(ValueError):
        _ = ta.ROC(close, backend="gpu")


def test_talib_backend_rust_rsi_runs() -> None:
    """Rust backend should run for RSI and return ndarray."""
    close = np.linspace(10.0, 20.0, 40)
    rsi = ta.RSI(close, timeperiod=14, backend="rust")
    assert isinstance(rsi, np.ndarray)
    assert rsi.shape == close.shape
    assert np.isfinite(rsi[20:]).any()


def test_talib_backend_rust_macd_runs() -> None:
    """Rust backend should run for MACD and return three arrays."""
    close = np.linspace(10.0, 20.0, 80)
    macd, signal, hist = ta.MACD(close, backend="rust")
    assert isinstance(macd, np.ndarray)
    assert isinstance(signal, np.ndarray)
    assert isinstance(hist, np.ndarray)
    assert macd.shape == close.shape
    assert signal.shape == close.shape
    assert hist.shape == close.shape


def test_talib_backend_rust_bbands_runs() -> None:
    """Rust backend should run for BBANDS with symmetric deviations."""
    close = np.linspace(10.0, 20.0, 50)
    upper, middle, lower = ta.BBANDS(close, timeperiod=20, backend="rust")
    assert isinstance(upper, np.ndarray)
    assert isinstance(middle, np.ndarray)
    assert isinstance(lower, np.ndarray)
    assert upper.shape == close.shape
    assert middle.shape == close.shape
    assert lower.shape == close.shape


def test_talib_backend_rust_willr_runs() -> None:
    """Rust backend should run for WILLR and return ndarray."""
    close = np.linspace(10.0, 20.0, 50)
    high = close + 1.0
    low = close - 1.0
    willr = ta.WILLR(high, low, close, timeperiod=14, backend="rust")
    assert isinstance(willr, np.ndarray)
    assert willr.shape == close.shape
    assert np.isfinite(willr[20:]).any()


def test_talib_backend_rust_cci_runs() -> None:
    """Rust backend should run for CCI and return ndarray."""
    close = np.linspace(10.0, 20.0, 60)
    high = close + 1.0
    low = close - 1.0
    cci = ta.CCI(high, low, close, timeperiod=14, backend="rust")
    assert isinstance(cci, np.ndarray)
    assert cci.shape == close.shape
    assert np.isfinite(cci[25:]).any()


def test_talib_backend_rust_adx_runs() -> None:
    """Rust backend should run for ADX and return ndarray."""
    close = np.linspace(10.0, 20.0, 60)
    high = close + 1.0
    low = close - 1.0
    adx = ta.ADX(high, low, close, timeperiod=14, backend="rust")
    assert isinstance(adx, np.ndarray)
    assert adx.shape == close.shape
    assert np.isfinite(adx[30:]).any()


def test_talib_backend_rust_stoch_runs() -> None:
    """Rust backend should run for STOCH and return two arrays."""
    close = np.linspace(10.0, 20.0, 60)
    high = close + 1.0
    low = close - 1.0
    slowk, slowd = ta.STOCH(high, low, close, backend="rust")
    assert isinstance(slowk, np.ndarray)
    assert isinstance(slowd, np.ndarray)
    assert slowk.shape == close.shape
    assert slowd.shape == close.shape
    assert np.isfinite(slowk[15:]).any()
    assert np.isfinite(slowd[20:]).any()


def test_talib_backend_rust_mom_runs() -> None:
    """Rust backend should run for MOM and return ndarray."""
    close = np.linspace(10.0, 20.0, 40)
    mom = ta.MOM(close, timeperiod=10, backend="rust")
    assert isinstance(mom, np.ndarray)
    assert mom.shape == close.shape
    assert np.isfinite(mom[12:]).any()


def test_talib_backend_rust_obv_runs() -> None:
    """Rust backend should run for OBV and return ndarray."""
    close = np.linspace(10.0, 20.0, 40)
    volume = np.linspace(1000.0, 2000.0, 40)
    obv = ta.OBV(close, volume, backend="rust")
    assert isinstance(obv, np.ndarray)
    assert obv.shape == close.shape
    assert np.isfinite(obv).all()


def test_talib_backend_rust_dema_runs() -> None:
    """Rust backend should run for DEMA and return ndarray."""
    close = np.linspace(10.0, 20.0, 60)
    dema = ta.DEMA(close, timeperiod=20, backend="rust")
    assert isinstance(dema, np.ndarray)
    assert dema.shape == close.shape
    assert np.isfinite(dema[40:]).any()


def test_talib_backend_rust_trix_runs() -> None:
    """Rust backend should run for TRIX and return ndarray."""
    close = np.linspace(10.0, 20.0, 120)
    trix = ta.TRIX(close, timeperiod=15, backend="rust")
    assert isinstance(trix, np.ndarray)
    assert trix.shape == close.shape
    assert np.isfinite(trix[50:]).any()


def test_talib_backend_rust_mfi_runs() -> None:
    """Rust backend should run for MFI and return ndarray."""
    close = np.linspace(10.0, 20.0, 60)
    high = close + 1.0
    low = close - 1.0
    volume = np.linspace(1000.0, 3000.0, 60)
    mfi = ta.MFI(high, low, close, volume, timeperiod=14, backend="rust")
    assert isinstance(mfi, np.ndarray)
    assert mfi.shape == close.shape
    assert np.isfinite(mfi[20:]).any()


def test_talib_backend_rust_tema_runs() -> None:
    """Rust backend should run for TEMA and return ndarray."""
    close = np.linspace(10.0, 20.0, 120)
    tema = ta.TEMA(close, timeperiod=20, backend="rust")
    assert isinstance(tema, np.ndarray)
    assert tema.shape == close.shape
    assert np.isfinite(tema[60:]).any()


def test_talib_backend_rust_kama_runs() -> None:
    """Rust backend should run for KAMA and return ndarray."""
    close = np.linspace(10.0, 20.0, 80)
    kama = ta.KAMA(close, timeperiod=10, backend="rust")
    assert isinstance(kama, np.ndarray)
    assert kama.shape == close.shape
    assert np.isfinite(kama[20:]).any()


def test_talib_backend_rust_natr_runs() -> None:
    """Rust backend should run for NATR and return ndarray."""
    close = np.linspace(10.0, 20.0, 60)
    high = close + 1.0
    low = close - 1.0
    natr = ta.NATR(high, low, close, timeperiod=14, backend="rust")
    assert isinstance(natr, np.ndarray)
    assert natr.shape == close.shape
    assert np.isfinite(natr[20:]).any()


def test_talib_backend_rust_sar_runs() -> None:
    """Rust backend should run for SAR and return ndarray."""
    close = np.linspace(10.0, 20.0, 60)
    high = close + 1.0
    low = close - 1.0
    sar = ta.SAR(high, low, acceleration=0.02, maximum=0.2, backend="rust")
    assert isinstance(sar, np.ndarray)
    assert sar.shape == close.shape
    assert np.isfinite(sar[5:]).any()
