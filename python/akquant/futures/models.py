from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class FuturesContract:
    """期货合约信息."""

    symbol: str
    multiplier: float = 1.0
    margin_ratio: float = 0.1
    tick_size: float = 1.0
    lot_size: float = 1.0
    expiry_date: Optional[int] = None
    settlement_type: Optional[str] = None


@dataclass(frozen=True)
class FuturesFeeConfig:
    """期货手续费配置."""

    commission_rate: float = 0.000023
    symbol_prefix: str = ""

    def matches(self, symbol: str) -> bool:
        """Check if this config matches the given symbol."""
        return symbol.startswith(self.symbol_prefix)


def get_fee_rate(symbol: str, fee_by_prefix: list[FuturesFeeConfig]) -> Optional[float]:
    """按最长前缀匹配查找手续费率."""
    best: Optional[FuturesFeeConfig] = None
    best_len = -1
    for cfg in fee_by_prefix:
        prefix = cfg.symbol_prefix
        if symbol.startswith(prefix) and len(prefix) > best_len:
            best = cfg
            best_len = len(prefix)
    return best.commission_rate if best is not None else None
