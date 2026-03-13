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


def test_talib_wma_period_alias_matches_timeperiod() -> None:
    """WMA should support both timeperiod and period alias."""
    _, _, close = _sample_ohlc(size=60)
    a = ta.WMA(close, timeperiod=10)
    b = ta.WMA(close, period=10)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_talib_adxr_period_alias_matches_timeperiod() -> None:
    """ADXR should support both timeperiod and period alias."""
    high, low, close = _sample_ohlc(size=100)
    a = ta.ADXR(high, low, close, timeperiod=14)
    b = ta.ADXR(high, low, close, period=14)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_talib_cmo_period_alias_matches_timeperiod() -> None:
    """CMO should support both timeperiod and period alias."""
    _, _, close = _sample_ohlc(size=80)
    a = ta.CMO(close, timeperiod=14)
    b = ta.CMO(close, period=14)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_talib_trange_supports_series_output_with_index() -> None:
    """TRANGE as_series should preserve pandas index."""
    high, low, close = _sample_ohlc(size=40)
    trange = ta.TRANGE(high, low, close, as_series=True)
    assert isinstance(trange, pd.Series)
    assert trange.index.equals(close.index)


def test_talib_bop_supports_series_output_with_index() -> None:
    """BOP as_series should preserve pandas index."""
    high, low, close = _sample_ohlc(size=40)
    open_ = close - 0.2
    bop = ta.BOP(open_, high, low, close, as_series=True)
    assert isinstance(bop, pd.Series)
    assert bop.index.equals(close.index)


def test_talib_plus_di_period_alias_matches_timeperiod() -> None:
    """PLUS_DI should support both timeperiod and period alias."""
    high, low, close = _sample_ohlc(size=100)
    a = ta.PLUS_DI(high, low, close, timeperiod=14)
    b = ta.PLUS_DI(high, low, close, period=14)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_talib_minus_di_period_alias_matches_timeperiod() -> None:
    """MINUS_DI should support both timeperiod and period alias."""
    high, low, close = _sample_ohlc(size=100)
    a = ta.MINUS_DI(high, low, close, timeperiod=14)
    b = ta.MINUS_DI(high, low, close, period=14)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_talib_ultosc_supports_series_output_with_index() -> None:
    """ULTOSC as_series should preserve pandas index."""
    high, low, close = _sample_ohlc(size=80)
    ultosc = ta.ULTOSC(high, low, close, as_series=True)
    assert isinstance(ultosc, pd.Series)
    assert ultosc.index.equals(close.index)


def test_talib_apo_has_expected_output_shape() -> None:
    """APO should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    apo = ta.APO(close, fastperiod=12, slowperiod=26)
    assert isinstance(apo, np.ndarray)
    assert apo.shape == close.shape


def test_talib_ppo_has_expected_output_shape() -> None:
    """PPO should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    ppo = ta.PPO(close, fastperiod=12, slowperiod=26)
    assert isinstance(ppo, np.ndarray)
    assert ppo.shape == close.shape


def test_talib_dx_period_alias_matches_timeperiod() -> None:
    """DX should support both timeperiod and period alias."""
    high, low, close = _sample_ohlc(size=100)
    a = ta.DX(high, low, close, timeperiod=14)
    b = ta.DX(high, low, close, period=14)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_talib_aroon_period_alias_matches_timeperiod() -> None:
    """AROON should support both timeperiod and period alias."""
    high, low, _ = _sample_ohlc(size=80)
    down_a, up_a = ta.AROON(high, low, timeperiod=14)
    down_b, up_b = ta.AROON(high, low, period=14)
    assert isinstance(down_a, np.ndarray)
    assert isinstance(up_a, np.ndarray)
    assert isinstance(down_b, np.ndarray)
    assert isinstance(up_b, np.ndarray)
    np.testing.assert_allclose(down_a, down_b, equal_nan=True)
    np.testing.assert_allclose(up_a, up_b, equal_nan=True)


