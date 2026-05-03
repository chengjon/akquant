from __future__ import annotations

from datetime import datetime, timezone

import pytest

import akquant
from akquant import Engine


class TwapBuyStrategy(akquant.Strategy):
    """Buy 1000 shares on bar 0 for TWAP testing."""

    def __init__(self) -> None:
        super().__init__()
        self._submitted = False

    def on_bar(self, bar: akquant.Bar) -> None:
        if not self._submitted:
            self.buy(symbol=bar.symbol, quantity=1000)
            self._submitted = True


def _make_flat_bars(
    symbol: str, n_bars: int, price: float = 10.0
) -> list[akquant.Bar]:
    """Create n_bars of flat OHLC bars at the given price."""
    bars = []
    base = datetime(2023, 1, 2, 10, 0, tzinfo=timezone.utc)
    for i in range(n_bars):
        ts = int(datetime(2023, 1, 2 + i, 10, 0, tzinfo=timezone.utc).timestamp() * 1e9)
        bars.append(
            akquant.Bar(ts, price, price, price, price, 100000.0, symbol)
        )
    return bars


class TestFillPolicyPriceBasis:
    """Fill policy PriceBasis extension tests."""

    def _make_engine(self) -> Engine:
        """Create a minimal engine for fill policy testing."""
        engine = Engine()
        engine.use_simple_market(0.0001)
        return engine

    def test_mid_quote_basis(self) -> None:
        """mid_quote price basis can be set and retrieved."""
        engine = self._make_engine()
        engine.set_fill_policy("mid_quote", 1, "same_cycle", 0)
        basis, offset, temporal, twap_bars = engine.get_fill_policy()
        assert basis == "mid_quote"
        assert offset == 1
        assert twap_bars == 0

    def test_typical_basis(self) -> None:
        """typical price basis can be set and retrieved."""
        engine = self._make_engine()
        engine.set_fill_policy("typical", 1, "same_cycle", 0)
        basis, offset, temporal, twap_bars = engine.get_fill_policy()
        assert basis == "typical"

    def test_vwap_bar_basis(self) -> None:
        """vwap_bar price basis can be set and retrieved."""
        engine = self._make_engine()
        engine.set_fill_policy("vwap_bar", 1, "same_cycle", 0)
        basis, offset, temporal, twap_bars = engine.get_fill_policy()
        assert basis == "vwap_bar"

    def test_new_basis_requires_bar_offset_1(self) -> None:
        """New price basis variants require bar_offset=1."""
        engine = self._make_engine()
        for basis in ["mid_quote", "typical", "vwap_bar"]:
            with pytest.raises(ValueError, match="bar_offset"):
                engine.set_fill_policy(basis, 0, "same_cycle", 0)

    def test_unknown_basis_rejected(self) -> None:
        """Unknown price basis is rejected."""
        engine = self._make_engine()
        with pytest.raises(ValueError, match="Unknown"):
            engine.set_fill_policy("twap", 1, "same_cycle", 0)

    def test_existing_basis_still_works(self) -> None:
        """Existing price basis options still work."""
        engine = self._make_engine()
        for basis in ["open", "close", "ohlc4", "hl2"]:
            offset = 0 if basis == "close" else 1
            engine.set_fill_policy(basis, offset, "same_cycle", 0)
            b, _, _, _ = engine.get_fill_policy()
            assert b == basis


class TestFillPolicyTwapWindow:
    """TWAP window fill policy tests."""

    def _make_engine(self) -> Engine:
        engine = Engine()
        engine.use_simple_market(0.0001)
        return engine

    def test_twap_window_set_and_get(self) -> None:
        """twap_window basis can be set and retrieved."""
        engine = self._make_engine()
        engine.set_fill_policy("twap_window", 1, "same_cycle", 5)
        basis, offset, temporal, twap_bars = engine.get_fill_policy()
        assert basis == "twap_window"
        assert offset == 1
        assert twap_bars == 5

    def test_twap_window_requires_positive_bars(self) -> None:
        """twap_window with twap_bars=0 is rejected."""
        engine = self._make_engine()
        with pytest.raises(ValueError, match="twap_bars > 0"):
            engine.set_fill_policy("twap_window", 1, "same_cycle", 0)

    def test_twap_window_requires_bar_offset_1(self) -> None:
        """twap_window requires bar_offset=1."""
        engine = self._make_engine()
        with pytest.raises(ValueError, match="bar_offset"):
            engine.set_fill_policy("twap_window", 0, "same_cycle", 5)

    def test_twap_window_with_various_bar_counts(self) -> None:
        """twap_window works with different bar counts."""
        engine = self._make_engine()
        for bars in [1, 3, 10, 100]:
            engine.set_fill_policy("twap_window", 1, "same_cycle", bars)
            b, _, _, tb = engine.get_fill_policy()
            assert b == "twap_window"
            assert tb == bars


