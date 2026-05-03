from __future__ import annotations

import pandas as pd
from akquant.talib import (
    CDL_3BLACKCROWS,
    CDL_3WHITESOLDIERS,
    CDL_ENGULFING,
    CDL_EVENINGSTAR,
    CDL_HARAMI,
    CDL_MORNINGSTAR,
    CDL_SHOOTINGSTAR,
    CDLDARKCLOUDCOVER,
    CDLDOJI,
    CDLHAMMER,
    CDLHANGINGMAN,
    CDLMARUBOZU,
    CDLPIERCING,
    CDLRISEFALL3METHODS,
    CDLSPINNINGTOP,
    CDLTHRUSTING,
)


def _s(**kwargs: list[float]) -> dict[str, pd.Series]:
    """Build Series dict from OHLC lists."""
    return {k: pd.Series(v) for k, v in kwargs.items()}


class TestCDLDOJI:
    """Doji pattern: body <= 10% of range."""

    def test_doji_detected(self) -> None:
        """Doji is detected when body is very small."""
        d = _s(
            open=[10.0, 10.0],
            high=[11.0, 10.5],
            low=[9.0, 9.5],
            close=[10.5, 10.02],
        )
        result = CDLDOJI(d["open"], d["high"], d["low"], d["close"])
        assert len(result) == 2

    def test_not_doji(self) -> None:
        """Large body is not a doji."""
        d = _s(open=[10.0], high=[11.0], low=[9.0], close=[10.8])
        result = CDLDOJI(d["open"], d["high"], d["low"], d["close"])
        assert result[0] == 0.0


class TestCDLHAMMER:
    """Hammer: downtrend + small body + long lower shadow."""

    def test_hammer_returns_series(self) -> None:
        """Hammer returns correct length."""
        d = _s(
            open=[10.0, 9.5, 9.0],
            high=[10.5, 9.6, 9.1],
            low=[9.0, 8.0, 8.5],
            close=[9.5, 9.0, 8.9],
        )
        result = CDLHAMMER(d["open"], d["high"], d["low"], d["close"])
        assert len(result) == 3


class TestCDLENGULFING:
    """Engulfing: current body engulfs prior opposite body."""

    def test_bullish_engulfing(self) -> None:
        """Bullish engulfing is detected."""
        d = _s(
            open=[10.0, 9.0],
            high=[10.5, 11.0],
            low=[9.0, 8.8],
            close=[9.2, 10.5],
        )
        result = CDL_ENGULFING(d["open"], d["high"], d["low"], d["close"])
        assert len(result) == 2
        assert result[1] == 100.0

    def test_bearish_engulfing(self) -> None:
        """Bearish engulfing is detected."""
        d = _s(
            open=[9.0, 10.5],
            high=[11.0, 10.5],
            low=[8.8, 9.0],
            close=[10.5, 9.0],
        )
        result = CDL_ENGULFING(d["open"], d["high"], d["low"], d["close"])
        assert result[1] == -100.0


class TestCDLHARAMI:
    """Harami: current body inside prior body."""

    def test_harami_returns_series(self) -> None:
        """Harami returns correct length."""
        d = _s(
            open=[8.0, 10.0],
            high=[11.0, 10.5],
            low=[9.0, 9.5],
            close=[10.5, 10.2],
        )
        result = CDL_HARAMI(d["open"], d["high"], d["low"], d["close"])
        assert len(result) == 2


class TestCDLMorningStar:
    """Morning Star: bearish + small star + bullish reversal."""

    def test_morning_star_returns_series(self) -> None:
        """Morning star returns correct length."""
        d = _s(
            open=[12.0, 10.0, 9.5],
            high=[12.5, 10.2, 11.0],
            low=[10.0, 9.3, 9.4],
            close=[10.1, 9.5, 10.8],
        )
        result = CDL_MORNINGSTAR(d["open"], d["high"], d["low"], d["close"])
        assert len(result) == 3


class TestCDLEVENINGSTAR:
    """Evening Star: bullish + small star + bearish reversal."""

    def test_evening_star_returns_series(self) -> None:
        """Evening star returns correct length."""
        d = _s(
            open=[9.0, 10.5, 10.2],
            high=[11.0, 10.8, 10.3],
            low=[8.8, 10.0, 9.0],
            close=[10.5, 10.2, 9.2],
        )
        result = CDL_EVENINGSTAR(d["open"], d["high"], d["low"], d["close"])
        assert len(result) == 3


class TestCDL3BLACKCROWS:
    """Three Black Crows: 3 consecutive bearish bars."""

    def test_returns_series(self) -> None:
        """Three black crows returns correct length."""
        d = _s(
            open=[12.0, 11.5, 11.0],
            high=[12.2, 11.6, 11.1],
            low=[11.3, 10.8, 10.3],
            close=[11.4, 10.9, 10.4],
        )
        result = CDL_3BLACKCROWS(d["open"], d["high"], d["low"], d["close"])
        assert len(result) == 3


class TestCDL3WHITESOLDIERS:
    """Three White Soldiers: 3 consecutive bullish bars."""

    def test_returns_series(self) -> None:
        """Three white soldiers returns correct length."""
        d = _s(
            open=[9.0, 9.5, 10.0],
            high=[9.8, 10.3, 10.8],
            low=[8.9, 9.4, 9.9],
            close=[9.6, 10.1, 10.6],
        )
        result = CDL_3WHITESOLDIERS(d["open"], d["high"], d["low"], d["close"])
        assert len(result) == 3