def test_talib_aroonosc_period_alias_matches_timeperiod() -> None:
    """AROONOSC should support both timeperiod and period alias."""
    high, low, _ = _sample_ohlc(size=80)
    a = ta.AROONOSC(high, low, timeperiod=14)
    b = ta.AROONOSC(high, low, period=14)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_talib_ad_supports_series_output_with_index() -> None:
    """AD as_series should preserve pandas index."""
    high, low, close = _sample_ohlc(size=60)
    volume = pd.Series(np.linspace(1000.0, 2000.0, len(close)), index=close.index)
    ad = ta.AD(high, low, close, volume, as_series=True)
    assert isinstance(ad, pd.Series)
    assert ad.index.equals(close.index)


def test_talib_adosc_has_expected_output_shape() -> None:
    """ADOSC should return ndarray with same shape as input."""
    high, low, close = _sample_ohlc(size=80)
    volume = pd.Series(np.linspace(1000.0, 2000.0, len(close)), index=close.index)
    adosc = ta.ADOSC(high, low, close, volume, fastperiod=3, slowperiod=10)
    assert isinstance(adosc, np.ndarray)
    assert adosc.shape == close.shape


def test_talib_trima_period_alias_matches_timeperiod() -> None:
    """TRIMA should support both timeperiod and period alias."""
    _, _, close = _sample_ohlc(size=80)
    a = ta.TRIMA(close, timeperiod=20)
    b = ta.TRIMA(close, period=20)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_talib_stddev_supports_series_output_with_index() -> None:
    """STDDEV as_series should preserve pandas index."""
    _, _, close = _sample_ohlc(size=80)
    stddev = ta.STDDEV(close, timeperiod=20, nbdev=2.0, as_series=True)
    assert isinstance(stddev, pd.Series)
    assert stddev.index.equals(close.index)


def test_talib_var_period_alias_matches_timeperiod() -> None:
    """VAR should support both timeperiod and period alias."""
    _, _, close = _sample_ohlc(size=80)
    a = ta.VAR(close, timeperiod=20, nbdev=1.0)
    b = ta.VAR(close, period=20, nbdev=1.0)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_talib_linearreg_has_expected_output_shape() -> None:
    """LINEARREG should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    line = ta.LINEARREG(close, timeperiod=14)
    assert isinstance(line, np.ndarray)
    assert line.shape == close.shape


def test_talib_linearreg_slope_has_expected_output_shape() -> None:
    """LINEARREG_SLOPE should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    slope = ta.LINEARREG_SLOPE(close, timeperiod=14)
    assert isinstance(slope, np.ndarray)
    assert slope.shape == close.shape


def test_talib_linearreg_intercept_has_expected_output_shape() -> None:
    """LINEARREG_INTERCEPT should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    intercept = ta.LINEARREG_INTERCEPT(close, timeperiod=14)
    assert isinstance(intercept, np.ndarray)
    assert intercept.shape == close.shape


def test_talib_linearreg_angle_period_alias_matches_timeperiod() -> None:
    """LINEARREG_ANGLE should support both timeperiod and period alias."""
    _, _, close = _sample_ohlc(size=80)
    a = ta.LINEARREG_ANGLE(close, timeperiod=14)
    b = ta.LINEARREG_ANGLE(close, period=14)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_talib_tsf_has_expected_output_shape() -> None:
    """TSF should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    tsf = ta.TSF(close, timeperiod=14)
    assert isinstance(tsf, np.ndarray)
    assert tsf.shape == close.shape


def test_talib_correl_supports_series_output_with_index() -> None:
    """CORREL as_series should preserve pandas index."""
    _, _, close = _sample_ohlc(size=80)
    other = close * 0.8 + 1.2
    correl = ta.CORREL(close, other, timeperiod=30, as_series=True)
    assert isinstance(correl, pd.Series)
    assert correl.index.equals(close.index)


