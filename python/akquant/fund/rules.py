from __future__ import annotations

from .models import FundFeeConfig


def calculate_commission(
    price: float,
    quantity: float,
    config: FundFeeConfig,
) -> float:
    """Calculate fund trading commission.

    Formula matches Rust src/market/fund.rs:
    brokerage = max(transaction_value * commission_rate, min_commission)
    transfer_fee = transaction_value * transfer_fee
    total = brokerage + transfer_fee
    """
    transaction_value = abs(price) * abs(quantity)
    brokerage = max(transaction_value * config.commission_rate, config.min_commission)
    transfer = transaction_value * config.transfer_fee
    return brokerage + transfer


def is_t_plus_one() -> bool:
    """Fund T+1: same as stock, buy does not increase available position."""
    return True
