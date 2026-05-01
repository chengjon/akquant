from __future__ import annotations


def calculate_commission(
    quantity: float,
    commission_per_contract: float,
) -> float:
    """Calculate option trading commission.

    Formula matches Rust src/market/option.rs:
    commission = quantity * commission_per_contract
    Per-contract pricing, side-independent.
    """
    return abs(quantity) * abs(commission_per_contract)


def is_t_plus_zero() -> bool:
    """Option T+0: buy and sell on same day."""
    return True
