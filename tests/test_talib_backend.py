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


def test_talib_backend_rust_wma_runs() -> None:
    """Rust backend should run for WMA and return ndarray."""
    close = np.linspace(10.0, 20.0, 60)
    wma = ta.WMA(close, timeperiod=10, backend="rust")
    assert isinstance(wma, np.ndarray)
    assert wma.shape == close.shape
    assert np.isfinite(wma[20:]).any()


def test_talib_backend_rust_adxr_runs() -> None:
    """Rust backend should run for ADXR and return ndarray."""
    close = np.linspace(10.0, 20.0, 150)
    high = close + 1.0
    low = close - 1.0
    adxr = ta.ADXR(high, low, close, timeperiod=14, backend="rust")
    assert isinstance(adxr, np.ndarray)
    assert adxr.shape == close.shape
    assert np.isfinite(adxr[60:]).any()


def test_talib_backend_rust_cmo_runs() -> None:
    """Rust backend should run for CMO and return ndarray."""
    close = np.linspace(10.0, 20.0, 80) + np.sin(np.linspace(0.0, 10.0, 80))
    cmo = ta.CMO(close, timeperiod=14, backend="rust")
    assert isinstance(cmo, np.ndarray)
    assert cmo.shape == close.shape
    assert np.isfinite(cmo[20:]).any()


def test_talib_backend_rust_trange_runs() -> None:
    """Rust backend should run for TRANGE and return ndarray."""
    close = np.linspace(10.0, 20.0, 60)
    high = close + 1.5
    low = close - 1.0
    trange = ta.TRANGE(high, low, close, backend="rust")
    assert isinstance(trange, np.ndarray)
    assert trange.shape == close.shape
    assert np.isfinite(trange).any()


def test_talib_backend_rust_bop_runs() -> None:
    """Rust backend should run for BOP and return ndarray."""
    close = np.linspace(10.0, 20.0, 60)
    open_ = close - 0.2
    high = np.maximum(open_, close) + 0.8
    low = np.minimum(open_, close) - 0.8
    bop = ta.BOP(open_, high, low, close, backend="rust")
    assert isinstance(bop, np.ndarray)
    assert bop.shape == close.shape
    assert np.isfinite(bop).all()


def test_talib_backend_rust_apo_runs() -> None:
    """Rust backend should run for APO and return ndarray."""
    close = np.linspace(10.0, 20.0, 80)
    apo = ta.APO(close, fastperiod=12, slowperiod=26, backend="rust")
    assert isinstance(apo, np.ndarray)
    assert apo.shape == close.shape
    assert np.isfinite(apo[35:]).any()


def test_talib_backend_rust_ppo_runs() -> None:
    """Rust backend should run for PPO and return ndarray."""
    close = np.linspace(10.0, 20.0, 80)
    ppo = ta.PPO(close, fastperiod=12, slowperiod=26, backend="rust")
    assert isinstance(ppo, np.ndarray)
    assert ppo.shape == close.shape
    assert np.isfinite(ppo[35:]).any()


def test_talib_backend_rust_plus_di_runs() -> None:
    """Rust backend should run for PLUS_DI and return ndarray."""
    close = np.linspace(10.0, 20.0, 100)
    high = close + 1.0
    low = close - 1.0
    plus_di = ta.PLUS_DI(high, low, close, timeperiod=14, backend="rust")
    assert isinstance(plus_di, np.ndarray)
    assert plus_di.shape == close.shape
    assert np.isfinite(plus_di[30:]).any()


def test_talib_backend_rust_minus_di_runs() -> None:
    """Rust backend should run for MINUS_DI and return ndarray."""
    close = np.linspace(20.0, 10.0, 100)
    high = close + 1.0
    low = close - 1.0
    minus_di = ta.MINUS_DI(high, low, close, timeperiod=14, backend="rust")
    assert isinstance(minus_di, np.ndarray)
    assert minus_di.shape == close.shape
    assert np.isfinite(minus_di[30:]).any()


