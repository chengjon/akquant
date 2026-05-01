from __future__ import annotations

import pytest
from akquant.futures import (
    FuturesContract,
    FuturesFeeConfig,
    calculate_commission,
    calculate_margin,
    calculate_notional,
    get_fee_rate,
    is_t_plus_zero,
    resolve_commission_rate,
)


class TestCalculateCommission:
    """Commission calculation tests."""

    def test_basic(self) -> None:
        """Basic commission: price=4000, qty=1, mult=300, rate=0.000023."""
        result = calculate_commission(4000.0, 1.0, 300.0, 0.000023)
        assert result == pytest.approx(27.6)

    def test_negative_inputs_use_abs(self) -> None:
        """Negative inputs should use absolute values."""
        result = calculate_commission(-4000.0, -1.0, 300.0, 0.000023)
        assert result == pytest.approx(27.6)

    def test_zero_rate(self) -> None:
        """Zero rate yields zero commission."""
        assert calculate_commission(100.0, 10.0, 10.0, 0.0) == 0.0


class TestCalculateMargin:
    """Margin calculation tests."""

    def test_basic(self) -> None:
        """Basic margin: qty=1, price=4000, mult=300, ratio=0.1 -> 120000."""
        result = calculate_margin(1.0, 4000.0, 300.0, 0.1)
        assert result == pytest.approx(120000.0)

    def test_negative_quantity(self) -> None:
        """Negative quantity (short) uses absolute value."""
        result = calculate_margin(-2.0, 4000.0, 300.0, 0.1)
        assert result == pytest.approx(240000.0)


class TestCalculateNotional:
    """Notional value tests."""

    def test_basic(self) -> None:
        """Basic notional: qty=1, price=4000, mult=300 -> 1.2M."""
        result = calculate_notional(1.0, 4000.0, 300.0)
        assert result == pytest.approx(1200000.0)


class TestFeePrefixMatching:
    """Fee prefix matching tests."""

    def test_longest_prefix_wins(self) -> None:
        """Longer prefix takes priority."""
        configs = [
            FuturesFeeConfig(commission_rate=0.0001, symbol_prefix="IF"),
            FuturesFeeConfig(commission_rate=0.00005, symbol_prefix="IF2"),
        ]
        assert get_fee_rate("IF2206", configs) == pytest.approx(0.00005)

    def test_no_match_returns_none(self) -> None:
        """No matching prefix returns None."""
        configs = [FuturesFeeConfig(commission_rate=0.0001, symbol_prefix="IF")]
        assert get_fee_rate("au2606", configs) is None

    def test_empty_prefix_matches_all(self) -> None:
        """Empty prefix matches any symbol."""
        configs = [FuturesFeeConfig(commission_rate=0.0001, symbol_prefix="")]
        assert get_fee_rate("anything", configs) == pytest.approx(0.0001)

    def test_empty_list_returns_none(self) -> None:
        """Empty config list returns None."""
        assert get_fee_rate("IF2206", []) is None


class TestResolveCommissionRate:
    """Commission rate resolution tests."""

    def test_falls_back_to_default(self) -> None:
        """Unmatched symbol uses default rate."""
        configs = [FuturesFeeConfig(commission_rate=0.0001, symbol_prefix="IF")]
        rate = resolve_commission_rate("au2606", configs, default_rate=0.000023)
        assert rate == pytest.approx(0.000023)

    def test_uses_prefix_match(self) -> None:
        """Matched symbol uses prefix rate."""
        configs = [FuturesFeeConfig(commission_rate=0.0001, symbol_prefix="IF")]
        rate = resolve_commission_rate("IF2206", configs, default_rate=0.000023)
        assert rate == pytest.approx(0.0001)


class TestTPlusZero:
    """Futures T+0 rule tests."""

    def test_always_true(self) -> None:
        """Futures always T+0."""
        assert is_t_plus_zero() is True


class TestFuturesContract:
    """FuturesContract dataclass tests."""

    def test_defaults(self) -> None:
        """Default field values."""
        c = FuturesContract(symbol="IF2206")
        assert c.multiplier == 1.0
        assert c.margin_ratio == 0.1

    def test_custom_values(self) -> None:
        """Custom field values."""
        c = FuturesContract(
            symbol="IF2206",
            multiplier=300.0,
            margin_ratio=0.1,
            tick_size=0.2,
        )
        assert c.multiplier == 300.0
        assert c.tick_size == 0.2
