from __future__ import annotations

from .models import StockFeeConfig


def calculate_commission(
    price: float,
    quantity: float,
    side: str,
    config: StockFeeConfig,
) -> float:
    """Calculate stock trading commission.

    Formula matches Rust src/market/stock.rs:
    brokerage = max(transaction_value * commission_rate, min_commission)
    stamp_tax = transaction_value * stamp_tax (sell only)
    transfer_fee = transaction_value * transfer_fee
    total = brokerage + stamp_tax + transfer_fee
    """
    transaction_value = abs(price) * abs(quantity)
    brokerage = max(transaction_value * config.commission_rate, config.min_commission)
    stamp = transaction_value * config.stamp_tax if side == "sell" else 0.0
    transfer = transaction_value * config.transfer_fee
    return brokerage + stamp + transfer


def is_t_plus_one() -> bool:
    """Stock T+1: buy does not increase available position on same day."""
    return True