def test_talib_backend_rust_ultosc_runs() -> None:
    """Rust backend should run for ULTOSC and return ndarray."""
    close = np.linspace(10.0, 20.0, 120) + np.sin(np.linspace(0.0, 8.0, 120))
    high = close + 1.0
    low = close - 1.0
    ultosc = ta.ULTOSC(
        high,
        low,
        close,
        timeperiod1=7,
        timeperiod2=14,
        timeperiod3=28,
        backend="rust",
    )
    assert isinstance(ultosc, np.ndarray)
    assert ultosc.shape == close.shape
    assert np.isfinite(ultosc[40:]).any()


def test_talib_backend_rust_dx_runs() -> None:
    """Rust backend should run for DX and return ndarray."""
    close = np.linspace(10.0, 20.0, 100)
    high = close + 1.0
    low = close - 1.0
    dx = ta.DX(high, low, close, timeperiod=14, backend="rust")
    assert isinstance(dx, np.ndarray)
    assert dx.shape == close.shape
    assert np.isfinite(dx[30:]).any()


def test_talib_backend_rust_aroon_runs() -> None:
    """Rust backend should run for AROON and return ndarray pair."""
    close = np.linspace(10.0, 20.0, 80) + np.sin(np.linspace(0.0, 9.0, 80))
    high = close + 1.0
    low = close - 1.0
    aroondown, aroonup = ta.AROON(high, low, timeperiod=14, backend="rust")
    assert isinstance(aroondown, np.ndarray)
    assert isinstance(aroonup, np.ndarray)
    assert aroondown.shape == close.shape
    assert aroonup.shape == close.shape
    assert np.isfinite(aroondown[20:]).any()
    assert np.isfinite(aroonup[20:]).any()


def test_talib_backend_rust_aroonosc_runs() -> None:
    """Rust backend should run for AROONOSC and return ndarray."""
    close = np.linspace(10.0, 20.0, 80) + np.sin(np.linspace(0.0, 9.0, 80))
    high = close + 1.0
    low = close - 1.0
    aroonosc = ta.AROONOSC(high, low, timeperiod=14, backend="rust")
    assert isinstance(aroonosc, np.ndarray)
    assert aroonosc.shape == close.shape
    assert np.isfinite(aroonosc[20:]).any()


def test_talib_backend_rust_ad_runs() -> None:
    """Rust backend should run for AD and return ndarray."""
    close = np.linspace(10.0, 20.0, 80) + np.sin(np.linspace(0.0, 10.0, 80))
    high = close + 1.0
    low = close - 1.0
    volume = np.linspace(1000.0, 3000.0, 80)
    ad = ta.AD(high, low, close, volume, backend="rust")
    assert isinstance(ad, np.ndarray)
    assert ad.shape == close.shape
    assert np.isfinite(ad).all()


def test_talib_backend_rust_adosc_runs() -> None:
    """Rust backend should run for ADOSC and return ndarray."""
    close = np.linspace(10.0, 20.0, 100) + np.sin(np.linspace(0.0, 10.0, 100))
    high = close + 1.0
    low = close - 1.0
    volume = np.linspace(1000.0, 3000.0, 100)
    adosc = ta.ADOSC(
        high,
        low,
        close,
        volume,
        fastperiod=3,
        slowperiod=10,
        backend="rust",
    )
    assert isinstance(adosc, np.ndarray)
    assert adosc.shape == close.shape
    assert np.isfinite(adosc[20:]).any()


def test_talib_backend_rust_trima_runs() -> None:
    """Rust backend should run for TRIMA and return ndarray."""
    close = np.linspace(10.0, 20.0, 90)
    trima = ta.TRIMA(close, timeperiod=20, backend="rust")
    assert isinstance(trima, np.ndarray)
    assert trima.shape == close.shape
    assert np.isfinite(trima[30:]).any()


def test_talib_backend_rust_stddev_runs() -> None:
    """Rust backend should run for STDDEV and return ndarray."""
    close = np.linspace(10.0, 20.0, 90) + np.sin(np.linspace(0.0, 8.0, 90))
    stddev = ta.STDDEV(close, timeperiod=20, nbdev=2.0, backend="rust")
    assert isinstance(stddev, np.ndarray)
    assert stddev.shape == close.shape
    assert np.isfinite(stddev[30:]).any()


