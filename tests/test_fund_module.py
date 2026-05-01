from __future__ import annotations

import pytest
from akquant.fund import (
    FundFeeConfig,
    FundInfo,
    calculate_commission,
    is_t_plus_one,
)


class TestCalculateCommission:
    """Fund commission calculation tests."""

    def test_small_value_uses_min_commission(self) -> None:
        """Small value: transaction=1000, brokerage=0.3 < 5 -> 5."""
        config = FundFeeConfig()
        result = calculate_commission(10.0, 100.0, config)
        assert result == pytest.approx(5.01)

    def test_large_value(self) -> None:
        """Large value: transaction=100000, brokerage=30, transfer=1.0."""
        config = FundFeeConfig()
        result = calculate_commission(50.0, 2000.0, config)
        assert result == pytest.approx(31.0)

    def test_custom_config(self) -> None:
        """Custom fee config values."""
        config = FundFeeConfig(
            commission_rate=0.001,
            transfer_fee=0.0,
            min_commission=1.0,
        )
        result = calculate_commission(100.0, 10.0, config)
        # value=1000, brokerage=max(1.0, 1.0)=1.0, transfer=0.0
        assert result == pytest.approx(1.0)


class TestTPlusOne:
    """Fund T+1 rule tests."""

    def test_always_true(self) -> None:
        """Fund always T+1."""
        assert is_t_plus_one() is True


class TestFundInfo:
    """FundInfo dataclass tests."""

    def test_defaults(self) -> None:
        """Default field values."""
        info = FundInfo(symbol="159915")
        assert info.tick_size == 0.001
        assert info.lot_size == 1.0

    def test_custom_values(self) -> None:
        """Custom field values."""
        info = FundInfo(symbol="159915", tick_size=0.01, lot_size=100.0)
        assert info.tick_size == 0.01
        assert info.lot_size == 100.0


class TestFundFeeConfig:
    """FundFeeConfig dataclass tests."""

    def test_defaults(self) -> None:
        """Default field values."""
        config = FundFeeConfig()
        assert config.commission_rate == pytest.approx(0.0003)
        assert config.transfer_fee == pytest.approx(0.00001)
        assert config.min_commission == 5.0