class TestCDLSHOOTINGSTAR:
    """Shooting Star: uptrend + small body + long upper shadow."""

    def test_returns_series(self) -> None:
        """Shooting star returns correct length."""
        d = _s(
            open=[9.0, 10.5],
            high=[10.5, 11.5],
            low=[8.9, 10.4],
            close=[10.4, 10.6],
        )
        result = CDL_SHOOTINGSTAR(d["open"], d["high"], d["low"], d["close"])
        assert len(result) == 2


class TestCDLHANGINGMAN:
    """Hanging Man: uptrend + small body + long lower shadow."""

    def test_returns_series(self) -> None:
        """Hanging man returns correct length."""
        d = _s(
            open=[9.0, 10.5],
            high=[10.5, 10.6],
            low=[8.5, 9.5],
            close=[10.4, 10.5],
        )
        result = CDLHANGINGMAN(d["open"], d["high"], d["low"], d["close"])
        assert len(result) == 2


class TestCDLRustBackend:
    """Verify Rust backend returns correct integer patterns."""

    def test_engulfing_rust_backend(self) -> None:
        """Rust backend correctly detects bullish engulfing."""
        d = _s(
            open=[11.0, 10.0, 8.5],
            high=[11.5, 10.5, 11.0],
            low=[10.0, 8.5, 8.3],
            close=[10.5, 9.0, 10.5],
        )
        result = CDL_ENGULFING(
            d["open"], d["high"], d["low"], d["close"],
            backend="rust",
        )
        assert result[2] == 100.0

    def test_doji_rust_backend(self) -> None:
        """Rust backend correctly detects doji."""
        d = _s(
            open=[10.0, 10.01],
            high=[11.0, 10.5],
            low=[9.0, 9.5],
            close=[10.5, 10.02],
        )
        result = CDLDOJI(
            d["open"], d["high"], d["low"], d["close"],
            backend="rust",
        )
        assert result[1] == 100.0


class TestCDLPIERCING:
    """Piercing Line: bullish reversal, gap down + close above midpoint."""

    def test_piercing_detected(self) -> None:
        """Bullish piercing is detected."""
        d = _s(
            open=[10.0, 8.0],
            high=[10.5, 10.2],
            low=[8.5, 7.8],
            close=[8.6, 9.8],
        )
        result = CDLPIERCING(
            d["open"], d["high"], d["low"], d["close"], backend="rust",
        )
        assert result[1] == 100.0


class TestCDLDARKCLOUDCOVER:
    """Dark Cloud Cover: bearish reversal, gap up + close below midpoint."""

    def test_dark_cloud_detected(self) -> None:
        """Bearish dark cloud cover is detected."""
        d = _s(
            open=[9.0, 10.8],
            high=[10.5, 11.0],
            low=[8.5, 9.0],
            close=[10.4, 9.3],
        )
        result = CDLDARKCLOUDCOVER(
            d["open"], d["high"], d["low"], d["close"], backend="rust",
        )
        assert result[1] == -100.0


class TestCDLMARUBOZU:
    """Marubozu: no/minimal shadows."""

    def test_bullish_marubozu(self) -> None:
        """Bullish marubozu detected."""
        d = _s(open=[10.0], high=[11.0], low=[10.0], close=[11.0])
        result = CDLMARUBOZU(
            d["open"], d["high"], d["low"], d["close"], backend="rust",
        )
        assert result[0] == 100.0

    def test_not_marubozu(self) -> None:
        """Bar with shadows is not marubozu."""
        d = _s(open=[10.0], high=[12.0], low=[8.0], close=[11.0])
        result = CDLMARUBOZU(
            d["open"], d["high"], d["low"], d["close"], backend="rust",
        )
        assert result[0] == 0.0


class TestCDLSPINNINGTOP:
    """Spinning Top: small body, similar shadows."""

    def test_returns_series(self) -> None:
        """Spinning top returns correct length."""
        d = _s(
            open=[10.0, 10.05],
            high=[10.5, 10.6],
            low=[9.5, 9.4],
            close=[10.1, 10.0],
        )
        result = CDLSPINNINGTOP(
            d["open"], d["high"], d["low"], d["close"], backend="rust",
        )
        assert len(result) == 2


class TestCDLRISEFALL3METHODS:
    """Rising/Falling Three Methods: 5-bar continuation pattern."""

    def test_returns_series(self) -> None:
        """Pattern returns correct length."""
        d = _s(
            open=[9.0, 9.8, 9.7, 9.9, 9.6],
            high=[10.5, 10.0, 9.9, 10.1, 10.8],
            low=[8.8, 9.5, 9.4, 9.6, 9.5],
            close=[10.4, 9.6, 9.5, 9.7, 10.7],
        )
        result = CDLRISEFALL3METHODS(
            d["open"], d["high"], d["low"], d["close"], backend="rust",
        )
        assert len(result) == 5


class TestCDLTHRUSTING:
    """Thrusting: bearish continuation."""

    def test_returns_series(self) -> None:
        """Thrusting returns correct length."""
        d = _s(
            open=[10.0, 9.0],
            high=[10.5, 9.7],
            low=[9.0, 8.5],
            close=[9.1, 9.4],
        )
        result = CDLTHRUSTING(
            d["open"], d["high"], d["low"], d["close"], backend="rust",
        )
        assert len(result) == 2