def test_talib_backend_rust_var_runs() -> None:
    """Rust backend should run for VAR and return ndarray."""
    close = np.linspace(10.0, 20.0, 90) + np.sin(np.linspace(0.0, 8.0, 90))
    variance = ta.VAR(close, timeperiod=20, nbdev=1.0, backend="rust")
    assert isinstance(variance, np.ndarray)
    assert variance.shape == close.shape
    assert np.isfinite(variance[30:]).any()


def test_talib_backend_rust_linearreg_runs() -> None:
    """Rust backend should run for LINEARREG and return ndarray."""
    close = np.linspace(10.0, 20.0, 90) + np.sin(np.linspace(0.0, 8.0, 90))
    line = ta.LINEARREG(close, timeperiod=14, backend="rust")
    assert isinstance(line, np.ndarray)
    assert line.shape == close.shape
    assert np.isfinite(line[20:]).any()


def test_talib_backend_rust_linearreg_slope_runs() -> None:
    """Rust backend should run for LINEARREG_SLOPE and return ndarray."""
    close = np.linspace(10.0, 20.0, 90) + np.sin(np.linspace(0.0, 8.0, 90))
    slope = ta.LINEARREG_SLOPE(close, timeperiod=14, backend="rust")
    assert isinstance(slope, np.ndarray)
    assert slope.shape == close.shape
    assert np.isfinite(slope[20:]).any()


def test_talib_backend_rust_linearreg_intercept_runs() -> None:
    """Rust backend should run for LINEARREG_INTERCEPT and return ndarray."""
    close = np.linspace(10.0, 20.0, 90) + np.sin(np.linspace(0.0, 8.0, 90))
    intercept = ta.LINEARREG_INTERCEPT(close, timeperiod=14, backend="rust")
    assert isinstance(intercept, np.ndarray)
    assert intercept.shape == close.shape
    assert np.isfinite(intercept[20:]).any()


def test_talib_backend_rust_linearreg_angle_runs() -> None:
    """Rust backend should run for LINEARREG_ANGLE and return ndarray."""
    close = np.linspace(10.0, 20.0, 90) + np.sin(np.linspace(0.0, 8.0, 90))
    angle = ta.LINEARREG_ANGLE(close, timeperiod=14, backend="rust")
    assert isinstance(angle, np.ndarray)
    assert angle.shape == close.shape
    assert np.isfinite(angle[20:]).any()


def test_talib_backend_rust_tsf_runs() -> None:
    """Rust backend should run for TSF and return ndarray."""
    close = np.linspace(10.0, 20.0, 90) + np.sin(np.linspace(0.0, 8.0, 90))
    tsf = ta.TSF(close, timeperiod=14, backend="rust")
    assert isinstance(tsf, np.ndarray)
    assert tsf.shape == close.shape
    assert np.isfinite(tsf[20:]).any()


def test_talib_backend_rust_correl_runs() -> None:
    """Rust backend should run for CORREL and return ndarray."""
    real0 = np.linspace(10.0, 20.0, 100) + np.sin(np.linspace(0.0, 8.0, 100))
    real1 = np.linspace(8.0, 18.0, 100) + np.sin(np.linspace(0.5, 8.5, 100))
    correl = ta.CORREL(real0, real1, timeperiod=30, backend="rust")
    assert isinstance(correl, np.ndarray)
    assert correl.shape == real0.shape
    assert np.isfinite(correl[40:]).any()


def test_talib_backend_rust_beta_runs() -> None:
    """Rust backend should run for BETA and return ndarray."""
    real0 = np.linspace(10.0, 20.0, 100) + np.sin(np.linspace(0.0, 8.0, 100))
    real1 = np.linspace(8.0, 18.0, 100) + np.sin(np.linspace(0.5, 8.5, 100))
    beta = ta.BETA(real0, real1, timeperiod=20, backend="rust")
    assert isinstance(beta, np.ndarray)
    assert beta.shape == real0.shape
    assert np.isfinite(beta[30:]).any()


def test_talib_backend_rust_linearreg_r2_runs() -> None:
    """Rust backend should run for LINEARREG_R2 and return ndarray."""
    close = np.linspace(10.0, 20.0, 100) + np.sin(np.linspace(0.0, 8.0, 100))
    r2 = ta.LINEARREG_R2(close, timeperiod=14, backend="rust")
    assert isinstance(r2, np.ndarray)
    assert r2.shape == close.shape
    assert np.isfinite(r2[20:]).any()