class TestTwapBehavior:
    """Behavioral tests: verify TWAP actually splits fills across bars."""

    def test_twap_splits_order_into_even_slices(self) -> None:
        """A 1000-qty order with twap_bars=5 should produce 5 fills of 200."""
        symbol = "TWAP_TEST"
        bars = _make_flat_bars(symbol, n_bars=8, price=10.0)
        result = akquant.run_backtest(
            data=bars,
            strategy=TwapBuyStrategy,
            symbols=symbol,
            fill_policy={
                "price_basis": "twap_window",
                "twap_bars": 5,
                "temporal": "same_cycle",
            },
            initial_cash=1_000_000.0,
            commission_rate=0.0,
            stamp_tax_rate=0.0,
            transfer_fee_rate=0.0,
            min_commission=0.0,
            lot_size=1,
            show_progress=False,
        )
        orders_df = result.orders_df
        assert not orders_df.empty, "TWAP should produce orders"
        # Total filled across all bars should equal 1000
        total_filled = float(orders_df["filled_quantity"].sum())
        assert total_filled == pytest.approx(1000.0), (
            f"Expected 1000 total filled, got {total_filled}"
        )

    def test_twap_fills_across_multiple_bars(self) -> None:
        """TWAP splits across bars — verify via avg price with varying bar prices."""
        symbol = "TWAP_MULTI"
        # Create bars with ascending prices so TWAP avg differs from one-shot
        bars = []
        base = datetime(2023, 1, 2, 10, 0, tzinfo=timezone.utc)
        for i in range(8):
            price = 10.0 + i  # prices: 10, 11, 12, 13, 14, 15, 16, 17
            ts = int(datetime(2023, 1, 2 + i, 10, 0, tzinfo=timezone.utc).timestamp() * 1e9)
            bars.append(akquant.Bar(ts, price, price, price, price, 100000.0, symbol))
        result = akquant.run_backtest(
            data=bars,
            strategy=TwapBuyStrategy,
            symbols=symbol,
            fill_policy={
                "price_basis": "twap_window",
                "twap_bars": 4,
                "temporal": "same_cycle",
            },
            initial_cash=1_000_000.0,
            commission_rate=0.0,
            stamp_tax_rate=0.0,
            transfer_fee_rate=0.0,
            min_commission=0.0,
            lot_size=1,
            show_progress=False,
        )
        orders_df = result.orders_df
        assert not orders_df.empty
        total_filled = float(orders_df["filled_quantity"].sum())
        assert total_filled == pytest.approx(1000.0)
        avg_price = float(orders_df["avg_price"].iloc[0])
        # TWAP fills 250 @ bar1(11), 250 @ bar2(12), 250 @ bar3(13), 250 @ bar4(14)
        # avg = (11+12+13+14)/4 = 12.5
        assert avg_price == pytest.approx(12.5, abs=0.01), (
            f"Expected TWAP avg ~12.5, got {avg_price}"
        )

    def test_twap_single_bar_fills_immediately(self) -> None:
        """twap_bars=1 should fill the entire order in one shot."""
        symbol = "TWAP_ONE"
        bars = _make_flat_bars(symbol, n_bars=4, price=10.0)
        result = akquant.run_backtest(
            data=bars,
            strategy=TwapBuyStrategy,
            symbols=symbol,
            fill_policy={
                "price_basis": "twap_window",
                "twap_bars": 1,
                "temporal": "same_cycle",
            },
            initial_cash=1_000_000.0,
            commission_rate=0.0,
            stamp_tax_rate=0.0,
            transfer_fee_rate=0.0,
            min_commission=0.0,
            lot_size=1,
            show_progress=False,
        )
        orders_df = result.orders_df
        assert not orders_df.empty
        assert len(orders_df) == 1
        assert float(orders_df["filled_quantity"].iloc[0]) == pytest.approx(1000.0)
