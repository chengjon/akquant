from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StockInfo:
    """Stock instrument information."""

    symbol: str
    tick_size: float = 0.01
    lot_size: float = 100.0


@dataclass(frozen=True)
class StockFeeConfig:
    """Stock fee configuration."""

    commission_rate: float = 0.0003
    stamp_tax: float = 0.0005
    transfer_fee: float = 0.00001
    min_commission: float = 5.0