def test_talib_backend_rust_t3_runs() -> None:
    """Rust backend should run for T3 and return ndarray."""
    close = np.linspace(10.0, 20.0, 100)
    t3 = ta.T3(close, timeperiod=5, vfactor=0.7, backend="rust")
    assert isinstance(t3, np.ndarray)
    assert t3.shape == close.shape
    assert np.isfinite(t3[20:]).any()


def test_talib_backend_rust_medprice_runs() -> None:
    """Rust backend should run for MEDPRICE and return ndarray."""
    close = np.linspace(10.0, 20.0, 80)
    high = close + 1.0
    low = close - 1.0
    medprice = ta.MEDPRICE(high, low, backend="rust")
    assert isinstance(medprice, np.ndarray)
    assert medprice.shape == close.shape
    assert np.isfinite(medprice).all()


def test_talib_backend_rust_typprice_runs() -> None:
    """Rust backend should run for TYPPRICE and return ndarray."""
    close = np.linspace(10.0, 20.0, 80)
    high = close + 1.0
    low = close - 1.0
    typprice = ta.TYPPRICE(high, low, close, backend="rust")
    assert isinstance(typprice, np.ndarray)
    assert typprice.shape == close.shape
    assert np.isfinite(typprice).all()


def test_talib_backend_rust_wclprice_runs() -> None:
    """Rust backend should run for WCLPRICE and return ndarray."""
    close = np.linspace(10.0, 20.0, 80)
    high = close + 1.0
    low = close - 1.0
    wclprice = ta.WCLPRICE(high, low, close, backend="rust")
    assert isinstance(wclprice, np.ndarray)
    assert wclprice.shape == close.shape
    assert np.isfinite(wclprice).all()


def test_talib_backend_rust_avgprice_runs() -> None:
    """Rust backend should run for AVGPRICE and return ndarray."""
    close = np.linspace(10.0, 20.0, 80)
    open_ = close - 0.2
    high = close + 1.0
    low = close - 1.0
    avgprice = ta.AVGPRICE(open_, high, low, close, backend="rust")
    assert isinstance(avgprice, np.ndarray)
    assert avgprice.shape == close.shape
    assert np.isfinite(avgprice).all()


def test_talib_backend_rust_midpoint_runs() -> None:
    """Rust backend should run for MIDPOINT and return ndarray."""
    close = np.linspace(10.0, 20.0, 80) + np.sin(np.linspace(0.0, 8.0, 80))
    midpoint = ta.MIDPOINT(close, timeperiod=14, backend="rust")
    assert isinstance(midpoint, np.ndarray)
    assert midpoint.shape == close.shape
    assert np.isfinite(midpoint[20:]).any()


def test_talib_backend_rust_midprice_runs() -> None:
    """Rust backend should run for MIDPRICE and return ndarray."""
    close = np.linspace(10.0, 20.0, 80)
    high = close + 1.0
    low = close - 1.0
    midprice = ta.MIDPRICE(high, low, timeperiod=14, backend="rust")
    assert isinstance(midprice, np.ndarray)
    assert midprice.shape == close.shape
    assert np.isfinite(midprice[20:]).any()


def test_talib_backend_rust_ht_trendline_runs() -> None:
    """Rust backend should run for HT_TRENDLINE and return ndarray."""
    close = np.linspace(10.0, 20.0, 80) + np.sin(np.linspace(0.0, 8.0, 80))
    trend = ta.HT_TRENDLINE(close, backend="rust")
    assert isinstance(trend, np.ndarray)
    assert trend.shape == close.shape
    assert np.isfinite(trend[10:]).any()


def test_talib_backend_rust_mama_runs() -> None:
    """Rust backend should run for MAMA and return ndarray pair."""
    close = np.linspace(10.0, 20.0, 80) + np.sin(np.linspace(0.0, 8.0, 80))
    mama, fama = ta.MAMA(close, fastlimit=0.5, slowlimit=0.05, backend="rust")
    assert isinstance(mama, np.ndarray)
    assert isinstance(fama, np.ndarray)
    assert mama.shape == close.shape
    assert fama.shape == close.shape
    assert np.isfinite(mama[10:]).any()
    assert np.isfinite(fama[10:]).any()