def test_talib_beta_period_alias_matches_timeperiod() -> None:
    """BETA should support both timeperiod and period alias."""
    _, _, close = _sample_ohlc(size=80)
    other = close * 0.8 + 1.2
    a = ta.BETA(close, other, timeperiod=20)
    b = ta.BETA(close, other, period=20)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_talib_linearreg_r2_period_alias_matches_timeperiod() -> None:
    """LINEARREG_R2 should support both timeperiod and period alias."""
    _, _, close = _sample_ohlc(size=80)
    a = ta.LINEARREG_R2(close, timeperiod=14)
    b = ta.LINEARREG_R2(close, period=14)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_talib_t3_has_expected_output_shape() -> None:
    """T3 should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    t3 = ta.T3(close, timeperiod=5, vfactor=0.7)
    assert isinstance(t3, np.ndarray)
    assert t3.shape == close.shape


def test_talib_medprice_supports_series_output_with_index() -> None:
    """MEDPRICE as_series should preserve pandas index."""
    high, low, close = _sample_ohlc(size=80)
    med = ta.MEDPRICE(high, low, as_series=True)
    assert isinstance(med, pd.Series)
    assert med.index.equals(close.index)


def test_talib_typprice_has_expected_output_shape() -> None:
    """TYPPRICE should return ndarray with same shape as input."""
    high, low, close = _sample_ohlc(size=80)
    typ = ta.TYPPRICE(high, low, close)
    assert isinstance(typ, np.ndarray)
    assert typ.shape == close.shape


def test_talib_wclprice_has_expected_output_shape() -> None:
    """WCLPRICE should return ndarray with same shape as input."""
    high, low, close = _sample_ohlc(size=80)
    wcl = ta.WCLPRICE(high, low, close)
    assert isinstance(wcl, np.ndarray)
    assert wcl.shape == close.shape


def test_talib_avgprice_supports_series_output_with_index() -> None:
    """AVGPRICE as_series should preserve pandas index."""
    high, low, close = _sample_ohlc(size=80)
    open_ = close - 0.2
    avg = ta.AVGPRICE(open_, high, low, close, as_series=True)
    assert isinstance(avg, pd.Series)
    assert avg.index.equals(close.index)


def test_talib_midpoint_period_alias_matches_timeperiod() -> None:
    """MIDPOINT should support both timeperiod and period alias."""
    _, _, close = _sample_ohlc(size=80)
    a = ta.MIDPOINT(close, timeperiod=14)
    b = ta.MIDPOINT(close, period=14)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_talib_midprice_period_alias_matches_timeperiod() -> None:
    """MIDPRICE should support both timeperiod and period alias."""
    high, low, _ = _sample_ohlc(size=80)
    a = ta.MIDPRICE(high, low, timeperiod=14)
    b = ta.MIDPRICE(high, low, period=14)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_talib_ht_trendline_has_expected_output_shape() -> None:
    """HT_TRENDLINE should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    trend = ta.HT_TRENDLINE(close)
    assert isinstance(trend, np.ndarray)
    assert trend.shape == close.shape


def test_talib_mama_has_expected_output_shape() -> None:
    """MAMA should return ndarray pair with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    mama, fama = ta.MAMA(close, fastlimit=0.5, slowlimit=0.05)
    assert isinstance(mama, np.ndarray)
    assert isinstance(fama, np.ndarray)
    assert mama.shape == close.shape
    assert fama.shape == close.shape


def test_talib_max_period_alias_matches_timeperiod() -> None:
    """MAX should support both timeperiod and period alias."""
    _, _, close = _sample_ohlc(size=80)
    a = ta.MAX(close, timeperiod=14)
    b = ta.MAX(close, period=14)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_talib_min_period_alias_matches_timeperiod() -> None:
    """MIN should support both timeperiod and period alias."""
    _, _, close = _sample_ohlc(size=80)
    a = ta.MIN(close, timeperiod=14)
    b = ta.MIN(close, period=14)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_talib_maxindex_has_expected_output_shape() -> None:
    """MAXINDEX should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.MAXINDEX(close, timeperiod=14)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_minindex_has_expected_output_shape() -> None:
    """MININDEX should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.MININDEX(close, timeperiod=14)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_minmax_returns_pair_shapes() -> None:
    """MINMAX should return ndarray pair with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out_min, out_max = ta.MINMAX(close, timeperiod=14)
    assert isinstance(out_min, np.ndarray)
    assert isinstance(out_max, np.ndarray)
    assert out_min.shape == close.shape
    assert out_max.shape == close.shape


