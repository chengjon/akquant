from __future__ import annotations

import pytest
from akquant.stock import (
    StockFeeConfig,
    StockInfo,
    calculate_commission,
    is_t_plus_one,
)


class TestCalculateCommission:
    """Stock commission calculation tests."""

    def test_buy_small_value_uses_min_commission(self) -> None:
        """Small buy uses min_commission: value=1000, brokerage=0.3 < 5 -> 5."""
        config = StockFeeConfig()
        result = calculate_commission(10.0, 100.0, "buy", config)
        assert result == pytest.approx(5.01)

    def test_sell_adds_stamp_tax(self) -> None:
        """Sell adds stamp tax: value=1000, brokerage=5, stamp=0.5, transfer=0.01."""
        config = StockFeeConfig()
        result = calculate_commission(10.0, 100.0, "sell", config)
        assert result == pytest.approx(5.51)

    def test_buy_large_value(self) -> None:
        """Large buy: value=100000, brokerage=30, no stamp, transfer=1.0."""
        config = StockFeeConfig()
        result = calculate_commission(50.0, 2000.0, "buy", config)
        assert result == pytest.approx(31.0)

    def test_sell_large_value(self) -> None:
        """Large sell: value=100000, brokerage=30, stamp=50, transfer=1.0."""
        config = StockFeeConfig()
        result = calculate_commission(50.0, 2000.0, "sell", config)
        assert result == pytest.approx(81.0)

    def test_custom_config(self) -> None:
        """Custom fee config values."""
        config = StockFeeConfig(
            commission_rate=0.001,
            stamp_tax=0.001,
            transfer_fee=0.0,
            min_commission=1.0,
        )
        result = calculate_commission(100.0, 10.0, "sell", config)
        # value=1000, brokerage=max(1.0, 1.0)=1.0, stamp=1.0, transfer=0.0
        assert result == pytest.approx(2.0)


class TestTPlusOne:
    """Stock T+1 rule tests."""

    def test_always_true(self) -> None:
        """Stock always T+1."""
        assert is_t_plus_one() is True


class TestStockInfo:
    """StockInfo dataclass tests."""

    def test_defaults(self) -> None:
        """Default field values."""
        info = StockInfo(symbol="600000")
        assert info.tick_size == 0.01
        assert info.lot_size == 100.0

    def test_custom_values(self) -> None:
        """Custom field values."""
        info = StockInfo(symbol="600000", tick_size=0.05, lot_size=200.0)
        assert info.tick_size == 0.05
        assert info.lot_size == 200.0


class TestStockFeeConfig:
    """StockFeeConfig dataclass tests."""

    def test_defaults(self) -> None:
        """Default field values."""
        config = StockFeeConfig()
        assert config.commission_rate == pytest.approx(0.0003)
        assert config.stamp_tax == pytest.approx(0.0005)
        assert config.transfer_fee == pytest.approx(0.00001)
        assert config.min_commission == 5.0
