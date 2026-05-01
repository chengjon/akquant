from __future__ import annotations

from .models import FuturesFeeConfig, get_fee_rate


def calculate_commission(
    price: float,
    quantity: float,
    multiplier: float,
    commission_rate: float,
) -> float:
    """计算期货交易手续费.

    公式: price * quantity * multiplier * commission_rate
    与 Rust src/market/futures.rs 一致.
    """
    return abs(price) * abs(quantity) * abs(multiplier) * abs(commission_rate)


def resolve_commission_rate(
    symbol: str,
    fee_by_prefix: list[FuturesFeeConfig],
    default_rate: float,
) -> float:
    """解析手续费率: 先查前缀匹配，无匹配则用默认值."""
    rate = get_fee_rate(symbol, fee_by_prefix)
    return rate if rate is not None else default_rate


def is_t_plus_zero() -> bool:
    """期货 T+0: 买入后可立即卖出."""
    return True