def test_talib_sum_period_alias_matches_timeperiod() -> None:
    """SUM should support both timeperiod and period alias."""
    _, _, close = _sample_ohlc(size=80)
    a = ta.SUM(close, timeperiod=14)
    b = ta.SUM(close, period=14)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_talib_avgdev_has_expected_output_shape() -> None:
    """AVGDEV should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.AVGDEV(close, timeperiod=14)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_range_supports_series_output_with_index() -> None:
    """RANGE as_series should preserve pandas index."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.RANGE(close, timeperiod=14, as_series=True)
    assert isinstance(out, pd.Series)
    assert out.index.equals(close.index)


def test_talib_minmaxindex_returns_pair_shapes() -> None:
    """MINMAXINDEX should return ndarray pair with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out_min_idx, out_max_idx = ta.MINMAXINDEX(close, timeperiod=14)
    assert isinstance(out_min_idx, np.ndarray)
    assert isinstance(out_max_idx, np.ndarray)
    assert out_min_idx.shape == close.shape
    assert out_max_idx.shape == close.shape


def test_talib_rocp_period_alias_matches_timeperiod() -> None:
    """ROCP should support both timeperiod and period alias."""
    _, _, close = _sample_ohlc(size=80)
    a = ta.ROCP(close, timeperiod=10)
    b = ta.ROCP(close, period=10)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_talib_rocr_period_alias_matches_timeperiod() -> None:
    """ROCR should support both timeperiod and period alias."""
    _, _, close = _sample_ohlc(size=80)
    a = ta.ROCR(close, timeperiod=10)
    b = ta.ROCR(close, period=10)
    assert isinstance(a, np.ndarray)
    assert isinstance(b, np.ndarray)
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_talib_rocr100_has_expected_output_shape() -> None:
    """ROCR100 should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.ROCR100(close, timeperiod=10)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_covar_has_expected_output_shape() -> None:
    """COVAR should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    other = close + 0.5
    out = ta.COVAR(close, other, timeperiod=20)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_ln_supports_series_output_with_index() -> None:
    """LN as_series should preserve pandas index."""
    _, _, close = _sample_ohlc(size=80)
    positive = close.abs() + 1.0
    out = ta.LN(positive, as_series=True)
    assert isinstance(out, pd.Series)
    assert out.index.equals(close.index)


def test_talib_log10_has_expected_output_shape() -> None:
    """LOG10 should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    positive = close.abs() + 1.0
    out = ta.LOG10(positive)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_sqrt_has_expected_output_shape() -> None:
    """SQRT should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    positive = close.abs()
    out = ta.SQRT(positive)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_ceil_has_expected_output_shape() -> None:
    """CEIL should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.CEIL(close)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_floor_has_expected_output_shape() -> None:
    """FLOOR should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.FLOOR(close)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_sin_has_expected_output_shape() -> None:
    """SIN should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.SIN(close)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_cos_has_expected_output_shape() -> None:
    """COS should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.COS(close)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_tan_has_expected_output_shape() -> None:
    """TAN should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.TAN(close)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_asin_has_expected_output_shape() -> None:
    """ASIN should return ndarray with same shape as input."""
    values = pd.Series(np.linspace(-1.0, 1.0, 80))
    out = ta.ASIN(values)
    assert isinstance(out, np.ndarray)
    assert out.shape == values.shape


