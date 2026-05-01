from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FundInfo:
    """Fund instrument information."""

    symbol: str
    tick_size: float = 0.001
    lot_size: float = 1.0


@dataclass(frozen=True)
class FundFeeConfig:
    """Fund fee configuration."""

    commission_rate: float = 0.0003
    transfer_fee: float = 0.00001
    min_commission: float = 5.0
