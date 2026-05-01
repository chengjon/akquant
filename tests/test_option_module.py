from __future__ import annotations

import pytest
from akquant.option import (
    OptionContract,
    calculate_commission,
    calculate_option_margin,
    is_t_plus_zero,
)


class TestCalculateCommission:
    """Option commission calculation tests."""

    def test_basic(self) -> None:
        """Basic commission: qty=10, rate=5.0 -> 50.0."""
        result = calculate_commission(10.0, 5.0)
        assert result == pytest.approx(50.0)

    def test_negative_quantity(self) -> None:
        """Negative quantity uses absolute value."""
        result = calculate_commission(-10.0, 5.0)
        assert result == pytest.approx(50.0)

    def test_zero_quantity(self) -> None:
        """Zero quantity yields zero commission."""
        assert calculate_commission(0.0, 5.0) == 0.0


class TestCalculateOptionMargin:
    """Option margin calculation tests."""

    def test_long_zero_margin(self) -> None:
        """Long position has zero margin."""
        result = calculate_option_margin(
            quantity=10.0,
            option_price=5.0,
            underlying_price=3000.0,
            multiplier=10000.0,
            margin_ratio=0.1,
            is_short=False,
        )
        assert result == 0.0

    def test_short_with_underlying(self) -> None:
        """Short with underlying price."""
        result = calculate_option_margin(
            quantity=-10.0,
            option_price=5.0,
            underlying_price=3000.0,
            multiplier=10000.0,
            margin_ratio=0.1,
            is_short=True,
        )
        # margin_per_unit = 5 + 3000 * 0.1 = 305
        # total = 305 * 10000 * 10 = 30500000
        assert result == pytest.approx(30_500_000.0)

    def test_short_without_underlying(self) -> None:
        """Short without underlying price."""
        result = calculate_option_margin(
            quantity=-10.0,
            option_price=5.0,
            underlying_price=None,
            multiplier=10000.0,
            margin_ratio=0.1,
            is_short=True,
        )
        # margin_per_unit = 5 * (1 + 0.1) = 5.5
        # total = 5.5 * 10000 * 10 = 550000
        assert result == pytest.approx(550_000.0)

    def test_short_zero_underlying(self) -> None:
        """Short with underlying_price=0 falls back to no-underlying formula."""
        result = calculate_option_margin(
            quantity=-10.0,
            option_price=5.0,
            underlying_price=0.0,
            multiplier=10000.0,
            margin_ratio=0.1,
            is_short=True,
        )
        assert result == pytest.approx(550_000.0)


class TestTPlusZero:
    """Option T+0 rule tests."""

    def test_always_true(self) -> None:
        """Option always T+0."""
        assert is_t_plus_zero() is True


class TestOptionContract:
    """OptionContract dataclass tests."""

    def test_defaults(self) -> None:
        """Default field values."""
        c = OptionContract(symbol="10003720")
        assert c.multiplier == 1.0
        assert c.margin_ratio == 0.1

    def test_custom_values(self) -> None:
        """Custom field values."""
        c = OptionContract(
            symbol="10003720",
            multiplier=10000.0,
            margin_ratio=0.1,
            option_type="call",
            strike_price=3.0,
            underlying_symbol="510050",
            expiry_date=20250620,
        )
        assert c.multiplier == 10000.0
        assert c.option_type == "call"