def test_talib_acos_supports_series_output_with_index() -> None:
    """ACOS as_series should preserve pandas index."""
    values = pd.Series(
        np.linspace(-1.0, 1.0, 80),
        index=pd.date_range("2024-01-01", periods=80),
    )
    out = ta.ACOS(values, as_series=True)
    assert isinstance(out, pd.Series)
    assert out.index.equals(values.index)


def test_talib_atan_has_expected_output_shape() -> None:
    """ATAN should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.ATAN(close)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_sinh_has_expected_output_shape() -> None:
    """SINH should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.SINH(close)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_cosh_has_expected_output_shape() -> None:
    """COSH should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.COSH(close)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_tanh_has_expected_output_shape() -> None:
    """TANH should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.TANH(close)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_exp_supports_series_output_with_index() -> None:
    """EXP as_series should preserve pandas index."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.EXP(close, as_series=True)
    assert isinstance(out, pd.Series)
    assert out.index.equals(close.index)


def test_talib_abs_has_expected_output_shape() -> None:
    """ABS should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.ABS(close)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_sign_has_expected_output_shape() -> None:
    """SIGN should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.SIGN(close)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_add_has_expected_output_shape() -> None:
    """ADD should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.ADD(close, close + 1.0)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_sub_has_expected_output_shape() -> None:
    """SUB should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.SUB(close, close + 1.0)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_mult_supports_series_output_with_index() -> None:
    """MULT as_series should preserve pandas index."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.MULT(close, close + 1.0, as_series=True)
    assert isinstance(out, pd.Series)
    assert out.index.equals(close.index)


def test_talib_div_has_expected_output_shape() -> None:
    """DIV should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.DIV(close + 1.0, close + 2.0)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_max2_has_expected_output_shape() -> None:
    """MAX2 should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.MAX2(close, close + 1.0)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_min2_has_expected_output_shape() -> None:
    """MIN2 should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.MIN2(close, close + 1.0)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_clip_has_expected_output_shape() -> None:
    """CLIP should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.CLIP(close, close - 0.5, close + 0.5)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_round_supports_series_output_with_index() -> None:
    """ROUND as_series should preserve pandas index."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.ROUND(close, as_series=True)
    assert isinstance(out, pd.Series)
    assert out.index.equals(close.index)


def test_talib_pow_has_expected_output_shape() -> None:
    """POW should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.POW(close.abs() + 1.0, close.abs() + 0.5)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_mod_has_expected_output_shape() -> None:
    """MOD should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.MOD(close.abs() + 1.0, close.abs() + 0.5)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_clamp01_has_expected_output_shape() -> None:
    """CLAMP01 should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.CLAMP01(close)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_sq_has_expected_output_shape() -> None:
    """SQ should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.SQ(close)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_cube_supports_series_output_with_index() -> None:
    """CUBE as_series should preserve pandas index."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.CUBE(close, as_series=True)
    assert isinstance(out, pd.Series)
    assert out.index.equals(close.index)


def test_talib_recip_has_expected_output_shape() -> None:
    """RECIP should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.RECIP(close.abs() + 1.0)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_inv_sqrt_has_expected_output_shape() -> None:
    """INV_SQRT should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.INV_SQRT(close.abs() + 0.1)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_log1p_has_expected_output_shape() -> None:
    """LOG1P should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.LOG1P(close.abs())
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_expm1_has_expected_output_shape() -> None:
    """EXPM1 should return ndarray with same shape as input."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.EXPM1(close)
    assert isinstance(out, np.ndarray)
    assert out.shape == close.shape


def test_talib_deg2rad_supports_series_output_with_index() -> None:
    """DEG2RAD as_series should preserve pandas index."""
    _, _, close = _sample_ohlc(size=80)
    out = ta.DEG2RAD(close, as_series=True)
    assert isinstance(out, pd.Series)
    assert out.index.equals(close.index)