def test_talib_backend_rust_max_runs() -> None:
    """Rust backend should run for MAX and return ndarray."""
    close = np.linspace(10.0, 20.0, 90) + np.sin(np.linspace(0.0, 8.0, 90))
    out = ta.MAX(close, timeperiod=14, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out[20:]).any()


def test_talib_backend_rust_min_runs() -> None:
    """Rust backend should run for MIN and return ndarray."""
    close = np.linspace(10.0, 20.0, 90) + np.sin(np.linspace(0.0, 8.0, 90))
    out = ta.MIN(close, timeperiod=14, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out[20:]).any()


def test_talib_backend_rust_maxindex_runs() -> None:
    """Rust backend should run for MAXINDEX and return ndarray."""
    close = np.linspace(10.0, 20.0, 90) + np.sin(np.linspace(0.0, 8.0, 90))
    out = ta.MAXINDEX(close, timeperiod=14, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out[20:]).any()


def test_talib_backend_rust_minindex_runs() -> None:
    """Rust backend should run for MININDEX and return ndarray."""
    close = np.linspace(10.0, 20.0, 90) + np.sin(np.linspace(0.0, 8.0, 90))
    out = ta.MININDEX(close, timeperiod=14, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out[20:]).any()


def test_talib_backend_rust_minmax_runs() -> None:
    """Rust backend should run for MINMAX and return ndarray pair."""
    close = np.linspace(10.0, 20.0, 90) + np.sin(np.linspace(0.0, 8.0, 90))
    out_min, out_max = ta.MINMAX(close, timeperiod=14, backend="rust")
    assert isinstance(out_min, np.ndarray)
    assert isinstance(out_max, np.ndarray)
    assert out_min.shape == close.shape
    assert out_max.shape == close.shape
    assert np.isfinite(out_min[20:]).any()
    assert np.isfinite(out_max[20:]).any()


def test_talib_backend_rust_sum_runs() -> None:
    """Rust backend should run for SUM and return ndarray."""
    close = np.linspace(10.0, 20.0, 90) + np.sin(np.linspace(0.0, 8.0, 90))
    out = ta.SUM(close, timeperiod=14, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out[20:]).any()


def test_talib_backend_rust_avgdev_runs() -> None:
    """Rust backend should run for AVGDEV and return ndarray."""
    close = np.linspace(10.0, 20.0, 90) + np.sin(np.linspace(0.0, 8.0, 90))
    out = ta.AVGDEV(close, timeperiod=14, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out[20:]).any()


def test_talib_backend_rust_range_runs() -> None:
    """Rust backend should run for RANGE and return ndarray."""
    close = np.linspace(10.0, 20.0, 90) + np.sin(np.linspace(0.0, 8.0, 90))
    out = ta.RANGE(close, timeperiod=14, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out[20:]).any()


def test_talib_backend_rust_minmaxindex_runs() -> None:
    """Rust backend should run for MINMAXINDEX and return ndarray pair."""
    close = np.linspace(10.0, 20.0, 90) + np.sin(np.linspace(0.0, 8.0, 90))
    out_min_idx, out_max_idx = ta.MINMAXINDEX(close, timeperiod=14, backend="rust")
    assert isinstance(out_min_idx, np.ndarray)
    assert isinstance(out_max_idx, np.ndarray)
    assert out_min_idx.shape == close.shape
    assert out_max_idx.shape == close.shape
    assert np.isfinite(out_min_idx[20:]).any()
    assert np.isfinite(out_max_idx[20:]).any()


def test_talib_backend_rust_rocp_runs() -> None:
    """Rust backend should run for ROCP and return ndarray."""
    close = np.linspace(10.0, 20.0, 90) + np.sin(np.linspace(0.0, 8.0, 90))
    out = ta.ROCP(close, timeperiod=10, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out[20:]).any()


