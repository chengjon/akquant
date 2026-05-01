from __future__ import annotations

import pickle

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Indicator incremental update tests
# ---------------------------------------------------------------------------


class TestEMAIncremental:
    """EMA incremental update tests."""

    def test_ema_converges(self) -> None:
        """EMA converges to constant input."""
        from akquant.indicator import EMA

        ema = EMA(5)
        for _ in range(20):
            ema.update(100.0)
        assert ema.value == pytest.approx(100.0, abs=0.01)

    def test_ema_first_value(self) -> None:
        """First update returns the input value."""
        from akquant.indicator import EMA

        ema = EMA(10)
        assert ema.update(42.0) == pytest.approx(42.0)

    def test_ema_batch_vs_incremental(self) -> None:
        """Batch and incremental results agree on last value."""
        from akquant.indicator import EMA

        prices = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]
        ema_inc = EMA(3)
        for p in prices:
            last = ema_inc.update(float(p))

        df = pd.DataFrame({"close": prices})
        ema_batch = EMA(3)
        series = ema_batch(df, "SYM")
        assert last == pytest.approx(series.iloc[-1], abs=0.01)

    def test_ema_pickle_roundtrip(self) -> None:
        """EMA survives pickle roundtrip."""
        from akquant.indicator import EMA

        ema = EMA(5)
        ema.update(10.0)
        ema.update(11.0)
        data = pickle.dumps(ema)
        ema2 = pickle.loads(data)
        assert ema2.value == pytest.approx(ema.value)


class TestRSIIncremental:
    """RSI incremental update tests."""

    def test_rsi_all_up_is_high(self) -> None:
        """Monotonically increasing prices give high RSI."""
        from akquant.indicator import RSI

        rsi = RSI(14)
        for i in range(20):
            rsi.update(float(100 + i))
        assert rsi.value > 70

    def test_rsi_all_down_is_low(self) -> None:
        """Monotonically decreasing prices give low RSI."""
        from akquant.indicator import RSI

        rsi = RSI(14)
        for i in range(20):
            rsi.update(float(100 - i))
        assert rsi.value < 30

    def test_rsi_pickle_roundtrip(self) -> None:
        """RSI survives pickle roundtrip."""
        from akquant.indicator import RSI

        rsi = RSI(14)
        for i in range(20):
            rsi.update(float(100 + i))
        data = pickle.dumps(rsi)
        rsi2 = pickle.loads(data)
        assert rsi2.value == pytest.approx(rsi.value)


class TestMACDIncremental:
    """MACD incremental update tests."""

    def test_macd_returns_line(self) -> None:
        """MACD update returns the macd line value."""
        from akquant.indicator import MACD

        macd = MACD()
        np.random.seed(42)
        for p in 100 + np.cumsum(np.random.randn(30) * 0.5):
            val = macd.update(float(p))
        assert isinstance(val, float)
        assert not np.isnan(val)

    def test_macd_has_histogram(self) -> None:
        """MACD histogram property is populated."""
        from akquant.indicator import MACD

        macd = MACD()
        for p in [100 + i * 0.5 for i in range(30)]:
            macd.update(p)
        assert isinstance(macd.histogram, float)

    def test_macd_pickle_roundtrip(self) -> None:
        """MACD survives pickle roundtrip."""
        from akquant.indicator import MACD

        macd = MACD()
        for p in [100 + i * 0.5 for i in range(30)]:
            macd.update(p)
        data = pickle.dumps(macd)
        macd2 = pickle.loads(data)
        assert macd2.value == pytest.approx(macd.value)


# ---------------------------------------------------------------------------
# Sizer tests
# ---------------------------------------------------------------------------


class TestATRSizer:
    """ATRSizer tests."""

    def test_with_set_atr(self) -> None:
        """Size respects manually set ATR."""
        from akquant.sizer import ATRSizer

        sizer = ATRSizer(risk_per_trade=0.02)
        sizer.set_atr("TEST", 2.0)
        size = sizer.get_size(100.0, 100000.0, None, "TEST")
        assert size == int(100000 * 0.02 / 2.0)

    def test_zero_atr_returns_zero(self) -> None:
        """Zero ATR returns zero size."""
        from akquant.sizer import ATRSizer

        sizer = ATRSizer()
        sizer.set_atr("TEST", 0.0)
        assert sizer.get_size(100.0, 100000.0, None, "TEST") == 0.0


class TestKellySizer:
    """KellySizer tests."""

    def test_positive_edge(self) -> None:
        """Positive expected value gives positive size."""
        from akquant.sizer import KellySizer

        sizer = KellySizer(win_rate=0.6, avg_win=2.0, avg_loss=1.0, fraction=1.0)
        size = sizer.get_size(50.0, 100000.0, None, "TEST")
        assert size > 0

    def test_negative_edge_returns_zero(self) -> None:
        """Negative expected value returns zero."""
        from akquant.sizer import KellySizer

        sizer = KellySizer(win_rate=0.3, avg_win=1.0, avg_loss=2.0)
        assert sizer.get_size(50.0, 100000.0, None, "TEST") == 0.0


class TestRiskParitySizer:
    """RiskParitySizer tests."""

    def test_basic(self) -> None:
        """Basic risk parity sizing."""
        from akquant.sizer import RiskParitySizer

        sizer = RiskParitySizer(total_risk=0.02, volatility={"TEST": 0.2})
        size = sizer.get_size(100.0, 100000.0, None, "TEST")
        assert size == int(100000 * 0.02 / (100 * 0.2))

    def test_unknown_symbol_uses_default(self) -> None:
        """Unknown symbol uses default volatility."""
        from akquant.sizer import RiskParitySizer

        sizer = RiskParitySizer(total_risk=0.02)
        size = sizer.get_size(100.0, 100000.0, None, "UNKNOWN")
        assert size > 0


class TestEqualWeightSizer:
    """EqualWeightSizer tests."""

    def test_single_instrument(self) -> None:
        """Single instrument gets all cash."""
        from akquant.sizer import EqualWeightSizer

        sizer = EqualWeightSizer(n_instruments=1)
        assert sizer.get_size(100.0, 100000.0, None, "TEST") == 1000

    def test_multiple_instruments(self) -> None:
        """Multiple instruments split cash."""
        from akquant.sizer import EqualWeightSizer

        sizer = EqualWeightSizer(n_instruments=4)
        assert sizer.get_size(100.0, 100000.0, None, "TEST") == 250


# ---------------------------------------------------------------------------
# ML adapter tests (mock-based, no actual lightgbm/xgboost needed)
# ---------------------------------------------------------------------------


class TestLightGBMAdapterInit:
    """LightGBMAdapter initialization tests."""

    def test_default_params(self) -> None:
        """Default parameters are set."""
        from akquant.ml.model import LightGBMAdapter

        adapter = LightGBMAdapter()
        assert adapter.params["objective"] == "regression"
        assert adapter.num_boost_round == 100


class TestXGBoostAdapterInit:
    """XGBoostAdapter initialization tests."""

    def test_default_params(self) -> None:
        """Default parameters are set."""
        from akquant.ml.model import XGBoostAdapter

        adapter = XGBoostAdapter()
        assert adapter.params["objective"] == "reg:squarederror"
        assert adapter.num_boost_round == 100
