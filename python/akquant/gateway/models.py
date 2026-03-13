from dataclasses import dataclass
from enum import Enum


class UnifiedOrderStatus(str, Enum):
    """Canonical order status used by broker adapters."""

    NEW = "New"
    SUBMITTED = "Submitted"
    PARTIALLY_FILLED = "PartiallyFilled"
    FILLED = "Filled"
    CANCELLED = "Cancelled"
    REJECTED = "Rejected"


class UnifiedErrorType(str, Enum):
    """Canonical error category used by broker adapters."""

    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"
    RISK_REJECTED = "risk_rejected"


@dataclass
class UnifiedOrderRequest:
    """Normalized order request."""

    client_order_id: str
    symbol: str
    side: str
    quantity: float
    price: float | None = None
    order_type: str = "Market"
    time_in_force: str = "GTC"


@dataclass
class UnifiedOrderSnapshot:
    """Normalized order state snapshot."""

    client_order_id: str
    broker_order_id: str
    symbol: str
    status: UnifiedOrderStatus
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    reject_reason: str = ""
    timestamp_ns: int = 0


@dataclass
class UnifiedTrade:
    """Normalized trade fill record."""

    trade_id: str
    broker_order_id: str
    client_order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    timestamp_ns: int


@dataclass
class UnifiedExecutionReport:
    """Normalized execution report."""

    broker_order_id: str
    client_order_id: str
    status: UnifiedOrderStatus
    symbol: str
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    reject_reason: str = ""
    timestamp_ns: int = 0


@dataclass
class UnifiedAccount:
    """Normalized account snapshot."""

    account_id: str
    equity: float
    cash: float
    available_cash: float
    timestamp_ns: int = 0


@dataclass
class UnifiedPosition:
    """Normalized position snapshot."""

    symbol: str
    quantity: float
    available_quantity: float
    avg_price: float = 0.0
    timestamp_ns: int = 0