def test_talib_backend_rust_rocr_runs() -> None:
    """Rust backend should run for ROCR and return ndarray."""
    close = np.linspace(10.0, 20.0, 90) + np.sin(np.linspace(0.0, 8.0, 90))
    out = ta.ROCR(close, timeperiod=10, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out[20:]).any()


def test_talib_backend_rust_rocr100_runs() -> None:
    """Rust backend should run for ROCR100 and return ndarray."""
    close = np.linspace(10.0, 20.0, 90) + np.sin(np.linspace(0.0, 8.0, 90))
    out = ta.ROCR100(close, timeperiod=10, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out[20:]).any()


def test_talib_backend_rust_covar_runs() -> None:
    """Rust backend should run for COVAR and return ndarray."""
    real0 = np.linspace(10.0, 20.0, 90) + np.sin(np.linspace(0.0, 8.0, 90))
    real1 = np.linspace(9.0, 19.0, 90) + np.sin(np.linspace(0.5, 8.5, 90))
    out = ta.COVAR(real0, real1, timeperiod=20, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == real0.shape
    assert np.isfinite(out[30:]).any()


def test_talib_backend_rust_ln_runs() -> None:
    """Rust backend should run for LN and return ndarray."""
    close = np.linspace(1.0, 20.0, 90)
    out = ta.LN(close, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_log10_runs() -> None:
    """Rust backend should run for LOG10 and return ndarray."""
    close = np.linspace(1.0, 20.0, 90)
    out = ta.LOG10(close, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_sqrt_runs() -> None:
    """Rust backend should run for SQRT and return ndarray."""
    close = np.linspace(0.0, 20.0, 90)
    out = ta.SQRT(close, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_ceil_runs() -> None:
    """Rust backend should run for CEIL and return ndarray."""
    close = np.linspace(10.1, 20.9, 90)
    out = ta.CEIL(close, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_floor_runs() -> None:
    """Rust backend should run for FLOOR and return ndarray."""
    close = np.linspace(10.1, 20.9, 90)
    out = ta.FLOOR(close, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_sin_runs() -> None:
    """Rust backend should run for SIN and return ndarray."""
    close = np.linspace(-1.0, 1.0, 90)
    out = ta.SIN(close, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_cos_runs() -> None:
    """Rust backend should run for COS and return ndarray."""
    close = np.linspace(-1.0, 1.0, 90)
    out = ta.COS(close, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_tan_runs() -> None:
    """Rust backend should run for TAN and return ndarray."""
    close = np.linspace(-0.7, 0.7, 90)
    out = ta.TAN(close, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_asin_runs() -> None:
    """Rust backend should run for ASIN and return ndarray."""
    close = np.linspace(-1.0, 1.0, 90)
    out = ta.ASIN(close, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_acos_runs() -> None:
    """Rust backend should run for ACOS and return ndarray."""
    close = np.linspace(-1.0, 1.0, 90)
    out = ta.ACOS(close, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_atan_runs() -> None:
    """Rust backend should run for ATAN and return ndarray."""
    close = np.linspace(-2.0, 2.0, 90)
    out = ta.ATAN(close, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_sinh_runs() -> None:
    """Rust backend should run for SINH and return ndarray."""
    close = np.linspace(-2.0, 2.0, 90)
    out = ta.SINH(close, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_cosh_runs() -> None:
    """Rust backend should run for COSH and return ndarray."""
    close = np.linspace(-2.0, 2.0, 90)
    out = ta.COSH(close, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_tanh_runs() -> None:
    """Rust backend should run for TANH and return ndarray."""
    close = np.linspace(-2.0, 2.0, 90)
    out = ta.TANH(close, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_exp_runs() -> None:
    """Rust backend should run for EXP and return ndarray."""
    close = np.linspace(-2.0, 2.0, 90)
    out = ta.EXP(close, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_abs_runs() -> None:
    """Rust backend should run for ABS and return ndarray."""
    close = np.linspace(-2.0, 2.0, 90)
    out = ta.ABS(close, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_sign_runs() -> None:
    """Rust backend should run for SIGN and return ndarray."""
    close = np.linspace(-2.0, 2.0, 90)
    out = ta.SIGN(close, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_add_runs() -> None:
    """Rust backend should run for ADD and return ndarray."""
    left = np.linspace(1.0, 2.0, 90)
    right = np.linspace(2.0, 3.0, 90)
    out = ta.ADD(left, right, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == left.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_sub_runs() -> None:
    """Rust backend should run for SUB and return ndarray."""
    left = np.linspace(1.0, 2.0, 90)
    right = np.linspace(2.0, 3.0, 90)
    out = ta.SUB(left, right, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == left.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_mult_runs() -> None:
    """Rust backend should run for MULT and return ndarray."""
    left = np.linspace(1.0, 2.0, 90)
    right = np.linspace(2.0, 3.0, 90)
    out = ta.MULT(left, right, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == left.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_div_runs() -> None:
    """Rust backend should run for DIV and return ndarray."""
    left = np.linspace(1.0, 2.0, 90)
    right = np.linspace(2.0, 3.0, 90)
    out = ta.DIV(left, right, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == left.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_max2_runs() -> None:
    """Rust backend should run for MAX2 and return ndarray."""
    left = np.linspace(1.0, 2.0, 90)
    right = np.linspace(2.0, 3.0, 90)
    out = ta.MAX2(left, right, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == left.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_min2_runs() -> None:
    """Rust backend should run for MIN2 and return ndarray."""
    left = np.linspace(1.0, 2.0, 90)
    right = np.linspace(2.0, 3.0, 90)
    out = ta.MIN2(left, right, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == left.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_clip_runs() -> None:
    """Rust backend should run for CLIP and return ndarray."""
    values = np.linspace(-2.0, 2.0, 90)
    lo = np.full(90, -1.0)
    hi = np.full(90, 1.0)
    out = ta.CLIP(values, lo, hi, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == values.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_round_runs() -> None:
    """Rust backend should run for ROUND and return ndarray."""
    values = np.linspace(-2.0, 2.0, 90)
    out = ta.ROUND(values, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == values.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_pow_runs() -> None:
    """Rust backend should run for POW and return ndarray."""
    left = np.linspace(1.0, 2.0, 90)
    right = np.linspace(1.0, 3.0, 90)
    out = ta.POW(left, right, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == left.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_mod_runs() -> None:
    """Rust backend should run for MOD and return ndarray."""
    left = np.linspace(1.0, 10.0, 90)
    right = np.linspace(1.0, 3.0, 90)
    out = ta.MOD(left, right, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == left.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_clamp01_runs() -> None:
    """Rust backend should run for CLAMP01 and return ndarray."""
    values = np.linspace(-2.0, 2.0, 90)
    out = ta.CLAMP01(values, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == values.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_sq_runs() -> None:
    """Rust backend should run for SQ and return ndarray."""
    values = np.linspace(-2.0, 2.0, 90)
    out = ta.SQ(values, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == values.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_cube_runs() -> None:
    """Rust backend should run for CUBE and return ndarray."""
    values = np.linspace(-2.0, 2.0, 90)
    out = ta.CUBE(values, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == values.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_recip_runs() -> None:
    """Rust backend should run for RECIP and return ndarray."""
    values = np.linspace(1.0, 2.0, 90)
    out = ta.RECIP(values, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == values.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_inv_sqrt_runs() -> None:
    """Rust backend should run for INV_SQRT and return ndarray."""
    values = np.linspace(0.1, 2.0, 90)
    out = ta.INV_SQRT(values, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == values.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_log1p_runs() -> None:
    """Rust backend should run for LOG1P and return ndarray."""
    values = np.linspace(0.0, 2.0, 90)
    out = ta.LOG1P(values, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == values.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_expm1_runs() -> None:
    """Rust backend should run for EXPM1 and return ndarray."""
    values = np.linspace(-1.0, 1.0, 90)
    out = ta.EXPM1(values, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == values.shape
    assert np.isfinite(out).all()


def test_talib_backend_rust_deg2rad_runs() -> None:
    """Rust backend should run for DEG2RAD and return ndarray."""
    values = np.linspace(-180.0, 180.0, 90)
    out = ta.DEG2RAD(values, backend="rust")
    assert isinstance(out, np.ndarray)
    assert out.shape == values.shape
    assert np.isfinite(out).all()
